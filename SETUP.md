# Setup Guide — Life OS: Chat with Your Docs

This guide gets the project running locally from a clean checkout. It has four
parts that you start in order:

1. **PostgreSQL** (with the `pgvector` extension) — shared data store
2. **MCP server** — expense/exercise tools (`localhost:8000`)
3. **Backend** — FastAPI + LangGraph agents (`0.0.0.0:8069`)
4. **Frontend** — Expo / React Native app

> See `PROJECT_OVERVIEW.md` for the full architecture. This file is just the
> "how do I run it" version.

---

## Prerequisites

| Tool | Version used | Notes |
|------|--------------|-------|
| Python | 3.14 | `py` launcher on Windows |
| Node.js | 26.x | for the Expo frontend |
| PostgreSQL | 14+ | must support the `pgvector` extension |
| Google AI API key | — | Gemini LLM + embeddings (`GOOGLE_API_KEY`) |

You also need a phone with **Expo Go** (or an Android/iOS emulator) to run the
app.

---

## 1. Database

The backend and the MCP server share **one** PostgreSQL instance. The backend
also needs the `pgvector` extension for RAG.

```sql
-- create the role and databases (run as a postgres superuser)
CREATE ROLE "mcp-app" LOGIN PASSWORD 'mcp-app-pass';

CREATE DATABASE "life-tracker"      OWNER "mcp-app";   -- production / app DB
CREATE DATABASE "life-tracker-eval" OWNER "mcp-app";   -- thesis benchmark DB

-- enable pgvector in each DB you'll use for RAG
\c life-tracker
CREATE EXTENSION IF NOT EXISTS vector;

\c life-tracker-eval
CREATE EXTENSION IF NOT EXISTS vector;
```

Tables are created automatically on startup (SQLModel `init_db()` / lifespan),
so you don't need to run any migrations.

> The DB whose name contains `eval` is reserved for the benchmark harness — the
> seeder refuses to touch any DB without `eval` in the name as a safety guard.

---

## 2. Environment variables

There are **three** `.env` files. The two service ones already exist in the
repo; the root one is for the evaluation harness.

| File | Used by | Purpose |
|------|---------|---------|
| `backend/.env` | backend | DB pointers, `GOOGLE_API_KEY`, pricing |
| `mcp_server/.env` | MCP server | DB pointers for the tools layer |
| `.env` (repo root) | benchmark harness | `EVAL_POSTGRE_*` + `GOOGLE_API_KEY` |

Minimum keys each service expects:

```dotenv
# backend/.env  and  mcp_server/.env
POSTGRE_USER=mcp-app
POSTGRE_PASS=mcp-app-pass
POSTGRE_IP=localhost
POSTGRE_PORT=5432
POSTGRE_DB_NAME=life-tracker      # mcp_server MUST match the backend DB

# backend/.env only
GOOGLE_API_KEY=your-gemini-key
```

> ⚠️ Point the **MCP server at the same DB as the backend**. The tracking agent
> writes through the MCP server, so a mismatch sends writes to the wrong
> database.

---

## 3. MCP server (start first)

The backend connects to the MCP server at startup, so launch this one first.

```powershell
cd mcp_server
py -m venv venv                      # first time only
.\venv\Scripts\activate              # first time only
pip install -r requirements.txt      # first time only

.\run.bat                            # starts: fastmcp run main.py
```

Serves the tools at **http://localhost:8000/mcp**.

> `run.bat` already exists and just runs `fastmcp run main.py`. The venv at
> `mcp_server/venv` is already created in this checkout — if it's missing, run
> the three first-time commands above.

---

## 4. Backend (FastAPI + LangGraph)

```powershell
cd backend
py -m venv venv                      # first time only
.\venv\Scripts\activate              # first time only
pip install -r requirements.txt      # first time only

.\run.bat                            # starts uvicorn on 0.0.0.0:8069
```

`run.bat` runs:

```bat
py -m uvicorn --env-file .env --host 0.0.0.0 --port 8069 app.main:app
```

Verify it's up: open **http://localhost:8069/healthz** — it should return OK.

On startup the backend creates tables, initialises PGVector, connects to the
MCP server, builds the Gemini client, and compiles **both** agent arms
(supervisor + monolithic).

---

## 5. Frontend (Expo)

```powershell
cd frontend
npm install                          # first time only
npm start                            # expo start
```

Then scan the QR code with **Expo Go**, or press `a` (Android) / `i` (iOS) /
`w` (web).

> **Important — set the backend URL.** The app talks to the backend over your
> LAN IP, not `localhost`. The default is `http://192.168.1.28:8069`
> (`frontend/src/api.tsx`). Change that base URL to **your machine's LAN IP**
> so a physical phone can reach the backend, and make sure the phone is on the
> same Wi‑Fi network.

---

## Quick start (after first-time setup)

Open three terminals:

```powershell
# Terminal 1 — MCP server
cd mcp_server ; .\run.bat

# Terminal 2 — backend
cd backend ; .\run.bat

# Terminal 3 — frontend
cd frontend ; npm start
```

---

## Optional: Evaluation / benchmark harness (thesis)

The benchmark uses the **root `.env`** (the `EVAL_POSTGRE_*` family pointed at
`life-tracker-eval`) and needs extra packages not pinned in
`requirements.txt`: `pyyaml`, `pytest`, `matplotlib`, `scipy`, `python-docx`.

```powershell
cd backend
.\venv\Scripts\activate
pip install pyyaml pytest matplotlib scipy python-docx   # first time only

# point the MCP server at the EVAL DB first (POSTGRE_DB_NAME=life-tracker-eval),
# then with the MCP server running:
python -m app.evaluation.run_benchmark --arch both --repeats 5
python -m app.evaluation.run_benchmark --arch supervisor --limit 3 --repeats 1   # smoke run

# render the thesis report (stats + figures + .docx)
.\venv\Scripts\python.exe app\evaluation\analyze_results.py
```

> ⚠️ For the benchmark, the **MCP server must point at the eval DB** too
> (`POSTGRE_DB_NAME=life-tracker-eval`). Otherwise the agent's writes hit
> production while the seeder cleans the eval DB, and the measured `db_delta`
> will be wrong. See `PROJECT_OVERVIEW.md` §4 for details.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| Backend fails on startup connecting to MCP | Start the **MCP server first**; confirm it's on `localhost:8000`. |
| `pgvector` / `vector` type errors | `CREATE EXTENSION vector;` wasn't run in that database. |
| App can't reach backend | Update the base URL in `frontend/src/api.tsx` to your LAN IP; phone must be on the same Wi‑Fi. |
| Auth / 401 from Gemini | `GOOGLE_API_KEY` missing or invalid in `backend/.env`. |
| Tracking writes go to the wrong DB | `mcp_server/.env` `POSTGRE_DB_NAME` doesn't match the backend's DB. |
