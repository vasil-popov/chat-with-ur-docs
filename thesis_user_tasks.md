# Your Tasks — Things Only You Can Decide or Provide

These are the items the coding agents **cannot** do for you. They block or shape the work in `thesis_plan.md`. Roughly ordered by when they're needed.

---

## 🔴 Before coding starts

### 1. Confirm advisor's methodology expectations
The plan leaves these configurable, but your advisor may require specific values:
- **Repeats per query (`N`)** — e.g. 5 or 10 runs per scenario per arm (controls variance / lets you do significance tests). Suggested default: **5**.
- **Statistical tests** — does the thesis need significance testing (e.g. paired t-test / Wilcoxon on latency & cost)? If yes, tell me and I'll have the analyzer compute it.
- **Sample size for manual quality scoring** (if you do manual in addition to LLM-judge) — e.g. 20–30 responses per arm.

> If you don't know yet: we proceed with N=5, no significance test, LLM-judge only — and add the rest later.

### 2. Set up an isolated evaluation database
The harness seeds and wipes data between scenarios. **It must not touch your real data.**
- Create a separate Postgres database (or schema), e.g. `life-tracker-eval`, with the `pgvector` extension enabled.
- Provide its connection details (host, port, user, pass, db name) so I can wire an `EVAL_*` env config.
- Decide: same Postgres instance (new DB) — simplest — or a throwaway Docker Postgres for evals.

### 3. Provide Gemini pricing constants
For the cost metric I will **not guess prices**. Give me the current per-1K-token input and output prices for `gemini-3-flash-preview` (from your Google AI pricing page), and I'll put them in config as `PRICE_IN_PER_1K` / `PRICE_OUT_PER_1K`.

### 4. Confirm API quota / key for bulk runs
Running the full benchmark = (scenarios × 2 arms × N repeats) + judge calls. That can be hundreds of Gemini calls.
- Confirm `GOOGLE_API_KEY` is set and has enough quota, **or** tell me a rate-limit you want the harness to respect (delay between calls).

---

## 🟡 During Phase 3 (dataset) — this is where your domain knowledge is essential

### 5. Validate / co-author the golden scenarios
I'll **draft** the scenario set, but you must confirm the **expected outcomes** are correct, because you define what "success" means:
- For each scenario: is the **expected route** right? Are the **expected tool calls + args** right? Is the **expected DB effect** right?
- For RAG scenarios: provide (or point me to) the **sample documents** to upload, and the correct answers contained in them.
- For quality scenarios: confirm the **reference answer** and **rubric points** that the judge will grade against.

> The credibility of the whole comparison rests on this dataset being correct. Plan ~1 focused session reviewing the draft scenarios with me.

### 6. Decide scenario count per category
Plan aims for **≥5 per category** (tracking, rag, general, multi-domain, ambiguous). Tell me if your advisor expects more (e.g. 10–15 each) for stronger statistics.

---

## 🟢 Later / optional

### 7. Decide on the live demo toggle (Phase 7)
Do you want a button in the app to switch architectures live for your defense demo? It's optional and doesn't affect the data. Yes/No.

### 8. Manual quality scoring (if doing it)
If you want manual scores alongside the LLM-judge, you'll score the exported `manual_scoring.csv` (blind to architecture). I'll generate it; you fill in the scores.

### 9. Thesis write-up (yours to author)
The code produces tables + figures. The narrative — research question, literature review, methodology justification, interpretation of results, threats to validity, conclusion — is yours. I can help draft/structure any section on request, but the analysis and argument should be your own work.

---

## Quick-start: minimum to unblock me right now
If you want me to start **Phase 1 (build the monolithic agent + toggle)** immediately, I need **nothing** from this list — Phase 1 has no external dependencies. Items **1–4** are needed before **Phase 4 (running experiments)**; item **5** is needed during **Phase 3 (dataset)**.

Just say the word and I'll kick off Phase 1 through the orchestration workflow (python-developer → python-reviewer).
