# Thesis Implementation Plan — Coding Agent Brief

**Thesis:** *Comparative study of a Multi-Agent Supervisor architecture and a Monolithic ReAct Agent in an intelligent system for tracking daily activities.*

This document is the implementation brief for the coding subagents (`python-developer` to implement, `python-reviewer` to review). It describes **what to build**, **where**, and the **acceptance criteria** for each unit of work. Hand each phase to the developer subagent with this file as context.

> **Tech stack:** Python 3 · FastAPI 0.129 · LangGraph · LangChain · `langchain-google-genai` (Gemini) · SQLModel · PGVector. All new backend code lives under `backend/`.

---

## 1. Research framing (read first — it constrains every design choice)

| Concept | Decision |
|---------|----------|
| **Independent variable** | Agent architecture: `supervisor` (existing) vs `monolithic` (to build). |
| **Dependent variables** | Latency, token usage & cost, task-success/accuracy, response quality. |
| **Controlled (held identical)** | LLM model + temperature, tool implementations, prompt *content*, benchmark inputs, hardware, retrieval pipeline. |
| **Fairness rule** | The monolithic agent MUST reuse the *same tool objects*, the *same `ChatGoogleGenerativeAI` client*, and prompt text that is the **union of the three specialist prompts** (minus routing/handoff language). Nothing else may differ between arms. |

**Methodological note to preserve (document in code comments):** the supervisor intrinsically manages context differently from a monolithic ReAct loop (it strips intermediate tool calls and forwards only the last human turn to specialists; the monolithic agent keeps a full scratchpad). These *internal* differences are exactly what we are studying — so we hold the **external input identical** and allow internal handling to differ. Do not try to equalise internal context strategies.

### Known intended differences / threats to validity (document in the thesis, do NOT "fix" in code)

These were surfaced during Phase 1 review. They are *intrinsic to the two architectures* — equalising them would contaminate the independent variable, so they are documented as methodology rather than patched:

1. **The supervisor's `general` specialist has zero tools; the monolithic agent has all tools.** This means the monolithic arm has a strictly larger action space on queries a human would call "general." This is part of what the architectures *are* (a supervisor dispatches to specialists — one deliberately tool-free — vs one do-it-all agent). Report it as a threat to validity; the benchmark's "general" category and routing-accuracy metric will quantify its effect rather than hide it.
2. **`date.today()` is resolved once at graph-build (startup), not per request.** Both arms are built within milliseconds of each other in the same lifespan, so they always share the same date string — no confound between arms. Limitation: a server left running across midnight serves a stale date to both arms equally. Acceptable for batch experiment runs that start fresh.
3. **Internal context strategy differs** (see methodological note above) — intended.

---

## 2. Current state (baseline already in repo)

- `backend/app/services/agents.py` → `build_graph()` builds the **supervisor** arm (router + 3 ReAct specialists). This is arm A; **do not break it**.
- `backend/app/services/chat_service.py` → `stream_chat()` / `invoke_chat()` drive any LangGraph graph via `astream_events` / `ainvoke`. Both arms must remain drop-in compatible with these.
- `backend/app/deps/dependency_container.py` → singleton DI; currently holds a single `agent_instance`.
- `backend/app/deps/dependency_factory.py` → `get_llm_client()`, `get_mcp_client()`.
- `backend/app/main.py` lifespan → builds tools + graph at startup.
- Tools: MCP tracking tools (loaded from MCP server) + RAG tools (`backend/app/tools/rag_tools.py`).

---

## 3. Target end-state

```
ChatRequest { message, file_ids, arch: "supervisor" | "monolithic" }
        │
        ▼
DI container holds BOTH graphs: { "supervisor": g1, "monolithic": g2 }
        │
        ▼
MetricsCallbackHandler wraps every run → captures latency / tokens / LLM calls / tool calls
        │
        ▼
Evaluation harness runs the golden dataset × both arms × N repeats → JSONL
        │
        ▼
Scorer (rule-based correctness) + LLM-as-judge (quality) → enriched JSONL
        │
        ▼
Analyzer → CSV tables + matplotlib figures for the thesis
```

---

## 4. Metric definitions (must be implemented exactly as defined)

| Metric | Definition | Source |
|--------|------------|--------|
| `latency_total_ms` | Wall-clock from request received to final token. | timestamps in harness |
| `latency_ttft_ms` | Time to first streamed content token. | first `on_chat_model_stream`/content event |
| `llm_call_count` | Number of distinct LLM invocations (incl. supervisor router calls). | `on_llm_start` count |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | Summed across **all** LLM calls in the turn. | Gemini `usage_metadata` via `on_llm_end` |
| `est_cost_usd` | `prompt_tokens·P_in + completion_tokens·P_out`. `P_in`/`P_out` are configurable constants (set by user — do NOT hardcode guessed prices). | computed |
| `tool_call_count` | Number of tool executions. | `on_tool_start` count |
| `tools_called` | Ordered list of `(tool_name, args)`. | callback |
| `hops` | LangGraph super-steps taken. | graph stream |
| `route_correct` | (supervisor only) did the router pick the expected domain? | scorer vs dataset |
| `tool_calls_correct` | Did actual tool calls match expected set (name + key args)? | scorer vs dataset |
| `db_effect_correct` | (write scenarios) did DB end in expected state? | scorer vs dataset |
| `task_success` | Boolean AND of the applicable correctness checks. | scorer |
| `quality_*` | LLM-judge scores (correctness, completeness, relevance, conciseness, 1–5). | judge |

---

## 5. Phased work breakdown

Each phase is an independently reviewable unit. Order matters; later phases depend on earlier ones.

### Phase 1 — Monolithic ReAct agent + per-request architecture switch

**Files:**
- `backend/app/services/agents.py` — add `build_monolithic_agent(llm, mcp_tools, rag_tools)`.
- `backend/app/deps/dependency_container.py` — replace single `agent_instance` with a dict `agents: dict[str, Any]` + getter `get_agent(arch: str)` defaulting to `"supervisor"`.
- `backend/app/main.py` lifespan — build both graphs, register both.
- `backend/app/api/schemas/chat.py` — add `arch: Literal["supervisor","monolithic"] = "supervisor"`.
- `backend/app/api/routes/chat.py` — select graph by `req.arch` for both `/stream` and `/`.

**Design:**
- Define `MONOLITHIC_SYSTEM_PROMPT` as the union of `TRACKING_SYSTEM_PROMPT` + `RAG_SYSTEM_PROMPT` + `GENERAL_SYSTEM_PROMPT`, stripped of all "hand off / route to specialist" language, kept in the same module beside the existing prompts for traceability.
- `build_monolithic_agent` = `create_react_agent(llm, mcp_tools + rag_tools, prompt=SystemMessage(MONOLITHIC_SYSTEM_PROMPT.format(today=today)))`. It returns a compiled graph that is drop-in compatible with `chat_service`.
- Use the **same `llm` instance** and the **same tool lists** passed to `build_graph`.
- Document a recursion/step cap comparable to the supervisor's (`recursion_limit`); record actual hops rather than relying on the cap.

**Acceptance criteria:**
- `POST /api/chat {arch:"monolithic"}` and `{arch:"supervisor"}` both return valid responses through the unchanged `chat_service`.
- Existing supervisor behaviour unchanged when `arch` omitted.
- No duplicate LLM/tool construction — both arms share the singletons.

---

### Phase 2 — Metrics instrumentation

**Files (new):**
- `backend/app/evaluation/__init__.py`
- `backend/app/evaluation/metrics.py` — `RunMetrics` dataclass (all fields from §4) + JSONL writer.
- `backend/app/evaluation/callbacks.py` — `MetricsCallbackHandler(AsyncCallbackHandler)`.

**Design:**
- `MetricsCallbackHandler` records, per run: LLM-call count, token usage (sum `usage_metadata` / `response_metadata` from `on_llm_end`; handle Gemini's field names defensively), tool starts with name+args, first-token timestamp, start/end timestamps.
- Token capture must include **supervisor router calls** — verify by asserting `llm_call_count(supervisor) > llm_call_count(monolithic)` on a simple single-tool query in a smoke test.
- Provide a context-manager / helper `run_with_metrics(graph, state, config) -> (result, RunMetrics)` usable by both the harness and (optionally) the live endpoints.
- Cost computed from constants `PRICE_IN_PER_1K`, `PRICE_OUT_PER_1K` read from settings/env (user supplies real numbers).

**Acceptance criteria:**
- Running one query through each arm yields a populated `RunMetrics` with non-zero token counts.
- Smoke test confirms supervisor records ≥1 extra LLM call (the routing call) vs monolithic for the same single-domain query.

---

### Phase 3 — Golden benchmark dataset

**Files (new):**
- `backend/app/evaluation/dataset/scenarios.yaml` (or `.json`) — versioned scenario list.
- `backend/app/evaluation/dataset/loader.py` — parse + validate scenarios into typed objects (Pydantic).
- `backend/app/evaluation/dataset/seed.py` — per-scenario DB seed + teardown helpers.

**Scenario schema (per entry):**
```yaml
- id: track-log-001
  category: tracking            # tracking | rag | general | multi_domain | ambiguous
  history: []                   # optional prior turns for multi-turn cases
  message: "Log €12 pizza for dinner"
  file_ids: []                  # optional attachments (RAG cases)
  setup: { expenses: [], workouts: [] }   # rows to seed before run (query cases)
  expected:
    route: tracking             # supervisor expected domain (null if N/A)
    tool_calls:                 # name + key args that MUST appear
      - name: log_expense
        args_contains: { amount: 12, category: "Food" }
    db_effect:                  # expected post-run DB state (write cases)
      expenses_added: 1
    reference_answer: "Confirms €12 logged under Food."  # for judge/manual
    answer_points:              # rubric bullet points for the judge
      - "States the amount (12)"
      - "States the category (Food)"
      - "Confirms it was saved"
```

**Coverage targets (the user validates the expected outcomes — see `thesis_user_tasks.md`):**
- Tracking: log expense, log workout, query spending summary, edit/delete, receipt bulk-log.
- RAG: factual lookup in an uploaded doc, summarise, "not in document" refusal.
- General: greeting, definition, follow-up clarification.
- Multi-domain: one turn needing two domains (e.g. "summarise the receipt and log its items").
- Ambiguous: under-specified input that stresses routing.

**Acceptance criteria:**
- Loader validates the file and rejects malformed scenarios with clear errors.
- Seed/teardown leaves no residual rows between scenarios.
- ≥ a small but balanced set per category (final count set with user; aim ≥ 5 per category).

> **DB isolation:** seed/teardown must run against a **dedicated evaluation database/schema**, never production data. Connection configured via env (see user tasks).

---

### Phase 4 — Evaluation harness

**Files (new):**
- `backend/app/evaluation/scorer.py` — rule-based correctness (`route_correct`, `tool_calls_correct`, `db_effect_correct`, `task_success`).
- `backend/app/evaluation/run_benchmark.py` — CLI entry point.

**`run_benchmark.py` behaviour:**
- Args: `--arch {supervisor,monolithic,both}`, `--repeats N`, `--dataset PATH`, `--out PATH`, `--judge/--no-judge`.
- For each scenario × arch × repeat: seed DB → `run_with_metrics` → capture actual tool calls + final answer + final DB state → score → append one JSONL row.
- Deterministic ordering, fixed random seed where randomisation is used, progress logging, resumable (skip already-completed rows by id+arch+repeat).
- Must NOT depend on the running FastAPI server — import and invoke the graphs directly so it works headless.

**Acceptance criteria:**
- A full run over the dataset for both arms produces a JSONL where every row has metrics + correctness fields.
- Re-running with the same args is idempotent (no duplicate rows).

---

### Phase 5 — LLM-as-judge (response quality)

**Files (new):**
- `backend/app/evaluation/judge.py`

**Design:**
- Function `judge_answer(question, reference_answer, answer_points, candidate) -> QualityScores` using a `ChatGoogleGenerativeAI` judge at `temperature=0` with structured output (Pydantic): `correctness`, `completeness`, `relevance`, `conciseness` (1–5) + short rationale.
- **Blind scoring:** the judge prompt must NOT reveal which architecture produced the answer; harness passes candidates anonymised and in randomised order.
- Also emit a **manual-scoring export** (`results/manual_scoring.csv`) with columns: `scenario_id`, `anon_id`, `question`, `answer`, blank score columns — arch label kept in a separate key file so manual raters stay blind.

**Acceptance criteria:**
- Judge returns valid structured scores for a sample answer.
- Export CSV opens cleanly and contains no architecture leak in the rater-facing columns.

---

### Phase 6 — Analysis & reporting

**Files (new):**
- `backend/app/evaluation/analyze.py`

**Design (pandas + matplotlib):**
- Load results JSONL → DataFrame.
- Aggregate per arch (and per category): mean/median/p95 latency, mean tokens & cost, success rate, mean judge scores.
- Emit: `results/summary.csv`, `results/summary.md` (Markdown tables ready for the thesis), and figures under `results/figures/` (latency boxplot, token/cost bar chart, success-rate bar chart, quality-score grouped bar chart).
- Where relevant, include a paired comparison per scenario (same input, two arms) to support significance testing.

**Acceptance criteria:**
- One command turns a results JSONL into CSV + Markdown tables + PNG figures.
- Numbers in `summary.md` reconcile with raw JSONL on spot check.

---

### Phase 7 — (Optional) Frontend architecture toggle for the live demo

**Files:**
- `frontend/src/api.tsx` — send `arch` in chat requests.
- A small dev-only selector (e.g. in the drawer footer) to switch arms during demos.

Only build if the user wants a live side-by-side demo; not required for the thesis data. Delegate to `frontend-developer` if requested.

---

## 6. New directory layout (additions only)

```
backend/app/evaluation/
├── __init__.py
├── metrics.py            # RunMetrics + JSONL writer
├── callbacks.py          # MetricsCallbackHandler
├── scorer.py             # rule-based correctness
├── judge.py              # LLM-as-judge + manual export
├── run_benchmark.py      # CLI harness
├── analyze.py            # tables + figures
├── dataset/
│   ├── scenarios.yaml
│   ├── loader.py
│   └── seed.py
└── results/              # JSONL, CSV, figures (gitignore large artefacts)
```

---

## 7. Dependency additions (`backend/requirements.txt`)

- `pandas`, `matplotlib` (analysis)
- `pyyaml` (if scenarios in YAML)
- (token/cost capture uses existing `langchain-google-genai`)

Keep additions minimal; justify any others in the PR.

---

## 8. Cross-cutting requirements

- **Do not regress** the existing supervisor arm or the live app.
- Follow the global engineering principles (SRP, DRY, KISS, guard clauses, small functions, explicit naming).
- All new modules get docstrings and type hints; no hardcoded secrets or prices.
- Each phase: developer implements → `python-reviewer` reviews (scope: correctness, async safety, security, fairness-of-comparison) → fix loop until approved.

## 9. Suggested delivery order & checkpoints

1. Phase 1 (arms + toggle) — verify both answer.
2. Phase 2 (metrics) — verify token/LLM-call capture incl. router overhead.
3. Phase 3 (dataset) — **user validates expected outcomes**.
4. Phase 4 (harness) — first full data run.
5. Phase 5 (judge) — quality layer.
6. Phase 6 (analysis) — thesis tables/figures.
7. Phase 7 (demo toggle) — optional.

After Phase 4 you can already produce preliminary latency/cost/accuracy results; quality (Phase 5–6) enriches them.
