from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlmodel import Session, func, select

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("run_benchmark")

# Load env BEFORE importing modules that read settings at import time.
# Anchor to the repo-root .env absolutely (independent of cwd). This file lives
# at backend/app/evaluation/run_benchmark.py, so parents[3] is the repo root,
# matching the previous relative ``../.env`` intent (cwd=backend/ -> <repo>/.env).
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from app.config import settings  # noqa: E402
from app.db.database import Expense, UploadedFile, WorkoutSession  # noqa: E402
from app.evaluation.dataset.loader import (  # noqa: E402
    DEFAULT_SCENARIOS_PATH,
    Scenario,
    load_dataset,
)
from app.evaluation.dataset.seed import (  # noqa: E402
    SeededIds,
    ensure_tables,
    get_eval_engine,
    seed_scenario,
    teardown,
)
from app.evaluation.metrics import append_run_metrics  # noqa: E402
from app.evaluation.scorer import score_run  # noqa: E402
from app.services import embedding_service  # noqa: E402
from app.services.chat_service import extract_content  # noqa: E402

_DEFAULT_OUT = Path(__file__).with_name("results") / "runs.jsonl"
# Top-level graph super-step cap, applied identically to both arms. Evidence
# (full limit-25 run): legitimate supervisor runs use <=5 top-level super-steps
# and the ReAct loop <=~9; runaway router loops use 13-25+. 15 leaves headroom
# for legitimate multi-domain routing while bounding runaway-loop cost.
_RECURSION_LIMIT = 15
_REF_PREFIX = "<ref:"
_REF_SUFFIX = ">"


# ---------------------------------------------------------------------------
# Placeholder resolution: <ref:NAME> -> real seeded UUID string.
# ---------------------------------------------------------------------------
def _resolve_ref(value: str, seeded: SeededIds) -> str:
    """Resolve a single ``<ref:NAME>`` token to its seeded UUID string.

    Looks the ref up across every SeededIds map (file/expense/workout/exercise).
    Returns the original token unchanged if no seeded id is found, so an
    unresolved placeholder surfaces as a scoring mismatch rather than a crash.
    """
    if not (value.startswith(_REF_PREFIX) and value.endswith(_REF_SUFFIX)):
        return value
    ref = value[len(_REF_PREFIX) : -len(_REF_SUFFIX)]
    for mapping in (
        seeded.file_ids,
        seeded.expense_ids,
        seeded.exercise_ids,
        seeded.workout_session_ids,
    ):
        if ref in mapping:
            return str(mapping[ref])
    logger.warning("Unresolved placeholder %r (no seeded ref); leaving as-is.", value)
    return value


def _resolve_value(value: Any, seeded: SeededIds) -> Any:
    """Recursively resolve ``<ref:...>`` tokens inside strings/lists/dicts."""
    if isinstance(value, str):
        return _resolve_ref(value, seeded)
    if isinstance(value, list):
        return [_resolve_value(item, seeded) for item in value]
    if isinstance(value, tuple):
        return tuple(_resolve_value(item, seeded) for item in value)
    if isinstance(value, dict):
        return {key: _resolve_value(item, seeded) for key, item in value.items()}
    return value


def _resolve_scenario(scenario: Scenario, seeded: SeededIds) -> Scenario:
    """Return a COPY of ``scenario`` with ``<ref:...>`` placeholders resolved.

    Resolves placeholders in ``file_ids`` and in every ``expected.tool_calls``
    ``args_expected`` so the scorer compares against real UUIDs. The original
    scenario object is never mutated.
    """
    raw = scenario.model_dump()
    raw["file_ids"] = [_resolve_ref(fid, seeded) for fid in scenario.file_ids]
    for tool_call in raw["expected"]["tool_calls"]:
        tool_call["args_expected"] = _resolve_value(tool_call["args_expected"], seeded)
    return Scenario.model_validate(raw)


# ---------------------------------------------------------------------------
# RAG indexing for seeded files (embeddings are NOT created by the seeder).
# ---------------------------------------------------------------------------
async def _index_seeded_files(scenario: Scenario, seeded: SeededIds) -> list[str]:
    """Embed each seeded file so semantic search can find it. Returns file ids.

    ``embed_file`` is a synchronous network+DB call, so it is offloaded to a
    worker thread to avoid blocking the event loop inside ``_run_one``.
    """
    indexed: list[str] = []
    for seed_file in scenario.setup.files:
        if not seed_file.ref or seed_file.ref not in seeded.file_ids:
            continue
        file_id = str(seeded.file_ids[seed_file.ref])
        await asyncio.to_thread(
            embedding_service.embed_file,
            file_id=file_id,
            file_name=seed_file.original_name,
            text=seed_file.extracted_text,
        )
        indexed.append(file_id)
    return indexed


async def _delete_seeded_embeddings(file_ids: list[str]) -> None:
    """Remove embeddings for the given seeded files so chunks do not leak.

    ``delete_file_embeddings`` is a synchronous network+DB call, so it is offloaded
    to a worker thread to avoid blocking the event loop inside ``_run_one``.
    """
    for file_id in file_ids:
        await asyncio.to_thread(embedding_service.delete_file_embeddings, file_id)


# ---------------------------------------------------------------------------
# DB delta computation (post-state minus pre-state row counts).
# ---------------------------------------------------------------------------
def _count_rows(engine: Engine) -> dict[str, int]:
    """Return current row counts for the tables a db_effect can describe."""
    with Session(engine) as session:
        expenses = session.exec(select(func.count()).select_from(Expense)).one()
        workouts = session.exec(select(func.count()).select_from(WorkoutSession)).one()
        files = session.exec(select(func.count()).select_from(UploadedFile)).one()
    return {"expenses": int(expenses), "workouts": int(workouts), "files": int(files)}


def _compute_db_delta(pre: dict[str, int], post: dict[str, int]) -> dict[str, int]:
    """Translate pre/post counts into the ``*_added`` keys the scorer expects."""
    return {
        "expenses_added": post["expenses"] - pre["expenses"],
        "workouts_added": post["workouts"] - pre["workouts"],
        "files_added": post["files"] - pre["files"],
    }


# ---------------------------------------------------------------------------
# Agent state construction (history turns prepended to the user message).
# ---------------------------------------------------------------------------
def _build_state(scenario: Scenario) -> dict[str, Any]:
    """Build the agent input state, prepending any history turns.

    History turns are dicts with ``role``/``content`` (see scenarios.yaml). They
    are mapped to LangChain ("user"/"assistant", content) tuples ahead of the
    current user message.
    """
    messages: list[tuple[str, str]] = []
    for turn in scenario.history:
        if isinstance(turn, dict) and "role" in turn and "content" in turn:
            role = "user" if turn["role"] == "user" else "assistant"
            messages.append((role, str(turn["content"])))
    messages.append(("user", scenario.message))
    return {"messages": messages}


# ---------------------------------------------------------------------------
# Resume support.
# ---------------------------------------------------------------------------
def _load_done_keys(out_path: Path) -> set[tuple[str, str, int]]:
    """Read existing (scenario_id, arch, repeat) keys from a prior JSONL run."""
    done: set[tuple[str, str, int]] = set()
    if not out_path.is_file():
        return done
    for line in out_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Any SCORED row counts as done on resume, including non-termination
        # FAILURES (which are scored, not errored). Only rows carrying an "error"
        # field are retried; scored rows are skipped, never re-run.
        if "error" in row:
            continue
        key = (row.get("scenario_id"), row.get("arch"), row.get("repeat"))
        if all(part is not None for part in key):
            done.add((str(key[0]), str(key[1]), int(key[2])))
    return done


# ---------------------------------------------------------------------------
# Single-run execution.
# ---------------------------------------------------------------------------
async def _run_one(
    *,
    scenario: Scenario,
    arch: str,
    repeat: int,
    graph: Any,
    engine: Engine,
    out_path: Path,
) -> None:
    """Seed, run, score, and persist ONE (scenario, arch, repeat) combination.

    Always tears down before and after so the DB starts and ends clean. The
    run_with_metrics import is local to keep the module importable without a live
    LLM environment.
    """
    from app.evaluation.callbacks import run_with_metrics

    teardown(engine)
    indexed_files: list[str] = []
    try:
        seeded = seed_scenario(scenario, engine)
        indexed_files = await _index_seeded_files(scenario, seeded)
        resolved = _resolve_scenario(scenario, seeded)

        # Baseline is captured AFTER seeding so db_delta reflects only the
        # agent's own writes during the run, not the scenario's seeded setup.
        pre_counts = _count_rows(engine)

        state = _build_state(scenario)
        result, metrics = await run_with_metrics(
            graph,
            state,
            {"recursion_limit": _RECURSION_LIMIT},
            settings.PRICE_IN_PER_1K,
            settings.PRICE_OUT_PER_1K,
        )
        final_answer = extract_content(result["messages"][-1]) if result is not None else ""

        # db_delta is still computed even on non-termination: the agent may have
        # written to the DB before looping, and those writes must be reflected.
        post_counts = _count_rows(engine)
        db_delta = _compute_db_delta(pre_counts, post_counts)

        score = score_run(
            resolved,
            arch=arch,
            actual_tool_calls=metrics.tools_called,
            nodes_visited=metrics.nodes_visited,
            final_answer=final_answer,
            db_delta=db_delta,
        )

        # A run that hit the recursion limit never terminated; force it to count
        # as a failure so the runaway cost is attributed to the arm rather than
        # excluded as an "error" row.
        if metrics.non_termination:
            score.task_success = False
            score.details["non_termination"] = True

        row = {
            "scenario_id": scenario.id,
            "category": scenario.category,
            "arch": arch,
            "repeat": repeat,
            "message": scenario.message,
            "final_answer": final_answer,
            "metrics": metrics.to_dict(),
            "score": score.to_dict(),
            "actual_tool_calls": [[name, args] for name, args in metrics.tools_called],
            "nodes_visited": list(metrics.nodes_visited),
            "db_delta": db_delta,
            "non_termination": metrics.non_termination,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        append_run_metrics(str(out_path), row)
        logger.info(
            "OK   %s | %s | repeat %d | task_success=%s",
            scenario.id,
            arch,
            repeat,
            score.task_success,
        )
    except Exception as exc:  # noqa: BLE001 -- one failure must not abort the sweep.
        logger.exception("FAIL %s | %s | repeat %d: %s", scenario.id, arch, repeat, exc)
        append_run_metrics(
            str(out_path),
            {
                "scenario_id": scenario.id,
                "category": scenario.category,
                "arch": arch,
                "repeat": repeat,
                "message": scenario.message,
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    finally:
        await _delete_seeded_embeddings(indexed_files)
        teardown(engine)


# ---------------------------------------------------------------------------
# Graph construction (mirrors app/main.py lifespan, headless).
# ---------------------------------------------------------------------------
async def _build_graphs(archs: list[str], today: str) -> dict[str, Any]:
    """Build the requested agent graphs once, mirroring the app lifespan.

    ``today`` pins the agents' notion of the current date to the dataset's
    ``reference_date`` so relative dates ("today", "yesterday") resolve
    identically across runs, giving reproducible benchmark scoring.
    """
    from app.deps.dependency_factory import get_llm_client, get_mcp_client
    from app.services.agents import build_graph, build_monolithic_agent
    from app.tools.rag_tools import (
        get_file_summary,
        list_uploaded_files,
        search_documents,
    )

    llm = get_llm_client()
    mcp_client = get_mcp_client()
    mcp_tools = await mcp_client.get_tools()
    rag_tools = [search_documents, list_uploaded_files, get_file_summary]
    logger.info("Loaded MCP tools: %s", [t.name for t in mcp_tools])

    graphs: dict[str, Any] = {}
    if "supervisor" in archs:
        graphs["supervisor"] = build_graph(llm, mcp_tools, rag_tools, today=today)
    if "monolithic" in archs:
        graphs["monolithic"] = build_monolithic_agent(llm, mcp_tools, rag_tools, today=today)
    return graphs


def _resolve_archs(arch_arg: str) -> list[str]:
    return ["supervisor", "monolithic"] if arch_arg == "both" else [arch_arg]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the golden dataset through the agent arms and score it."
    )
    parser.add_argument(
        "--arch",
        choices=["supervisor", "monolithic", "both"],
        default="both",
        help="Which architecture(s) to evaluate.",
    )
    parser.add_argument(
        "--repeats", type=int, default=5, help="Runs per scenario per arch."
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(DEFAULT_SCENARIOS_PATH),
        help="Path to the scenarios YAML.",
    )
    parser.add_argument(
        "--out", type=str, default=str(_DEFAULT_OUT), help="Output JSONL path."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run the first N scenarios (smoke runs).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip (scenario_id, arch, repeat) rows already present in --out.",
    )
    parser.add_argument(
        "--judge",
        dest="judge",
        action="store_true",
        help="Run the post-hoc LLM-as-judge quality scoring after the sweep "
        "(supplementary; never affects task_success).",
    )
    parser.add_argument(
        "--no-judge", dest="judge", action="store_false", help="Disable the judge (default)."
    )
    parser.set_defaults(judge=False)
    return parser.parse_args()


async def main() -> None:
    """Build graphs once, then sweep (scenario, arch, repeat) deterministically."""
    args = _parse_args()

    if not os.getenv("EVAL_POSTGRE_DB_NAME"):
        logger.error(
            "EVAL_POSTGRE_* not set. The harness needs an eval DB (name must "
            "contain 'eval'). See this module's docstring for setup."
        )
        return

    dataset = load_dataset(args.dataset)
    scenarios = list(dataset.scenarios)
    if args.limit is not None:
        scenarios = scenarios[: args.limit]

    archs = _resolve_archs(args.arch)
    out_path = Path(args.out)

    done = _load_done_keys(out_path) if args.resume else set()
    if done:
        logger.info("Resume: %d existing run rows will be skipped.", len(done))

    engine = get_eval_engine()
    ensure_tables(engine)
    graphs = await _build_graphs(archs, today=dataset.reference_date.isoformat())

    total = len(scenarios) * len(archs) * args.repeats
    completed = 0
    for scenario in scenarios:
        for arch in archs:
            graph = graphs[arch]
            for repeat in range(args.repeats):
                completed += 1
                if (scenario.id, arch, repeat) in done:
                    logger.info(
                        "SKIP %s | %s | repeat %d (resume) [%d/%d]",
                        scenario.id,
                        arch,
                        repeat,
                        completed,
                        total,
                    )
                    continue
                logger.info(
                    "RUN  %s | %s | repeat %d [%d/%d]",
                    scenario.id,
                    arch,
                    repeat,
                    completed,
                    total,
                )
                await _run_one(
                    scenario=scenario,
                    arch=arch,
                    repeat=repeat,
                    graph=graph,
                    engine=engine,
                    out_path=out_path,
                )

    logger.info("Benchmark sweep complete. Results: %s", out_path)

    if args.judge:
        # Post-hoc judging keeps the run re-runnable and cheaper than inline
        # per-run judging. The judge writes a separate enriched JSONL and never
        # touches the task_success scores written above.
        from app.evaluation import judge

        # Derive every judge artifact path from --out so the enriched JSONL and
        # the rater CSV pair land beside the raw runs file instead of at the
        # judge's hardcoded module defaults.
        out_file = Path(args.out)
        judged_out = out_file.with_name(out_file.stem + "_judged.jsonl")
        manual_csv = out_file.with_name("manual_scoring.csv")
        key_csv = out_file.with_name("manual_scoring_key.csv")

        logger.info("Running post-hoc LLM-as-judge over %s ...", out_path)
        summary = judge.judge_runs(
            args.out,
            dataset_path=args.dataset,
            out_path=str(judged_out),
            manual_csv_path=str(manual_csv),
            key_csv_path=str(key_csv),
        )
        logger.info("Judge summary: %s", summary.to_dict())


if __name__ == "__main__":
    asyncio.run(main())
