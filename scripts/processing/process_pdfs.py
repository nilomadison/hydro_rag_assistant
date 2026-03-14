"""
process_pdfs.py

Extracts text from every PDF in data/raw/ using layout-aware parsing,
preserves section headings and document structure as Markdown, and
writes one .md file per PDF into data/processed/.

Uses pymupdf4llm for:
  - Correct multi-column reading order
  - Header / footer removal
  - Table detection (rendered as Markdown tables)
  - Heading identification (by font size → # tags)
"""

import logging
import re
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


# ── helpers ──────────────────────────────────────────────────────────────
def extract_text(pdf_path: Path) -> str:
    """Extract text from a PDF with layout-aware parsing.

    Returns Markdown-formatted text with page-break markers.
    """
    pages = pymupdf4llm.to_markdown(
        str(pdf_path),
        page_chunks=True,
        header=False,       # strip repeated page headers
        footer=False,       # strip repeated page footers
        ignore_images=True, # skip images (not useful for text RAG)
    )

    sections: list[str] = []
    for chunk in pages:
        page_num = chunk["metadata"]["page"]
        text = chunk["text"].strip()
        if text:
            sections.append(f"<!-- Page {page_num} -->\n\n{text}")
        else:
            logger.warning("  ⚠  Page %d yielded no text – skipped", page_num)

    return "\n\n---\n\n".join(sections)


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
    """Find every PDF in RAW_DIR, extract + normalize, write to PROCESSED_DIR."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(RAW_DIR.glob("*.pdf"))

    if not pdf_files:
        logger.warning("No PDFs found in %s", RAW_DIR)
        return

    logger.info("Found %d PDF(s) in %s", len(pdf_files), RAW_DIR)

    for pdf_path in pdf_files:
        logger.info("Processing: %s", pdf_path.name)

        raw_text = extract_text(pdf_path)
        clean_text = normalize(raw_text)

        out_path = PROCESSED_DIR / f"{pdf_path.stem}.md"
        out_path.write_text(clean_text, encoding="utf-8")

        logger.info("  ✓  Saved %s (%d chars)", out_path.name, len(clean_text))

    logger.info("Done — %d file(s) processed.", len(pdf_files))


if __name__ == "__main__":
    process_all()
