# 🌱 Hydroponic RAG Assistant

A retrieval-augmented generation (RAG) application that answers plain-language questions about hydroponic gardening — pH levels, EC ranges, nutrient deficiencies, light requirements, and more — without requiring users to dig through dense technical PDFs.

Built as a portfolio project to demonstrate the full AI engineering loop: problem framing, data ingestion, RAG pipeline construction, evaluation, iteration, deployment, and monitoring.

---

## 🎯 Project Goal

Hobbyist hydroponic growers often struggle to find quick, accurate answers to specific growing questions. Extension service guides and academic resources contain the right information, but they're dense, jargon-heavy, and time-consuming to navigate. This assistant bridges that gap by retrieving relevant information from trusted sources and delivering it in plain, beginner-friendly language.

**What good looks like:** The system retrieves the right source material and gives an answer a knowledgeable gardener would agree with.

**What failure looks like:** Confidently wrong answers - especially on nutrient deficiency diagnosis - where bad advice wastes time and harms plants.

**V1 Scope:** Hydroponics-specific queries covering pH, EC, light requirements, nutrient deficiencies, and growth timelines for common beginner crops.

---

## 🗂️ Project Structure

```
hydro_rag_assistant/
│
├── data/
│   ├── raw/              # Original downloaded PDFs + sources.md manifest
│   ├── processed/        # Dual-output markdown from processing pipeline
│   │   ├── <name>.md         # Archive — full text with page markers
│   │   └── <name>.embed.md   # Embedding-ready — cleaned and reflowed
│   └── chunks/           # Final chunked documents ready for embedding
│
├── scripts/
│   ├── processing/
│   │   └── process_pdfs.py          # PDF → archive .md + embedding .embed.md
│   └── chunking/
│       └── chunk_embeds.py           # Split .embed.md into overlapping chunks
│
├── .gitignore
└── README.md
```

### Dual-Output Processing

Each source PDF produces two markdown files in `data/processed/`:

| Output | Filename | Purpose |
|---|---|---|
| **Archive** | `<name>.md` | Preserves the full extracted text with `<!-- Page N -->` markers. Useful for auditing, debugging, and traceability back to the original document. |
| **Embedding** | `<name>.embed.md` | Aggressively cleaned version — repeated headers/footers stripped, junk tables removed, OCR artifacts normalized, reference sections pruned, paragraphs reflowed. Ready for chunking and embedding. |

---

## 🔧 Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| PDF Parsing | `pymupdf4llm` | Markdown-native extraction with native multi-column handling |
| **Embedding Model** | **`sentence-transformers` (all-MiniLM-L6-v2)** | **Open-source, runs locally (no API), 256-token context. Trade-off: smaller model (22M params) vs. accuracy for domain-specific use. Tuned for semantic similarity over exact phrase matching.** |
| Vector Database | ChromaDB | Local, persistent, no external service dependency |
| LLM | OpenAI GPT-4o-mini | Cost-effective closed-source fallback for generation once retrieval is proven |
| API Framework | FastAPI | Async-ready, auto-generated OpenAPI docs |
| UI (optional) | Streamlit | Rapid prototyping for demo and user testing |

---

## 📚 Data Sources

All source material is freely available from reputable agricultural institutions. The full manifest with authors, years, and document types lives in [`data/raw/sources.md`](data/raw/sources.md).

| Document | Source | Author(s) | Year |
|---|---|---|---|
| A Guide to Home Hydroponics for Leafy Greens | Cornell Controlled Environment Agriculture (Cornell University) | Ryan Ronzoni, Neil Mattson | 2020 |
| Growing Direct-Seeded Watercress by Two Non-Circulating Hydroponic Methods | CTAHR, University of Hawai'i at Mānoa | B. A. Kratky | 2015 |
| Three Non-Circulating Hydroponic Methods for Growing Lettuce | CTAHR, University of Hawai'i at Mānoa | B. A. Kratky | 2009 |

---

## 🔄 The 7-Step Engineering Loop

This project is being built following a deliberate AI engineering methodology:

1. **Problem Framing** — Define the user, pain point, success criteria, and failure modes before writing code
2. **Data Collection & Preparation** — Source, parse, clean, and chunk documents with a reproducible pipeline
3. **RAG Pipeline** — Build retrieval and generation layers independently, then wire together
4. **Evaluation** — Hand-craft a ground-truth Q&A dataset; measure retrieval and generation separately
5. **Iteration** — Change one thing at a time, re-run evals, log every result
6. **Deployment** — Wrap in FastAPI, containerize with Docker, deploy to a cloud host
7. **Monitoring** — Log real queries, identify failure patterns, feed back into the eval set

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- An OpenAI API key

### Installation

```bash
git clone https://github.com/nilomadison/hydro_rag_assistant.git
cd hydro_rag_assistant
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### Environment Setup

```bash
cp .env.example .env
# Add your OpenAI API key to .env
```

### Process Source PDFs

```bash
python scripts/processing/process_pdfs.py
```

This reads every PDF in `data/raw/` and writes the dual-output markdown files (archive `.md` + embedding `.embed.md`) into `data/processed/`.

### Chunk the Processed Documents

```bash
python scripts/chunking/chunk_embeds.py
```

This reads every `.embed.md` file from `data/processed/` and splits it into overlapping chunks optimized for embedding, writing JSON arrays to `data/chunks/`.

#### Chunking Strategy: Markdown-Aware Recursive Splitting

The chunker respects document structure while respecting embedding model constraints:

1. **Heading boundaries first** — the document is split at `#` and `##` markers. Each heading is prepended to all chunks from its section, so retrieved snippets always carry their source context.

2. **Recursive sub-splitting** — within each section, text is split using a hierarchy of separators (paragraph break → line break → sentence end → word space), using only finer separators when coarser ones would produce chunks that are too large.

3. **Word-aligned overlap** — a 64-character tail from each chunk is prepended to the next (aligned to a word boundary), ensuring sentences that straddle a split appear in both neighboring chunks for better retrieval recall.

**Chunk Size: 512 characters (≈85–100 words)**

This limit was chosen to suit the embedding model:
- **Model:** `sentence-transformers` all-MiniLM-L6-v2
- **Max context:** 256 tokens (≈512 chars for typical English text)
- **Safety margin:** 512 chars leaves room for dense technical vocabulary (pH levels, EC ranges, nutrient formulas) without risk of token truncation
- **Results:** Watercress (210 chunks), Home Guide (236 chunks), Lettuce paper (48 chunks) — each under 674 chars max

---

## 📊 Evaluation

The project will include a structured evaluation framework with two layers:

**Retrieval Evaluation** — measures whether the correct source document appears in the top retrieved chunks for each eval question. Target: >80% hit rate.

**Generation Evaluation** — measures answer correctness and plain-language quality against a hand-crafted ground truth dataset. Scored 0–2 per question.

Results will be logged in `eval/results_log.md` with each iteration tracked against the baseline.

---

## 🗺️ Roadmap

- [x] Problem framing and scope definition
- [x] Data source identification and collection
- [x] PDF processing pipeline (dual-output: archive `.md` + embedding `.embed.md`)
- [x] Chunking strategy and implementation
- [ ] ChromaDB setup and chunk ingestion
- [ ] Retrieval and generation pipeline
- [ ] Evaluation dataset (50–60 Q&A pairs)
- [ ] Baseline eval scores
- [ ] FastAPI deployment
- [ ] Docker containerization
- [ ] Streamlit frontend
- [ ] Monitoring and logging

---

## 🧠 What I Learned

### PDF Parsing: `pdfplumber` → `pymupdf4llm`

The initial approach used `pdfplumber` for text extraction, but it struggled with multi-column layouts, produced garbled output for complex pages, and couldn't distinguish headers/footers from body text. Switching to `pymupdf4llm` solved these issues — it handles multi-column reflow natively, strips repeated headers/footers, detects tables, and outputs clean markdown that preserves document structure for downstream chunking.

### Dual-Output Processing

Rather than a single cleaned output, the pipeline writes two files per source: a full-fidelity **archive** (with page markers for traceability) and an aggressively cleaned **embedding-ready** version (boilerplate stripped, OCR artifacts normalized, reference sections pruned, paragraphs reflowed). This separation keeps the audit trail intact while giving the embedding step the cleanest possible input.

### Chunking Strategy: Markdown-Aware Recursive Splitting

A naive fixed-size chunk (e.g. every 512 chars with overlap) ignores document structure and can split sentences or context sections. Instead, the chunker uses a hierarchy of separators to respect markdown structure:

1. **Headings first** — split at `#` / `##`, prepending each heading to chunks from its section. This ensures every retrieved chunk carries its source heading as context, a critical signal for document-grounded retrieval.

2. **Paragraph breaks next** — only split at sentence boundaries or word spaces if a paragraph is still too large. This keeps semantic units intact.

3. **Overlap for continuity** — a 64-char tail from each chunk is prepended to the next (word-aligned). Any sentence that spans a chunk boundary appears in both, improving recall.

This approach produces 494 total chunks (210 + 236 + 48) with sizes clustering around the target (512 chars → ~85–100 words), well within the 256-token all-MiniLM-L6-v2 context window while maximizing semantic coherence.

## 📄 License

MIT License — feel free to fork and adapt for your own domain.

---

## 🙏 Acknowledgements

Source material provided by Cornell University (CEA) and the University of Hawai'i at Mānoa (CTAHR). This project is for educational purposes and is not affiliated with any of these institutions.