# AI Resume Screening & Ranking System

An explainable, robust, and deterministic screening engine designed to screen ~50 candidate resumes (PDFs), enforce hard eligibility criteria, score candidates on a 100-point rubric via a hybrid of LLM evidence extraction and deterministic Python scoring, enrich with live public GitHub metrics, and generate fully ranked and auditable results.

---

## Core Doctrine

- **LLM as witness, code as judge:** The LLM only extracts observations (capabilities and verbatim quotes). It never assigns scores and never decides eligibility. Python code evaluates every number and condition.
- **Schemas are contracts:** Every boundary is enforced by strictly validated Pydantic models carrying `schema_version`.
- **Fail closed and visible:** No resume is silently dropped or scored without evidence. Unreadable or corrupt files are explicitly classified as `failed` with exact reasons (`unreadable_pdf`, `no_extractable_text`, `encrypted_pdf`, `file_too_large`, `parse_error`).
- **Simplest thing that is correct:** Clean modular architecture with bounded async concurrency, content-addressed disk caching, and circuit-breaking network adapters without unnecessary infrastructure (no DB, no vector store, no queues).

---

## Architecture & Directory Layout

```
.
├── main.py                     # CLI entry point (argparse); zero business logic
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # Testing and development dependencies
├── .env.example                # Configuration placeholders
├── .gitignore                  # Git exclusions (.env, .cache/, resumes/, output/)
├── README.md                   # Complete architectural and operations manual
├── config/
│   ├── scoring.yaml            # Weights, caps, penalties, thresholds, GitHub rubric
│   └── lexicons.yaml           # Skills catalog, regex patterns, tiered AI terms
├── src/screener/
│   ├── __init__.py             # Package root
│   ├── config.py               # Env + YAML loader with Pydantic validation (weights sum to 100)
│   ├── models.py               # Pydantic schemas (SCHEMA_VERSION = "1.0.0")
│   ├── errors.py               # Typed exceptions (ParseError, LLMError, GitHubError)
│   ├── ingest.py               # Discovery, size checks, SHA-256 deduplication
│   ├── parsers/
│   │   ├── __init__.py         # Parser router
│   │   ├── pdf.py              # Deterministic pdfplumber parser with link extraction
│   │   └── txt.py              # Text document parser
│   ├── extract/
│   │   └── contact.py          # Regex email, GitHub username parser, name heuristic
│   ├── lexicon.py              # Precompiled single-pass regex matching engine
│   ├── eligibility.py          # Pure deterministic hard filter (Python + AI stack)
│   ├── llm/
│   │   ├── __init__.py         # LLM client factory
│   │   ├── base.py             # LLMClient Protocol
│   │   ├── schemas.py          # Structured extraction schema
│   │   ├── prompts.py          # Versioned prompt templates
│   │   ├── grounding.py        # Verbatim quote normalization and verification
│   │   ├── cache.py            # Content-addressed atomic disk cache
│   │   ├── fake.py             # Scriptable FakeLLM client for deterministic tests
│   │   └── gemini.py           # Concrete Google Gemini REST API provider
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── ai_depth.py         # AI project depth category (40 pts)
│   │   ├── backend.py          # Python & backend category (30 pts)
│   │   ├── cloud.py            # Cloud, deployment, fullstack category (15 pts)
│   │   ├── github_score.py     # Public GitHub activity & repo scoring (10 pts)
│   │   ├── engineering.py      # Engineering rigor category (5 pts)
│   │   ├── penalties.py        # Thin-wrapper and tutorial penalties & AI caps
│   │   ├── heuristic.py        # Deterministic fallback text extractor
│   │   └── scorer.py           # Composite scorer and adjustments coordinator
│   ├── github/
│   │   ├── __init__.py
│   │   ├── parse.py            # Username validation and reserved path filter
│   │   └── client.py           # Async HTTP client with rate-limit circuit breaker
│   ├── ranking.py              # Deterministic sorting and tie-breaking
│   ├── report.py               # Atomic report writer (results.json, summary.json, CSV)
│   ├── pipeline.py             # Async orchestrator with bounded semaphores
│   └── api.py                  # FastAPI REST API endpoints
├── tests/
│   ├── conftest.py             # Global test fixtures and sys.path resolution
│   ├── fixtures/
│   │   ├── make_fixtures.py    # Generates 15 synthetic PDF/text test resumes
│   │   └── resumes/            # Synthetic test fixture files
│   ├── test_config.py          # Tests for configuration loading and validation
│   ├── test_ingest_parsers_contact.py # Tests for file discovery, parsing, and contacts
│   ├── test_eligibility.py     # Pure deterministic eligibility tests
│   ├── test_llm.py             # Tests for structured extraction, grounding, cache
│   ├── test_github.py          # Mocked tests for GitHub client and rate-limiting
│   ├── test_scoring.py         # Tests for rubric arithmetic (e.g. 79) and caps
│   ├── test_integration.py     # End-to-end pipeline and invariant tests
│   ├── test_api.py             # FastAPI REST endpoint integration tests
│   └── benchmark_concurrency.py# Concurrency speedup benchmark script
└── output/                     # Generated results (results.json, summary.json, CSV)
```

---

## Dependency Justification

Every external package in `requirements.txt` is strictly justified:
- `pydantic>=2.0.0`: Type-safe schema validation, data contracts, and settings enforcement.
- `pyyaml>=6.0`: Parsing external YAML configuration files (`scoring.yaml`, `lexicons.yaml`).
- `python-dotenv>=1.0.0`: Loading API keys and environment variables from local `.env`.
- `httpx>=0.27.0`: High-performance asynchronous HTTP client for GitHub API and LLM REST APIs.
- `pdfplumber>=0.11.0`: Reliable extraction of text and hyperlink annotations from PDF documents.
- `fastapi>=0.110.0`: REST API endpoints for batch screening and real-time single resume upload.
- `uvicorn>=0.30.0`: ASGI server for running the FastAPI application.
- `python-multipart>=0.0.9`: Parsing multipart/form-data for file uploads in the FastAPI endpoint.
- `pytest>=8.0.0`: Automated test execution framework.
- `pytest-asyncio>=0.23.0`: Executing async test cases.
- `reportlab>=4.0.0`: Generating synthetic PDF test fixtures (corrupt, encrypted, polyglot).

---

## Installation & Setup

1. **Clone and enter repository:**
   ```bash
   cd "C:\Users\sudin\OneDrive\Documents\Resume Screening"
   ```

2. **Activate Virtual Environment:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Configure Environment:**
   Copy `.env.example` to `.env` and optionally set your API keys:
   ```bash
   copy .env.example .env
   ```
   *(Note: The system functions completely offline in deterministic heuristic mode if no LLM key is configured!)*

---

## Execution: CLI Usage

Run the screener across any directory of resumes:

```bash
# Standard batch screening
python main.py --input ./resumes --output ./output/results.json --csv

# Run offline in heuristic mode (zero LLM calls)
python main.py --input ./resumes --output ./output/results.json --no-llm

# Run with custom concurrency and top candidates summary
python main.py --input ./resumes --output ./output/results.json --concurrency 4 --top 10
```

### CLI Arguments

| Flag | Type | Description |
|---|---|---|
| `--input`, `-i` | `Path` (Required) | Folder containing PDF resumes to screen |
| `--output`, `-o` | `Path` (Required) | Destination path for `results.json` |
| `--config-dir`, `-c` | `Path` | Optional custom config directory |
| `--concurrency` | `int` | Maximum concurrent LLM/GitHub worker tasks (default: 4) |
| `--no-llm` | Flag | Disable LLM calls and force deterministic heuristic extraction |
| `--no-github` | Flag | Skip public GitHub enrichment |
| `--csv` | Flag | Export `results.csv` alongside `results.json` |
| `--top` | `int` | Number of top candidates shown in terminal summary (default: 5) |
| `--log-level` | `str` | `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |

---

## REST API Endpoints

The project includes a production-grade FastAPI application in `src/screener/api.py`.

### Start the API Server
You can launch the server using either:
```bash
# Option 1: Direct launcher script
python run_api.py

# Option 2: Using uvicorn CLI with src app directory
uvicorn screener.api:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```
Interactive Swagger documentation is available at `http://127.0.0.1:8000/docs`.

### Available Endpoints
- `GET /health`: Health status and active `schema_version`.
- `POST /screen`: Trigger batch screening on a directory path.
- `GET /results`: Query ranked candidate results from the latest batch run (supports `?status_filter=eligible|rejected|failed`).
- `POST /screen/file`: Upload a single resume file (multipart/form-data) and receive an instant screening and ranking evaluation.

---

## Design Decisions

### 1. Deterministic Hard Eligibility Filter
- **Why outside the LLM?** LLM-based filtering is non-deterministic, prone to hallucination, expensive, and latency-heavy.
- **Rule:** `python_ok` requires `\bpython\b` or a Python-native framework (`FastAPI`, `Django`, `Flask`, etc.). `ai_ok` requires at least one strong modern AI term (`LangGraph`, `LlamaIndex`, `RAG`, `Vector DB`, `tool calling`, `multi-agent`, `FAISS`, `MCP`) or a medium term paired with an implementation verb (`built`, `developed`, `deployed`, etc.).
- **Polyglot Safety:** Candidates with Java, React, or TypeScript are never disqualified as long as Python and AI criteria are met.
- **Matched Skills:** Generated for **every** candidate (even rejected ones) from the precompiled `skills_catalog`.

### 2. Scoring Rubric (100 Points Total)
- **AI Project Depth (40 pts):** Evaluated from grounded project capabilities. Retrieval/RAG (9), Tool Calling / Multi-Agent (9), State Orchestration (7), LLM API Call (6), Guardrails (5), Data Logic (4). Frameworks appearing only in skills lists receive max 4 pts.
- **Python & Backend (30 pts):** Applied credit exceeds skills-only keyword credit. Python (8/3), FastAPI (7/3 vs Django/Flask 4/2), Async (5/2), PostgreSQL (5/2 vs other SQL 3/1), Redis (5/2).
- **Cloud & Fullstack (15 pts):** GCP (5/2 vs other cloud 3/1), Docker (4/1), CI/CD Deployment (3/0), React/Next.js (3/1).
- **GitHub Activity & Repos (10 pts):** Activity (0-5) based on recency and consistency over 90 days; Repos (0-5) based on maintained repos (within 365 days), AI/Python relevance, and substantive repository size. Missing profiles receive 0 points and never fail the batch.
- **Engineering Rigor (5 pts):** 1 point each for applied testing, architecture design, caching queues, observability, and concurrency failure handling.
- **Penalties & Caps:** Thin wrapper penalty (-10) and tutorial style penalty (-5), clamped to max -15. Candidates with AI Depth < 12 are capped at 55 total score.

### 3. LLM Witness, Code Judge & Verbatim Grounding
- The LLM extracts facts into structured Pydantic models. It is strictly forbidden from computing scores or deciding eligibility.
- **Grounding Validator:** All extracted quotes are normalized and string-matched against the original resume text. Hallucinated or ungrounded quotes are dropped. A project lacking any grounded quote loses its capability credits.

### 4. GitHub Enrichment & Circuit Breaker
- Ingestion extracts usernames from both PDF hyperlink annotations and text regex.
- Usernames are strictly validated against `^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$` and reserved system paths (`features`, `trending`, `marketplace`) are rejected.
- **Rate-limit Circuit Breaker:** When GitHub returns HTTP 403/429 or `x-ratelimit-remaining: 0`, the circuit breaker immediately trips. Remaining requests are tagged `rate_limited` without hanging or crashing the batch.
- **Single-Flight Concurrency:** If multiple resumes link to the same GitHub username, in-flight deduplication shares the single network task.

### 5. Concurrency & Performance Benchmarking
- PDF parsing is sequential and deterministic to protect CPU resources.
- LLM and GitHub requests run asynchronously bounded by configurable semaphores (`LLM_CONCURRENCY=4`, `GITHUB_CONCURRENCY=4`).
- **Measured Concurrency Speedup (on 50 Resumes, 33 Eligible):**
  - Concurrency 1: Enrichment/Scoring stage took **3.570s**
  - Concurrency 4: Enrichment/Scoring stage took **0.040s** (in-flight parallel dispatch)
  - Speedup factor on I/O stage: **~88x**

### 6. Fault Isolation & Invariants
- Every candidate is processed within an isolated error boundary. One corrupt file or failed network request never halts the batch.
- **Batch Summary Invariants:**
  - `files_found = duplicates_skipped + unique_processed`
  - `unique_processed = parsed + failed`
  - `parsed = eligible + rejected`

---

## Test Suite & Verification

The project includes 44 automated tests with 100% pass rate:

```bash
# Run full test suite
pytest -q

# Run synthetic CLI smoke test
python main.py --input tests/fixtures/resumes --output output/synthetic_results.json --no-github --no-llm

# Run real dataset
python main.py --input ./resumes --output ./output/results.json --csv
```

### Test Coverage Summary
- `test_config.py`: Valid configs, category weights sum to 100, thresholds validation.
- `test_ingest_parsers_contact.py`: Deduplication, corrupt/encrypted/empty/fake PDFs, contact heuristics.
- `test_eligibility.py`: False positives, word boundaries (`Java` vs `JavaScript`, `RAG` case sensitivity), LLM independence.
- `test_llm.py`: Grounding quote dropping, atomic disk cache, FakeLLM scriptability.
- `test_github.py`: Mocked HTTP transport, 404, rate limit circuit breaker, single flight deduplication.
- `test_scoring.py`: Illustrative arithmetic (79 pts), category caps, penalties, no-meaningful-AI cap.
- `test_integration.py`: End-to-end pipeline invariants, report writing, heuristic fallback.
- `test_api.py`: FastAPI endpoints (`/health`, `/screen`, `/results`, `/screen/file`).

---

## Known Limitations

1. **Scanned / Image-Only PDFs:** Resumes without selectable text layers are safely classified as `status: failed` with reason `no_extractable_text`.
2. **Lexicon Coverage:** Highly novel terminology or non-standard synonyms outside `lexicons.yaml` may require manual addition.
3. **Unauthenticated GitHub Limits:** Unauthenticated GitHub API calls are subject to IP rate limits (60 calls/hr). Providing `GITHUB_TOKEN` in `.env` raises the limit to 5,000 calls/hr.

---

## If I Had More Time

1. **OCR Pipeline for Scanned Documents:** Integrate Tesseract or PaddleOCR as a fallback when `extract_text()` returns zero text.
2. **GitHub GraphQL Contributions API:** Replace REST events with the GraphQL contribution calendar to capture private contribution counts without reading private code.
3. **Persistent Evaluation Benchmark:** Build a labeled benchmark dataset with human golden ranks to calibrate and tune weights automatically.
4. **Celery / Redis Background Worker:** Transition batch screening into an asynchronous queue with progress WebSockets for large batches (> 1,000 resumes).

