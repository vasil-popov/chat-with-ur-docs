# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Life OS** — a personal assistant chat app for tracking fitness and expenses. Three independent services must all run simultaneously:

| Service | Tech | Port |
|---------|------|------|
| Frontend | React Native (Expo) | 8081 (web) or native |
| Backend | FastAPI + LangChain | 8069 |
| MCP Server | FastMCP + PostgreSQL | 8000 |

## Running the Services

### Backend
```powershell
cd backend
.\venv\Scripts\activate
py -m uvicorn --env-file .env --host 0.0.0.0 --port 8069 app.main:app
# Or use: .\run.bat
```

### MCP Server
```powershell
cd mcp_server
.\venv\Scripts\activate
# First-time only — initialize DB tables:
python database.py
# Start server:
.\run.bat
```

### Frontend
```powershell
cd frontend
npm install
npm start        # Expo dev server
npm run web      # Web browser
npm run android  # Android emulator
npm run lint     # ESLint
```

## Architecture

```
Frontend (Expo)
    │  POST /api/chat  {"message": "..."}
    ▼
Backend (FastAPI :8069)
  - DI Container holds: LLM client, MCP client, LangChain agent
  - Agent model: google/gemini-flash-3 via langchain-google-genai
  - Calls MCP tools over HTTP
    │  HTTP to localhost:8000/mcp
    ▼
MCP Server (FastMCP :8000)
  - 8 tools: log/get/delete/summary for expenses and workouts
  - Persists to PostgreSQL (life-tracker DB)
```

**Request flow:** User message → `POST /api/chat` → LangChain agent decides which MCP tools to call → MCP server queries PostgreSQL → agent synthesizes markdown response → frontend renders with `react-native-markdown-display`.

## Key Files

- `backend/app/main.py` — FastAPI lifespan: creates MCP client → LLM → agent, stores in `DIContainer`
- `backend/app/deps/dependency_container.py` — Singleton `DIContainer` holding agent, llm, mcp_client
- `backend/app/api/routes/chat.py` — `POST /api/chat` endpoint; extracts tool names from agent response metadata
- `mcp_server/main.py` — FastMCP server, registers tools from `expenses/tools.py` and `exercises/tools.py`
- `mcp_server/database.py` — SQLModel definitions: `Expense`, `WorkoutSession`, `ExerciseLog`
- `frontend/src/api.tsx` — `sendChatMessage()` HTTP client; **API URL is hardcoded** to `http://192.168.1.10:8069`
- `frontend/app/index.tsx` — Main chat screen (messages state, send handler, markdown rendering)

## Environment Variables

`backend/.env`:
```
GOOGLE_API_KEY=<gemini key>
```

`mcp_server/.env`:
```
DB_USER=mcp-app
DB_PASSWORD=mcp-app-pass
DB_HOST=localhost
DB_PORT=5432
DB_NAME=life-tracker
```

## Data Model

- **Expenses**: `id (UUID)`, `amount`, `category`, `description?`, `transaction_date`
- **WorkoutSession** (parent): `id`, `session_name`, `workout_date`
- **ExerciseLog** (child of session): `id`, `session_id (FK)`, `exercise_name`, `category`, `duration_minutes?`, `sets?`, `reps?`, `weight_kg?`, `distance_km?`

## Frontend Notes

- Expo Router 6 with file-based routing under `app/`
- The backend API base URL in `frontend/src/api.tsx` must match the machine's LAN IP for mobile devices to reach it
- Chat response `content` field is markdown; displayed via `react-native-markdown-display`
- TypeScript strict mode is enabled
