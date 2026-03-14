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
hydroponic-rag-assistant/
│
├── data/
│   ├── raw/              # Original downloaded files — never modified
│   ├── processed/        # Cleaned text output from parsing scripts
│   └── chunks/           # Final chunked documents ready for embedding
│
├── scripts/
│   ├── ingestion/        # Download, parse, and clean source documents
│   ├── embedding/        # Embed chunks and ingest into ChromaDB
│   └── eval/             # Evaluation scripts and results logging
│
├── src/
│   ├── retriever.py      # ChromaDB retrieval logic
│   ├── generator.py      # LLM prompt construction and generation
│   └── pipeline.py       # End-to-end ask() function
│
├── eval/
│   ├── eval_set.json     # Hand-crafted Q&A evaluation dataset
│   ├── retrieval_results.json
│   ├── generation_results.json
│   └── results_log.md    # Scored baseline and iteration history
│
├── app/
│   └── main.py           # FastAPI application entry point
│
├── .env.example          # Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🔧 Tech Stack

| Layer | Tool |
|---|---|
| Embedding Model | `sentence-transformers` (all-MiniLM-L6-v2) |
| Vector Database | ChromaDB (local persistent) |
| LLM | OpenAI GPT-4o-mini |
| PDF Parsing | pdfplumber |
| API Framework | FastAPI |
| UI (optional) | Streamlit |

---

## 📚 Data Sources

All source material is freely available from reputable agricultural institutions:

- **USDA PLANTS Database** — bulk plant characteristics CSV (plants.usda.gov)
- **Cornell CEA (Controlled Environment Agriculture)** — hydroponic production guides
- **Penn State Extension** — nutrient deficiency and pest management guides
- **UC Davis Extension** — vegetable crop and nutrient management PDFs
- **FAO (UN Food and Agriculture Organization)** — open crop production manuals

---

## 🔄 The 7-Step Engineering Loop

This project was built following a deliberate AI engineering methodology:

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
git clone https://github.com/nilomadison
/hydroponic-rag-assistant.git
cd hydroponic-rag-assistant
pip install -r requirements.txt
```

### Environment Setup

```bash
cp .env.example .env
# Add your OpenAI API key to .env
```

### Ingest Documents

```bash
python scripts/ingestion/parse_pdfs.py
python scripts/embedding/ingest_chunks.py
```

### Run the Pipeline

```python
from src.pipeline import ask

result = ask("What is the ideal pH range for hydroponic lettuce?")
print(result["answer"])
print("Sources:", result["sources"])
```

### Start the API

```bash
uvicorn app.main:app --reload
```

---

## 📊 Evaluation

The project includes a structured evaluation framework with two layers:

**Retrieval Evaluation** — measures whether the correct source document appears in the top retrieved chunks for each eval question. Target: >80% hit rate.

**Generation Evaluation** — measures answer correctness and plain-language quality against a hand-crafted ground truth dataset. Scored 0–2 per question.

Results are logged in `eval/results_log.md` with each iteration tracked against the baseline.

---

## 🗺️ Roadmap

- [x] Problem framing and scope definition
- [x] Data source identification
- [x] PDF ingestion and cleaning pipeline
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

*This section will be updated as the project progresses with key lessons from each stage of the engineering loop.*

---

## 📄 License

MIT License — feel free to fork and adapt for your own domain.

---

## 🙏 Acknowledgements

Source material provided by USDA, Cornell University, Penn State Extension, UC Davis, and the FAO. This project is for educational purposes and is not affiliated with any of these institutions.