"""Extract and clean PDFs into archive and embedding markdown outputs.

For each PDF in ``data/raw`` this script writes two files to ``data/processed``:

- ``<name>.md``: archive-friendly output with page markers
- ``<name>.embed.md``: aggressively cleaned output for chunking/embedding
"""

import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf4llm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


@dataclass(frozen=True)
class PageChunk:
    """Text chunk and page number from PDF extraction."""

    page: int
    text: str


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for archive and embedding outputs."""

    boilerplate_page_ratio: float = 0.35
    boilerplate_min_chars: int = 30


CONFIG = PipelineConfig()


# ── helpers ──────────────────────────────────────────────────────────────
def extract_pages(pdf_path: Path) -> list[PageChunk]:
    """Extract markdown text by page from a PDF."""
    pages = pymupdf4llm.to_markdown(
        str(pdf_path),
        page_chunks=True,
        header=False,       # strip repeated page headers
        footer=False,       # strip repeated page footers
        ignore_images=True, # skip images (not useful for text RAG)
    )

    extracted: list[PageChunk] = []
    for chunk in pages:
        page_num = chunk["metadata"]["page"]
        text = chunk["text"].strip()
        if text:
            extracted.append(PageChunk(page=page_num, text=text))
        else:
            logger.warning("  ⚠  Page %d yielded no text – skipped", page_num)

    return extracted


def build_archive_text(pages: list[PageChunk]) -> str:
    """Build archive output that preserves page boundaries."""
    sections = [f"<!-- Page {chunk.page} -->\n\n{chunk.text}" for chunk in pages]

    return "\n\n---\n\n".join(sections)


def normalize_for_repeat(line: str) -> str:
    """Normalize a line for repeated boilerplate detection."""
    text = line.strip().lower()
    text = re.sub(r"[*_`#]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def looks_like_known_header_footer(norm_line: str) -> bool:
    """Return True for known running header/footer patterns."""
    patterns = (
        r"uh.?ctahr",
        r"vc-?\d+",
        r"hort\. 843:65-72",
        r"proceedings of the international symposium on soilless culture",
        r"kratky, b\.a\. 2009",
        r"college of tropical agriculture",
    )
    return any(re.search(pattern, norm_line) for pattern in patterns)


def is_scanner_or_page_artifact(line: str) -> bool:
    """Return True for scanner/page-number noise lines."""
    stripped = line.strip()
    if re.fullmatch(r"\d+", stripped):
        return True
    if re.fullmatch(r"[ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]+", stripped):
        return True
    if re.fullmatch(r"\d+\s+\*\*\d+\*\*\s+\d+", stripped):
        return True
    return False


def strip_repeated_boilerplate(
    pages: list[PageChunk],
    config: PipelineConfig,
) -> tuple[list[PageChunk], int]:
    """Remove repeated running headers/footers across pages."""
    if not pages:
        return pages, 0

    min_pages = max(2, math.ceil(len(pages) * config.boilerplate_page_ratio))
    page_counts: dict[str, int] = {}

    for chunk in pages:
        seen: set[str] = set()
        for raw_line in chunk.text.splitlines():
            if is_scanner_or_page_artifact(raw_line):
                continue
            norm = normalize_for_repeat(raw_line)
            if len(norm) < config.boilerplate_min_chars and not looks_like_known_header_footer(norm):
                continue
            seen.add(norm)
        for norm in seen:
            page_counts[norm] = page_counts.get(norm, 0) + 1

    removed = 0
    cleaned_pages: list[PageChunk] = []
    for chunk in pages:
        kept_lines: list[str] = []
        for raw_line in chunk.text.splitlines():
            if is_scanner_or_page_artifact(raw_line):
                removed += 1
                continue

            norm = normalize_for_repeat(raw_line)
            if looks_like_known_header_footer(norm) and page_counts.get(norm, 0) >= 2:
                removed += 1
                continue
            repeated = page_counts.get(norm, 0) >= min_pages
            noisy_repeat = repeated and (
                len(norm) >= config.boilerplate_min_chars
                and (
                    looks_like_known_header_footer(norm)
                    or page_counts.get(norm, 0) >= max(3, math.ceil(len(pages) * 0.75))
                )
            )
            if noisy_repeat:
                removed += 1
                continue

            kept_lines.append(raw_line)

        cleaned_pages.append(PageChunk(page=chunk.page, text="\n".join(kept_lines).strip()))

    return cleaned_pages, removed


def clean_artifacts(text: str) -> str:
    """Apply OCR/layout artifact cleanup for embedding output."""
    # Remove markdown page comments and explicit separators in embedding output.
    text = re.sub(r"^\s*<!--\s*Page\s+\d+\s*-->\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*---\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"^.*Published by the College of Tropical Agriculture and Human Resources.*$",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^.*Find CTAHR publications at www\.ctahr\.hawaii\.edu/freepubs\..*$",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Remove scanner tokens and standalone page numerals/roman numerals.
    text = re.sub(r"^\s*\d+\s+\*\*\d+\*\*\s+\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(?:\d+|[ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]+)\s*$", "", text, flags=re.MULTILINE)

    # Normalize common OCR unit artifacts.
    text = re.sub(r"\[\s*o\s*\]\s*F", "deg F", text)
    text = re.sub(r"\[\s*o\s*\]\s*C", "deg C", text)
    text = re.sub(r"\[\s*-\s*([0-9]+)\s*\]", r"^-\1", text)
    text = re.sub(r"\[\s*([0-9]+)\s*\]", r"^\1", text)

    # Normalize broken spacing in exponents/units.
    text = re.sub(r"\s+\^", "^", text)
    text = re.sub(r"\^\s+", "^", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text


def drop_junk_table_blocks(text: str) -> str:
    """Remove malformed placeholder table blocks such as Col1/Col2 grids."""
    lines = text.splitlines()
    output: list[str] = []
    i = 0

    def is_junk_table_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped.startswith("|"):
            return False
        if re.search(r"\bCol\d+\b", stripped):
            return True
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            return False
        empty_cells = sum(1 for cell in cells if not cell)
        return empty_cells >= max(2, len(cells) - 1)

    while i < len(lines):
        line = lines[i]
        if is_junk_table_line(line):
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                i += 1
            continue

        output.append(line)
        i += 1

    return "\n".join(output)


def should_preserve_linebreak(line: str) -> bool:
    """Return True if line should keep hard line break in reflow."""
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith(("#", "-", "*", "|", "<!--")):
        return True
    if re.match(r"^\d+[.)]\s+", stripped):
        return True
    if re.match(r"^[A-Z][A-Z0-9\s&:/-]{3,}$", stripped):
        return True
    return False


def reflow_paragraphs(text: str) -> str:
    """Reflow hard-wrapped lines into paragraphs while preserving structure."""
    lines = text.splitlines()
    output: list[str] = []
    paragraph = ""

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            output.append(paragraph)
            paragraph = ""

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            output.append("")
            continue

        if should_preserve_linebreak(line):
            flush_paragraph()
            output.append(line)
            continue

        if not paragraph:
            paragraph = line
            continue

        if paragraph.endswith("-") and re.match(r"^[a-z]", line):
            paragraph = paragraph[:-1] + line
        else:
            paragraph = f"{paragraph} {line}"

    flush_paragraph()
    return "\n".join(output)


def prune_embedding_sections(text: str) -> str:
    """Drop low-value trailing reference sections for embedding output."""
    prune_headers = {
        "REFERENCES",
        "LITERATURE CITED",
        "IMAGE REFERENCES",
        "TABLE REFERENCES",
        "FIGURE REFERENCES",
        "ACKNOWLEDGEMENTS",
        "DISCLAIMER",
        "NOTICE",
    }

    lines = text.splitlines()
    output: list[str] = []
    skipping = False

    for line in lines:
        stripped = line.strip()
        clean = re.sub(r"^[#*\s]+|[#*\s]+$", "", stripped)
        normalized = re.sub(r"\s+", " ", clean).upper()

        if normalized in prune_headers or any(
            normalized.startswith(f"{header} ") for header in prune_headers
        ):
            skipping = True

        if not skipping:
            output.append(line)

    return "\n".join(output)


def build_embedding_text(
    pages: list[PageChunk],
    config: PipelineConfig,
) -> tuple[str, dict[str, int]]:
    """Build cleaned embedding output and return cleanup metrics."""
    stripped_pages, removed_boilerplate = strip_repeated_boilerplate(pages, config)
    combined = "\n\n".join(chunk.text for chunk in stripped_pages if chunk.text)
    cleaned = clean_artifacts(combined)
    cleaned = drop_junk_table_blocks(cleaned)
    cleaned = prune_embedding_sections(cleaned)
    cleaned = reflow_paragraphs(cleaned)
    cleaned = prune_embedding_sections(cleaned)
    cleaned = normalize(cleaned)

    metrics = {
        "pages_in": len(pages),
        "boilerplate_lines_removed": removed_boilerplate,
        "chars_out": len(cleaned),
    }
    return cleaned, metrics


def normalize(text: str) -> str:
    """Apply light normalization to extracted Markdown text.

    • Collapse runs of 3+ newlines to 2
    • Strip trailing whitespace from each line
    • Strip leading / trailing whitespace from the whole document
    """
    # Per-line trailing-whitespace strip
    text = "\n".join(line.rstrip() for line in text.splitlines())

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ── main routine ─────────────────────────────────────────────────────────
def process_all() -> None:
    """Find every PDF in RAW_DIR and write archive + embedding outputs."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(RAW_DIR.glob("*.pdf"))

    if not pdf_files:
        logger.warning("No PDFs found in %s", RAW_DIR)
        return

    logger.info("Found %d PDF(s) in %s", len(pdf_files), RAW_DIR)

    for pdf_path in pdf_files:
        logger.info("Processing: %s", pdf_path.name)

        pages = extract_pages(pdf_path)
        if not pages:
            logger.warning("  ⚠  No extractable pages found in %s", pdf_path.name)
            continue

        archive_text = normalize(build_archive_text(pages))
        embedding_text, metrics = build_embedding_text(pages, CONFIG)

        archive_path = PROCESSED_DIR / f"{pdf_path.stem}.md"
        embedding_path = PROCESSED_DIR / f"{pdf_path.stem}.embed.md"
        archive_path.write_text(archive_text, encoding="utf-8")
        embedding_path.write_text(embedding_text, encoding="utf-8")

        logger.info("  ✓  Saved %s (%d chars)", archive_path.name, len(archive_text))
        logger.info("  ✓  Saved %s (%d chars)", embedding_path.name, len(embedding_text))
        logger.info(
            "    embedding metrics: pages=%d boilerplate_removed=%d",
            metrics["pages_in"],
            metrics["boilerplate_lines_removed"],
        )

    logger.info("Done — %d file(s) processed.", len(pdf_files))


if __name__ == "__main__":
    process_all()
