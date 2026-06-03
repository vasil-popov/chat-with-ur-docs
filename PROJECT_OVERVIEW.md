# Project Overview: Life OS — Chat with Your Docs

A personal AI assistant that combines document Q&A, expense tracking, and fitness logging in a single conversational interface. Users interact via a React Native mobile app backed by a LangGraph multi-agent system, with a dedicated MCP server handling structured data persistence.

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
5. Compiles the LangGraph supervisor agent

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

### Multi-Agent System (`backend/app/services/agents.py`)

A LangGraph **supervisor** routes each user turn to one of three specialist agents:

```
User message
    └──> Supervisor (Gemini Flash 3, structured output RouteDecision)
              ├── "tracking" ──> Tracking Agent  (MCP tools: expenses + fitness)
              ├── "rag"      ──> RAG Agent       (PGVector document search)
              ├── "general"  ──> General Agent   (tool-less, knowledge Q&A)
              └── "FINISH"   ──> Return response
```

- **LLM:** `ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=0)`
- **Agent style:** `create_react_agent()` (ReAct loop)
- **Context window:** last 6 messages passed to supervisor; intermediate tool calls stripped before passing to next agent
- **Max recursion depth:** 8 supervisor hops
- **Streaming:** `agent.astream_events()` (v2), emitting `data:` JSON lines for tool starts and final content

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
- Compiled LangGraph agent

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
│   │   │   ├── agents.py            # LangGraph supervisor + 3 agents
│   │   │   ├── chat_service.py      # Request orchestration, file augmentation
│   │   │   ├── embedding_service.py # PGVector init, chunk + embed, retrieval
│   │   │   ├── extraction.py        # Per-type text extraction, receipt parsing
│   │   │   ├── file_service.py      # Upload, store, process, delete files
│   │   │   ├── expense_service.py   # Expense CRUD (SQLModel)
│   │   │   └── exercise_service.py  # Exercise/session CRUD (SQLModel)
│   │   └── tools/
│   │       └── rag_tools.py         # LangChain Tool wrappers for document search
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
