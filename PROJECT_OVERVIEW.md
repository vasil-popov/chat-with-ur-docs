# Project Overview: Life OS — Chat with Your Docs

A personal AI assistant that combines document Q&A, expense tracking, and fitness logging in a single conversational interface. Users interact via a React Native mobile app backed by a LangGraph multi-agent system, with a dedicated MCP server handling structured data persistence.

This codebase also serves as the experimental base for a thesis comparing two agent **architectures** over the same tools and LLM: a **supervisor** multi-agent system and a single **monolithic ReAct** agent. Both arms are compiled at startup and selectable per request; a headless benchmark harness (`backend/app/evaluation/`) evaluates them against a frozen golden dataset. See [§4 Evaluation & Benchmark Harness](#4-evaluation--benchmark-harness-thesis).

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────┐
│             React Native App (Expo)                 │
│  Chat · Files · Expenses · Exercises · Dark Mode    │
└────────────────────┬────────────────────────────────┘
                     │  HTTP/SSE  (192.168.1.28:8069)
┌────────────────────▼────────────────────────────────┐
│           FastAPI Backend  /api/*                   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │         LangGraph Supervisor Agent           │   │
│  │  Routes to: Tracking · RAG · General        │   │
│  └────┬────────────────┬───────────────────┬───┘   │
│       │                │                   │        │
│  ┌────▼───┐      ┌─────▼────┐      ┌──────▼──┐    │
│  │Tracking│      │  RAG     │      │ General │    │
│  │ Agent  │      │ Agent    │      │  Agent  │    │
│  └────┬───┘      └─────┬────┘      └─────────┘    │
│       │                │                            │
│       │HTTP      ┌─────▼────────┐                  │
│       │          │  PGVector    │                  │
│       │          │  (pgvector)  │                  │
│       │          └──────────────┘                  │
└───────┼─────────────────────────────────────────────┘
        │  MCP / SSE  (localhost:8000/mcp)
┌───────▼─────────────────────────────────────────────┐
│           FastMCP Server  (Life_OS_Tools)           │
│  Expenses · Exercises CRUD → PostgreSQL             │
└─────────────────────────────────────────────────────┘
                     │
              ┌──────▼──────┐
              │  PostgreSQL  │
              │  + pgvector  │
              └─────────────┘
```

---

## 1. React Native Frontend

**Stack:** React Native 0.81.5 · Expo SDK 54 · Expo Router 6 · TypeScript

### Navigation

Drawer navigation with four screens (defined in `frontend/app/_layout.tsx`):

| Screen | Route | Purpose |
|--------|-------|---------|
| Chat | `/` (index) | Main conversational interface |
| Files | `/files` | Upload and manage documents |
| Expenses | `/expenses` | View and manage financial expenses |
| Exercises | `/exercises` | View and manage workout sessions |

A dark/light theme toggle lives in the drawer footer and propagates via `ThemeContext` (`frontend/src/theme.tsx`).

### Screens

**Chat (`frontend/app/index.tsx`)**
- Scrollable message thread with user bubbles (purple, right) and AI bubbles (light card, left)
- AI responses render Markdown (bold, italic, code blocks, lists) via `react-native-markdown-display`
- File attachment via camera, photo library, or document picker (PDF, TXT, XLS/XLSX)
- Streaming response display — progress shown in real time via SSE (`XMLHttpRequest`)
- Active tool calls shown as a loading hint while the agent is working
- `FileContextBar` component shows attached files with per-file remove controls
- `ReceiptProposalCard` appears inline when the backend detects a receipt, letting users confirm and bulk-log expenses in one tap

**Files (`frontend/app/files.tsx`)**
- Horizontal category filter chips: All / General / Receipt / Document / Spreadsheet / Image
- Cards expand to reveal extracted text preview (max 1500 chars) and actions
- Status badges: Processing (gray) · Ready (green) · Error (red)
- "Ask about this file" navigates to Chat with the file pre-attached
- Upload and delete with confirmation dialogs

**Expenses (`frontend/app/expenses.tsx`)**
- Date-range filter with total spend and transaction count summary bar
- Add / Edit / Delete expenses via form sheet (bottom panel)
- Category color indicator on each card
- Amounts displayed in EUR

**Exercises (`frontend/app/exercises.tsx`)**
- Collapsible workout session cards; each session groups its exercise logs
- Form supports both strength fields (sets, reps, weight kg) and cardio fields (duration min, distance km)
- Date-range filter with sessions count and total exercises summary

### Components

| Component | File | Purpose |
|-----------|------|---------|
| `FileContextBar` | `frontend/src/components/FileContextBar.tsx` | Horizontal strip of attached file chips with remove/clear-all |
| `ReceiptProposalCard` | `frontend/src/components/ReceiptProposalCard.tsx` | Detected receipt items with bulk-confirm to create expenses |

### Backend Communication

- **Base URL:** `http://192.168.1.28:8069`
- **Chat:** `POST /api/chat/stream` — SSE stream; events: `tool`, `done`, `error`; 120 s timeout
- **Files:** `POST /api/files/upload` (multipart), `GET /api/files`, `DELETE /api/files/{id}`
- **Expenses:** full CRUD on `/api/expenses`, bulk creation via `/api/expenses/bulk`
- **Exercises:** `GET/POST /api/exercises`, `DELETE /api/exercises/{id}`
- State management: plain React `useState` per screen — no global store

### Key Libraries

| Library | Version | Role |
|---------|---------|------|
| `expo-router` | ~6.0.23 | File-based routing |
| `@react-navigation/drawer` | ^7.10.2 | Drawer navigation |
| `expo-image-picker` | ~17.0.11 | Camera & photo library access |
| `expo-document-picker` | ~14.0.8 | File browser |
| `react-native-markdown-display` | ^7.0.2 | Markdown in chat |
| `@expo/vector-icons` | ^15.0.3 | Ionicons throughout the app |

---

## 2. FastAPI + LangGraph Backend

**Stack:** FastAPI 0.129.0 · LangGraph · LangChain · Google Gemini · SQLModel · PGVector

### Entry Point & Startup (`backend/app/main.py`)

The app uses an async lifespan context manager that, in order:
1. Creates all SQLModel tables
2. Initialises the PGVector vectorstore
3. Connects the MCP server client
4. Creates the Google Generative AI LLM client
5. Compiles **both** agent arms — the LangGraph supervisor graph and the monolithic ReAct agent — and registers each under its arch name in the DI container's agent registry

Both arms are built from the **same** LLM instance and the **same** tool objects (MCP tools + RAG tools); architecture is the only variable that differs, keeping the thesis comparison fair.

CORS is open (`allow_origins=["*"]`). A `GET /healthz` endpoint is available.

### API Routes (`backend/app/api/`)

| Domain | Method | Path | Description |
|--------|--------|------|-------------|
| Chat | POST | `/api/chat/stream` | SSE streaming response |
| Chat | POST | `/api/chat` | Standard (non-streaming) response |
| Files | POST | `/api/files/upload` | Upload file (5 MB max) |
| Files | GET | `/api/files` | List files (optional `?category=`) |
| Files | GET | `/api/files/{file_id}` | Get file + extracted text |
| Files | DELETE | `/api/files/{file_id}` | Delete file and its embeddings |
| Expenses | GET | `/api/expenses` | List (date range + category filter) |
| Expenses | POST | `/api/expenses` | Create expense |
| Expenses | POST | `/api/expenses/bulk` | Bulk create from receipt |
| Expenses | PUT | `/api/expenses/{id}` | Update expense |
| Expenses | DELETE | `/api/expenses/{id}` | Delete expense |
| Exercises | GET | `/api/exercises` | List workout sessions (date range) |
| Exercises | POST | `/api/exercises` | Log exercise |
| Exercises | DELETE | `/api/exercises/{id}` | Delete exercise log |

### Agent Architectures (`backend/app/services/agents.py`)

The backend ships **two interchangeable agent arms**, both compiled at startup and built by the same module. They are drop-in compatible with `chat_service` (both support `astream_events` / `ainvoke`).

**Arm A — Supervisor (`build_graph`)** — a LangGraph `StateGraph` whose router LLM dispatches each turn to one of three specialist agents:

```
User message
    └──> Supervisor (Gemini Flash 3, structured output RouteDecision)
              ├── "tracking" ──> Tracking Agent  (MCP tools: expenses + fitness)
              ├── "rag"      ──> RAG Agent       (PGVector document search)
              ├── "general"  ──> General Agent   (tool-less, knowledge Q&A)
              └── "FINISH"   ──> Return response
```

- Router uses `llm.with_structured_output(RouteDecision)`; the supervisor node forwards the `RunnableConfig` so callbacks (e.g. the metrics handler) propagate into the router and specialist calls.
- Each specialist node receives only the **last human message** (general also gets the last 6 messages, cleaned of orphaned tool calls), runs its own ReAct loop, and returns to the supervisor with only its final `AIMessage` appended.

**Arm B — Monolithic ReAct (`build_monolithic_agent`)** — a single `create_react_agent` given the **union of every tool** (MCP + RAG) and one merged system prompt covering all three capability areas. No router, no inter-agent hops.

- **LLM (both arms):** `ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=0)`
- **Agent style:** `create_react_agent()` (ReAct loop)
- **Date injection:** both builders accept an injectable `today` (defaults to `date.today()`); the benchmark pins it to the dataset's `reference_date` for deterministic relative-date reasoning
- **Context window:** last 6 messages passed to the supervisor router; intermediate tool calls stripped before passing to the next agent
- **Max recursion depth:** `recursion_limit=8` in production (`chat_service`); the benchmark applies `recursion_limit=15` identically to both arms
- **Streaming:** `agent.astream_events()` (v2), emitting `data:` JSON lines for tool starts and the final terminal answer (an `AIMessage` with no `tool_calls`)

**Arm selection:** `ChatRequest.arch` (`"supervisor"` | `"monolithic"`, default `"supervisor"`) chooses the arm per request. The chat routes resolve it via `di_container_instance.get_agent(req.arch)`, which **fails loud** on an unknown arch rather than silently falling back (silent fallback would contaminate the architecture comparison).

### RAG Pipeline (`backend/app/services/embedding_service.py`)

| Setting | Value |
|---------|-------|
| Vector store | PGVector (PostgreSQL + pgvector extension) |
| Embedding model | `GoogleGenerativeAIEmbeddings(model="gemini-embedding-2")` |
| Collection | `life_os_docs` |
| Chunking | `RecursiveCharacterTextSplitter` — 1000 chars, 150 overlap |
| Retrieval | Similarity search, K=5, optional `file_ids` metadata filter |

**RAG tools** (used by the RAG agent):
- `search_documents` — semantic similarity query
- `list_uploaded_files` — enumerate available documents
- `get_file_summary` — retrieve file metadata and text

### Document Processing (`backend/app/services/`)

Supported types: PNG, JPEG, WebP, GIF · PDF · TXT · Excel (xlsx/xls)

| File Type | Extraction Method |
|-----------|-------------------|
| Images | LLM OCR (base64 encoded) |
| PDFs | PyMuPDF; fallback to LLM OCR for scanned PDFs |
| TXT | Direct UTF-8 read |
| Excel | openpyxl — sheets rendered as Markdown tables |

**Receipt detection** (`file_service.py`): keyword matching (EN + BG) + price regex; threshold = 2+ keywords + price pattern → `is_receipt = True`.

**Receipt parsing** (`extraction.py`): LLM extracts a JSON array of line items (description, amount, category, date) from receipt text.

**File status lifecycle:** `processing` → `ready` / `error`

### Database (`backend/app/db/`, `backend/app/services/`)

ORM: **SQLModel** (SQLAlchemy + Pydantic). UUID primary keys throughout.

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `expenses` | Financial transactions | amount, category, description, transaction_date |
| `workout_sessions` | Groups exercise logs | session_name, workout_date |
| `exercise_logs` | Individual exercises | session_id (FK), exercise_name, category, duration_min, sets, reps, weight_kg, distance_km |
| `uploaded_files` | Document metadata | original_name, file_path, file_type, category, size_bytes, status, extracted_text, is_receipt |

### Dependency Injection (`backend/app/deps/`)

A singleton `DIContainer` is initialised at startup and stores:
- LLM client (Gemini)
- MCP client (connected to `http://localhost:8000/mcp`)
- Embeddings client
- An **agent registry** — compiled graphs keyed by arch name (`"supervisor"`, `"monolithic"`). `register_agent(name, graph)` populates it; `get_agent(arch)` retrieves one (`DEFAULT_ARCH = "supervisor"`) and raises `ValueError` for an unregistered arch.

### Key Dependencies

| Package | Role |
|---------|------|
| `fastapi` 0.129.0 | HTTP framework |
| `langgraph` | Multi-agent state graph |
| `langchain-google-genai` | Gemini LLM + embeddings |
| `langchain-mcp-adapters` | Bridge from LangChain to MCP tools |
| `langchain-community` | PGVector integration, text splitters |
| `sqlmodel` 0.0.37 | ORM |
| `psycopg2-binary` | PostgreSQL driver |
| `pgvector` 0.4.2 | Vector column type |
| `PyMuPDF` | PDF text extraction |
| `openpyxl` | Excel parsing |

### Configuration

Environment variables (read from parent `.env`):

```
POSTGRE_USER · POSTGRE_PASS · POSTGRE_IP · POSTGRE_PORT · POSTGRE_DB_NAME
ENVIRONMENT  (local | staging | production)
GOOGLE_API_KEY                       # Gemini LLM + embeddings
```

**Pricing (thesis cost accounting)** — Gemini token prices per 1,000 tokens, surfaced on `Settings` and overridable via env:

```
PRICE_IN_PER_1K   (default 0.0005)   # input tokens
PRICE_OUT_PER_1K  (default 0.003)    # output tokens
```

**Evaluation database (benchmark only)** — a SEPARATE `EVAL_POSTGRE_*` family that the eval seeder uses; the DB **name must contain `"eval"`** or the seeder refuses to touch it (see §4):

```
EVAL_POSTGRE_USER · EVAL_POSTGRE_PASS · EVAL_POSTGRE_IP · EVAL_POSTGRE_PORT · EVAL_POSTGRE_DB_NAME
```

---

## 3. MCP Server (Life_OS_Tools)

**Stack:** FastMCP · SQLModel · PostgreSQL

**Location:** `mcp_server/`  
**Transport:** HTTP/SSE — served at `http://localhost:8000/mcp`  
**Start command:** `fastmcp run main.py`

The MCP server is a standalone service that owns the expense and exercise data layer. The backend's Tracking Agent uses it as its tool source via `MultiServerMCPClient` from `langchain-mcp-adapters`.

### Exposed Tools

**Expense Tools**

| Tool | Description |
|------|-------------|
| `log_expense` | Create a new expense (amount, category, description, date) |
| `get_expenses` | Query expenses by date range and optional category |
| `delete_expense` | Remove expense by UUID |
| `get_spending_summary` | Aggregate spend totals grouped by category for a date range |

**Exercise/Fitness Tools**

| Tool | Description |
|------|-------------|
| `log_exercise` | Log a movement within a named session (with optional sets/reps/weight/duration/distance) |
| `get_workouts` | Retrieve sessions and their exercises by date range |
| `delete_exercise` | Remove an exercise log by UUID |
| `get_workout_summary` | Aggregate totals (duration, distance) for a date range |

### Database

Uses the **same PostgreSQL instance** as the backend but connects independently via its own SQLModel engine:

```
postgresql://{POSTGRE_USER}:{POSTGRE_PASS}@{POSTGRE_IP}:{POSTGRE_PORT}/{POSTGRE_DB_NAME}
```

Tables are created on startup via `init_db()`. Schema mirrors the backend's `workout_sessions` and `exercise_logs` tables.

### Configuration

```
POSTGRE_USER=mcp-app
POSTGRE_PASS=mcp-app-pass
POSTGRE_IP=localhost
POSTGRE_PORT=5432
POSTGRE_DB_NAME=life-tracker
```

### Key Dependencies

| Package | Role |
|---------|------|
| `fastmcp` | MCP server framework (wraps official `mcp` SDK) |
| `sqlmodel` | ORM for expenses and exercises |
| `psycopg2-binary` | PostgreSQL driver |

---

## 4. Evaluation & Benchmark Harness (Thesis)

**Location:** `backend/app/evaluation/`
**Stack:** Pydantic v2 · SQLModel · LangChain callbacks · pytest · matplotlib · SciPy · python-docx

The evaluation layer runs the same golden dataset through **both architecture arms** (supervisor vs. monolithic), captures per-run efficiency and correctness metrics, optionally grades answer quality with an LLM judge, and renders a thesis-ready report. The research question it answers: *how does the management architecture affect tool-selection accuracy, argument-extraction correctness, and task-execution efficiency?*

### Pipeline at a Glance

```
scenarios.yaml ──load+validate──> Dataset (loader.py)
        │
   for each (scenario × arch × repeat):
        │  seed eval DB (seed.py) ──> index RAG files (embedding_service)
        │  run agent with metrics (callbacks.run_with_metrics)
        │  rule-based score (scorer.py)  ◀── PRIMARY evaluator
        │  append one JSONL row (metrics.append_run_metrics)
        │  teardown eval DB
        ▼
   results/runs.jsonl
        │  optional --judge
        ▼
   judge.py (LLM-as-judge) ◀── SUPPLEMENTARY ──> results/runs_judged.jsonl
        │                                        + blind manual_scoring.csv (+ key.csv)
        ▼
   analyze_results.py ──> results/analysis/{thesis_results.docx, figures/, *.csv}
```

### Golden Dataset (`dataset/`)

- **`scenarios.yaml`** — 26 annotated scenarios across 5 categories: tracking (6), rag (5), multi_domain (5), ambiguous (5), general (5). Each scenario carries `setup` rows to seed, the user `message` (+ optional `history`), and an `expected` block that is **ground truth**.
- **`loader.py`** — Pydantic v2 models (`Scenario`, `ExpectedOutcome`, `ToolCall`, `Dataset`, seed sub-models) plus a strict, fail-fast YAML loader. Validates: unique ids, every tool name ∈ the real MCP + RAG tool inventory (`KNOWN_TOOLS`), `clarification/confirmation ⇒ no_write_expected`, and general scenarios route to `general` with no tool calls.
- **`DATE ANCHOR`** — all relative dates are pre-resolved against a fixed `reference_date` (`2026-06-03`, a Wednesday); the loader does no date arithmetic.
- **`dataset/docs/`** — sample document text (`gym_membership.txt`, `nutrition_guidelines.txt`) backing the RAG scenarios.

### Eval Database Seeding (`dataset/seed.py`) — safety-critical

- Builds a **separate** SQLModel engine from the `EVAL_POSTGRE_*` vars; never reuses or falls back to the production engine.
- **Hard guard:** `_assert_eval_database` refuses any DB whose name lacks the substring `"eval"`, raising `RuntimeError` before any write or teardown — the single line of defence against wiping production.
- `seed_scenario` inserts expenses/workouts/files and returns `SeededIds` (UUIDs keyed by each row's `ref` handle); `teardown` deletes all eval rows in FK-safe order before and after every run.
- ⚠️ **MCP caveat:** tool writes (`log_expense`, `delete_*`, …) flow through the MCP server, which reads its **own** `POSTGRE_*` vars. The MCP server process must be pointed at the **same** eval DB, or the agent's writes hit production while the seeder cleans eval, and `db_delta` will be wrong.

### Metrics Capture (`callbacks.py`, `metrics.py`)

- **`MetricsCallbackHandler`** (one per run, stateful) — a LangChain `AsyncCallbackHandler` that counts LLM calls (chat + the supervisor router's structured-output call), sums token usage defensively across provider field-name variants, records ordered `(tool_name, args)` pairs, approximates graph super-steps (`hops`) and the ordered `nodes_visited` (excluding plumbing nodes), and times TTFT.
- **`run_with_metrics`** — invokes the graph once, merges the handler into a config copy (preserving the caller's `recursion_limit`), and captures a `GraphRecursionError` as **data** (`non_termination=True`) rather than propagating it, so a runaway router loop still counts with its partial metrics.
- **`RunMetrics`** — framework-agnostic value object (latency, TTFT, LLM/tool counts, tokens, est. cost, hops, nodes, non-termination); `compute_cost` applies the `PRICE_*` settings; `append_run_metrics` writes one JSON line per run (append-only, sequential).

### Rule-Based Scorer (`scorer.py`) — PRIMARY evaluator

A **pure** module (no I/O, no LLM, no DB) that compares an annotated `Scenario` against observed tool calls / visited nodes / final answer / DB delta and returns a `ScoreResult`. `task_success` is the AND of every *applicable* (non-`None`) check; `None` always means "not applicable", never "failed". Checks include:

| Check | Meaning |
|-------|---------|
| `route_correct` | Supervisor arm only — first specialist node entered matches the expected route (`None` for monolithic). |
| `tool_selection_correct` | **Lenient subset** check: all expected tools were called; harmless extra *reads* tolerated. |
| `args_extraction_ratio` / `_correct` | Per-parameter ground-truth arg match (numeric tolerance + case-folded strings); ratio + all-correct flag. |
| `wrong_tool_called` | Flags only a forbidden tool or an **unexpected write/destructive** tool. |
| `hallucination_free` | Conservative: write/destructive tool ran or DB mutated despite `no_write_expected`. |
| `clarification_correct` / `unsafe_action_avoided` | Ambiguous scenarios: asked-a-question-without-writing / no destructive call before confirmation. |
| `db_effect_correct` | Observed `db_delta` matches the annotated `*_added` / `*_unchanged` effect. |

### LLM-as-Judge (`judge.py`) — SUPPLEMENTARY

A secondary signal that **never** influences `task_success`. Blind-grades each final answer (1–5 on correctness, completeness, relevance, conciseness + a hallucination flag) against the reference answer + rubric points. Two layers of blindness: the grading prompt never sees the architecture, and the exported `manual_scoring.csv` is shuffled (fixed seed `1337`) with opaque `anon_id`s — architecture lives only in the separate `manual_scoring_key.csv`. Judge output is written under a `"quality"` key in `runs_judged.jsonl`; failures are non-fatal.

### Benchmark Runner (`run_benchmark.py`)

Headless entry point that sweeps every `(scenario, arch, repeat)`, resolving `<ref:NAME>` placeholders to real seeded UUIDs and tearing the DB down around each run. Pins agents' `today` to `reference_date` for reproducibility.

```bash
# from backend/, with venv active, MCP server running, and EVAL_POSTGRE_* + GOOGLE_API_KEY set
python -m app.evaluation.run_benchmark --arch both --repeats 5
python -m app.evaluation.run_benchmark --arch supervisor --limit 3 --repeats 1
python -m app.evaluation.run_benchmark --arch both --repeats 5 --judge   # also run the judge
```

Flags: `--arch {supervisor,monolithic,both}` · `--repeats N` · `--dataset` · `--out` · `--limit N` (smoke runs) · `--resume` (skip already-scored rows) · `--judge` / `--no-judge` (default off).

### Analysis & Reporting (`analyze_results.py`)

Reads the frozen `results/runs_judged.jsonl` and renders `results/analysis/thesis_results.docx` (native tables + embedded figures) plus CSV backups. The design is **paired** (every scenario runs under both arms): continuous efficiency metrics use the **Wilcoxon signed-rank** test on per-scenario means; binary accuracy axes use **McNemar's exact** test on paired `(scenario, repeat)` outcomes. Produces grouped-bar / box-plot figures and a research-question narrative.

```bash
backend/venv/Scripts/python.exe app/evaluation/analyze_results.py
```

### Tests (`evaluation/tests/`)

pytest unit tests covering the offline-testable modules: `test_callbacks.py`, `test_dataset.py`, `test_judge.py`, `test_metrics.py`, `test_scorer.py`.

### Results Artifacts (`evaluation/results/`)

`runs.jsonl` (raw scored runs) · `runs_judged.jsonl` (judge-enriched) · `manual_scoring.csv` + `manual_scoring_key.csv` (blind human-rater pair) · `run.log` · `analysis/` (Word report, `figures/`, CSVs).

> **Note on dependencies:** `backend/requirements.txt` covers the *running app* only. The evaluation layer additionally needs `pyyaml`, `pytest`, `matplotlib`, `scipy`, and `python-docx`, which are installed in the backend venv but not pinned in `requirements.txt`.

---

## Data Flow: End-to-End Chat Request

```
1. User types "Log €12 pizza for dinner" and taps Send
2. App POSTs to /api/chat/stream  { message, file_ids: [] }
3. Backend passes message to LangGraph supervisor
4. Supervisor (Gemini) → routes to "tracking" agent
5. Tracking Agent calls MCP tool: log_expense(12, "Food", "pizza", today)
6. MCP server persists expense to PostgreSQL → returns confirmation
7. Tracking Agent formats reply: "Logged €12 for pizza under Food ✓"
8. Backend streams SSE event: { type:"done", content:"Logged..." }
9. App renders message bubble with response
```

```
1. User uploads a PDF contract and asks "What is the termination clause?"
2. App uploads PDF → backend extracts text, chunks and embeds to PGVector
3. User sends question with file_id attached
4. Supervisor routes to "rag" agent
5. RAG agent calls search_documents("termination clause", file_ids=[...])
6. PGVector returns top-5 relevant chunks
7. RAG agent synthesises answer, cites source document
8. App renders formatted Markdown response
```

---

## Project Structure

```
chat-with-ur-docs/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, lifespan, startup
│   │   ├── config.py                # Pydantic Settings (env vars)
│   │   ├── exceptions.py            # Custom HTTP exceptions
│   │   ├── api/
│   │   │   ├── router.py            # Route aggregator
│   │   │   ├── routes/              # chat, files, expenses, exercises
│   │   │   └── schemas/             # Pydantic request/response models
│   │   ├── db/
│   │   │   └── database.py          # Engine, session factory
│   │   ├── deps/
│   │   │   ├── dependency_container.py   # Singleton DI container
│   │   │   └── dependency_factory.py     # Builds LLM, MCP, agent at startup
│   │   ├── services/
│   │   │   ├── agents.py            # build_graph (supervisor) + build_monolithic_agent
│   │   │   ├── chat_service.py      # Request orchestration, file augmentation, SSE
│   │   │   ├── embedding_service.py # PGVector init, chunk + embed, retrieval
│   │   │   ├── extraction.py        # Per-type text extraction, receipt parsing
│   │   │   ├── file_service.py      # Upload, store, process, delete files
│   │   │   ├── expense_service.py   # Expense CRUD (SQLModel)
│   │   │   └── exercise_service.py  # Exercise/session CRUD (SQLModel)
│   │   ├── tools/
│   │   │   └── rag_tools.py         # LangChain Tool wrappers for document search
│   │   └── evaluation/              # Thesis benchmark harness (§4)
│   │       ├── run_benchmark.py     # Headless sweep: scenario × arch × repeat
│   │       ├── callbacks.py         # MetricsCallbackHandler, run_with_metrics
│   │       ├── metrics.py           # RunMetrics, compute_cost, JSONL persistence
│   │       ├── scorer.py            # Rule-based PRIMARY scorer (pure)
│   │       ├── judge.py             # LLM-as-judge (SUPPLEMENTARY, blind)
│   │       ├── analyze_results.py   # Stats + figures + thesis_results.docx
│   │       ├── dataset/
│   │       │   ├── loader.py        # Pydantic models + strict YAML loader
│   │       │   ├── seed.py          # Eval DB seed/teardown (eval-name guard)
│   │       │   ├── scenarios.yaml   # 26 annotated golden scenarios
│   │       │   └── docs/            # Sample RAG documents
│   │       ├── tests/               # pytest unit tests
│   │       └── results/             # runs.jsonl, runs_judged.jsonl, analysis/
│   └── uploads/                     # Uploaded file storage
├── mcp_server/
│   ├── main.py                      # FastMCP server entry point
│   ├── database.py                  # SQLModel schema + engine
│   ├── expenses/
│   │   └── tools.py                 # Expense MCP tool definitions
│   └── exercises/
│       └── tools.py                 # Exercise MCP tool definitions
└── frontend/
    ├── app/
    │   ├── _layout.tsx              # Drawer navigation root
    │   ├── index.tsx                # Chat screen
    │   ├── files.tsx                # File management screen
    │   ├── expenses.tsx             # Expense tracking screen
    │   └── exercises.tsx            # Exercise logging screen
    └── src/
        ├── api.tsx                  # API client (fetch + SSE)
        ├── theme.tsx                # Light/dark theme context
        └── components/
            ├── FileContextBar.tsx   # Attached files strip
            └── ReceiptProposalCard.tsx  # Receipt confirm-and-log card
```
