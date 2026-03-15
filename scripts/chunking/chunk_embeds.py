"""Chunk embed.md files into overlapping text segments ready for embedding.

For each ``.embed.md`` file in ``data/processed/`` this script writes a JSON
array to ``data/chunks/<name>.chunks.json`` where each element is:

    {
        "source":     "<document stem>",
        "chunk_id":   <int>,
        "text":       "<chunk text>",
        "char_count": <int>
    }

Chunking strategy
-----------------
Markdown-aware recursive splitting:

1. The document is first split at heading boundaries (``#`` / ``##``).
   The heading is stored and prepended to every chunk produced from its
   section, so retrieval results always carry their section context.

2. Within each section the body is split recursively using a hierarchy of
   separators: paragraph break → line break → sentence end → word space.
   Finer separators are only tried when coarser ones cannot produce a chunk
   small enough.

3. A short tail of each chunk is prepended to the next (overlap), trimmed to
   a word boundary, so sentences that straddle a split are represented in
   both neighboring chunks.

Target chunk size (512 chars ≈ 85–100 words) sits well within the 256-token
context window of the ``all-MiniLM-L6-v2`` embedding model used downstream.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── paths ─────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CHUNKS_DIR = PROJECT_ROOT / "data" / "chunks"

# Separator hierarchy used by the recursive splitter, coarsest → finest.
SEPARATORS = ["\n\n", "\n", ". ", " "]


# ── config ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ChunkConfig:
    """Tunable parameters for the chunking pipeline."""

    chunk_size: int = 512   # target maximum characters per chunk
    overlap: int = 64       # characters of tail from previous chunk to prepend
    min_chunk_size: int = 50  # discard orphan chunks shorter than this


CONFIG = ChunkConfig()


# ── splitting helpers ─────────────────────────────────────────────────────
def split_by_headings(text: str) -> list[tuple[str, str]]:
    """Split a document into (heading, body) pairs at ``#`` / ``##`` lines.

    Any text that precedes the first heading is returned as a section with an
    empty heading string.
    """
    pattern = re.compile(r"^(#{1,2} .+)$", re.MULTILINE)
    parts = pattern.split(text)

    sections: list[tuple[str, str]] = []

    # parts[0] is content before the first heading (may be empty)
    if parts[0].strip():
        sections.append(("", parts[0].strip()))

    # Remaining parts alternate: heading, body, heading, body, …
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections.append((heading, body))

    return sections


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """Split *text* into chunks no larger than *chunk_size* characters.

    Tries each separator in order; falls back to a hard character split only
    when no separator is present.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    if not separators:
        # Last resort: hard split at chunk_size boundary
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep, remaining = separators[0], separators[1:]

    if sep not in text:
        # This separator doesn't appear; try the next finer one
        return _recursive_split(text, chunk_size, remaining)

    chunks: list[str] = []
    current = ""

    for piece in text.split(sep):
        if not piece.strip():
            continue

        candidate = f"{current}{sep}{piece}" if current else piece

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if len(piece) > chunk_size:
                # This single piece is also too large — recurse with finer seps
                sub = _recursive_split(piece.strip(), chunk_size, remaining)
                if sub:
                    chunks.extend(sub[:-1])
                    current = sub[-1]
                else:
                    current = ""
            else:
                current = piece.strip()

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if c.strip()]


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    """Prepend a tail of each chunk to the next, aligned to a word boundary.

    This ensures that content near a chunk boundary appears in both
    neighboring chunks, improving retrieval recall for queries that span
    the split point.
    """
    if overlap == 0 or len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        tail = chunks[i - 1][-overlap:]
        # Trim the tail to start at a word boundary
        space_pos = tail.find(" ")
        if space_pos >= 0:
            tail = tail[space_pos + 1:]
        result.append(f"{tail} {chunks[i]}" if tail else chunks[i])

    return result


def chunk_document(text: str, config: ChunkConfig) -> list[str]:
    """Chunk a full document, preserving section headings as context.

    Each chunk is prefixed with its section heading so that a retrieved
    snippet always identifies the part of the document it came from.
    """
    all_chunks: list[str] = []

    for heading, body in split_by_headings(text):
        if not body:
            # Section with no body (e.g. a stand-alone title) — keep as-is.
            if heading:
                all_chunks.append(heading)
            continue

        raw_chunks = _recursive_split(body, config.chunk_size, SEPARATORS)
        overlapping = _apply_overlap(raw_chunks, config.overlap)

        for chunk in overlapping:
            full = f"{heading}\n\n{chunk}" if heading else chunk
            if len(full) >= config.min_chunk_size:
                all_chunks.append(full)

    return all_chunks


# ── I/O ───────────────────────────────────────────────────────────────────
def chunk_file(embed_path: Path, config: ChunkConfig) -> list[dict]:
    """Load one ``.embed.md`` file, chunk it, and return a list of records."""
    text = embed_path.read_text(encoding="utf-8")
    chunks = chunk_document(text, config)

    # Strip the ".embed" suffix that process_pdfs.py appends before ".md"
    source = embed_path.stem.removesuffix(".embed")

    return [
        {
            "source": source,
            "chunk_id": i,
            "text": chunk,
            "char_count": len(chunk),
        }
        for i, chunk in enumerate(chunks)
    ]


def _log_chunk_stats(records: list[dict], out_path: Path) -> None:
    """Log a one-line summary of chunk count and size distribution."""
    counts = [r["char_count"] for r in records]
    avg = sum(counts) / len(counts) if counts else 0
    logger.info(
        "  → %d chunks  avg %.0f chars  min %d  max %d  saved to %s",
        len(records),
        avg,
        min(counts, default=0),
        max(counts, default=0),
        out_path.name,
    )


# ── entry point ───────────────────────────────────────────────────────────
def chunk_all() -> None:
    """Chunk every ``.embed.md`` file found in ``data/processed/``."""
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    embed_files = sorted(PROCESSED_DIR.glob("*.embed.md"))
    if not embed_files:
        logger.warning("No .embed.md files found in %s", PROCESSED_DIR)
        return

    logger.info("Found %d embed file(s) in %s", len(embed_files), PROCESSED_DIR)

    for embed_path in embed_files:
        logger.info("Chunking: %s", embed_path.name)
        records = chunk_file(embed_path, CONFIG)

        source_name = embed_path.stem.removesuffix(".embed")
        out_path = CHUNKS_DIR / f"{source_name}.chunks.json"
        out_path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        _log_chunk_stats(records, out_path)

    logger.info("Done — %d file(s) chunked.", len(embed_files))


if __name__ == "__main__":
    chunk_all()
