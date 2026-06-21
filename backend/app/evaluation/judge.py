from __future__ import annotations

import argparse
import csv
import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.evaluation.dataset.loader import (
    DEFAULT_SCENARIOS_PATH,
    Scenario,
    load_dataset,
)
from app.evaluation.metrics import append_run_metrics, compute_cost

logger = logging.getLogger("judge")

_MODULE_DIR = Path(__file__).with_name("results")
_DEFAULT_RUNS = _MODULE_DIR / "runs.jsonl"
_DEFAULT_OUT = _MODULE_DIR / "runs_judged.jsonl"
_DEFAULT_MANUAL_CSV = _MODULE_DIR / "manual_scoring.csv"
_DEFAULT_KEY_CSV = _MODULE_DIR / "manual_scoring_key.csv"

# Fixed seed so the blind manual-scoring shuffle is reproducible across exports.
_SHUFFLE_SEED = 1337

_MANUAL_COLUMNS = (
    "anon_id",
    "question",
    "answer",
    "correctness",
    "completeness",
    "relevance",
    "conciseness",
    "notes",
)
_KEY_COLUMNS = ("anon_id", "scenario_id", "arch", "repeat")

# Lazily built, module-level so a batch reuses one structured-output client.
_judge_llm: Any | None = None


# ---------------------------------------------------------------------------
# Structured judge output.
# ---------------------------------------------------------------------------
class QualityScores(BaseModel):
    """LLM-judged quality of a candidate final answer (supplementary signal).

    Each 1-5 dimension is graded strictly against the reference answer and
    rubric points. These scores never feed the rule-based ``task_success``.
    """

    model_config = ConfigDict(
        title="QualityScores",
        json_schema_extra={
            "description": "Blind 1-5 quality grading of a final answer "
            "against a reference answer and rubric."
        },
    )

    correctness: int = Field(
        ge=1,
        le=5,
        description="Factual agreement with the reference answer (1 worst, 5 best).",
    )
    completeness: int = Field(
        ge=1,
        le=5,
        description="How many rubric points the answer covers (1 worst, 5 best).",
    )
    relevance: int = Field(
        ge=1,
        le=5,
        description="How on-topic the answer is to the question (1 worst, 5 best).",
    )
    conciseness: int = Field(
        ge=1,
        le=5,
        description="Absence of padding/repetition while staying complete "
        "(1 worst, 5 best).",
    )
    hallucination_detected: bool = Field(
        description="True if the answer asserts facts not supported by the "
        "reference answer or rubric points.",
    )
    rationale: str = Field(
        description="One-sentence justification for the scores.",
    )


@dataclass(frozen=True, slots=True)
class JudgeResult:
    """Outcome of judging a single candidate answer.

    ``failed=True`` (with ``scores=None``) means the LLM did not return parsable
    structured output; the token counts may still be populated from the raw
    response so spend is accounted for even on failure.
    """

    scores: QualityScores | None
    failed: bool
    error: str | None
    prompt_tokens: int
    completion_tokens: int
    est_cost_usd: float


@dataclass
class JudgeSummary:
    """Aggregate counts and judge spend across a post-hoc batch."""

    judged: int = 0
    failed: int = 0
    skipped_error: int = 0
    skipped_resume: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    est_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary dict."""
        return {
            "judged": self.judged,
            "failed": self.failed,
            "skipped_error": self.skipped_error,
            "skipped_resume": self.skipped_resume,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "est_cost_usd": self.est_cost_usd,
        }


# ---------------------------------------------------------------------------
# Prompt construction (blind: no architecture, ever).
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a strict, impartial grader of assistant answers. You grade ONLY "
    "the candidate answer's quality against a provided reference answer and a "
    "list of rubric points. You do not know and must not speculate about which "
    "system produced the candidate. Grade each dimension on an integer scale of "
    "1 (worst) to 5 (best):\n"
    "- correctness: factual agreement with the reference answer.\n"
    "- completeness: how many rubric points the candidate covers.\n"
    "- relevance: how directly the candidate addresses the question.\n"
    "- conciseness: absence of padding/repetition while staying complete.\n"
    "Set hallucination_detected=true if the candidate asserts any fact NOT "
    "supported by the reference answer or rubric points. Provide a single-"
    "sentence rationale. Be terse and objective."
)


def _build_human_prompt(
    question: str,
    reference_answer: str,
    answer_points: tuple[str, ...],
    candidate: str,
) -> str:
    """Render the blind grading prompt for one candidate answer."""
    rubric = (
        "\n".join(f"- {point}" for point in answer_points)
        if answer_points
        else "(no explicit rubric points; grade against the reference answer)"
    )
    return (
        f"QUESTION:\n{question}\n\n"
        f"REFERENCE ANSWER (ground truth):\n{reference_answer}\n\n"
        f"RUBRIC POINTS the answer should cover:\n{rubric}\n\n"
        f"CANDIDATE ANSWER to grade:\n{candidate}\n\n"
        "Grade the candidate answer now."
    )


def _get_judge_llm(llm: Any | None) -> Any:
    """Return a structured-output judge client, caching the default at module level.

    A caller-supplied ``llm`` is wrapped fresh (tests inject mocks); the default
    Gemini client is built once and reused so a batch shares a single client.
    """
    if llm is not None:
        return llm.with_structured_output(QualityScores, include_raw=True)

    global _judge_llm
    if _judge_llm is None:
        from app.deps.dependency_factory import get_llm_client

        _judge_llm = get_llm_client().with_structured_output(
            QualityScores, include_raw=True
        )
    return _judge_llm


def _judge_prices() -> tuple[float, float]:
    """Return (price_in_per_1k, price_out_per_1k) from Settings.

    Imported lazily so the module stays importable offline (without a populated
    .env), mirroring how the harness localizes its settings-dependent imports.
    If Settings cannot be constructed (e.g. missing env in an offline context),
    prices fall back to 0.0 so the supplementary judge stays non-fatal -- token
    counts are still recorded, only the USD estimate is suppressed.
    """
    try:
        from app.config import settings

        return settings.PRICE_IN_PER_1K, settings.PRICE_OUT_PER_1K
    except Exception as exc:  # noqa: BLE001 -- judge cost must never abort a run.
        logger.warning("Could not load pricing from Settings (%s); using 0.0.", exc)
        return 0.0, 0.0


def _extract_token_usage(raw: Any) -> tuple[int, int]:
    """Pull (prompt_tokens, completion_tokens) from a raw AIMessage, defaulting to 0."""
    usage = getattr(raw, "usage_metadata", None)
    if not isinstance(usage, dict):
        return 0, 0
    prompt_tokens = int(usage.get("input_tokens", 0) or 0)
    completion_tokens = int(usage.get("output_tokens", 0) or 0)
    return prompt_tokens, completion_tokens


def judge_answer(
    question: str,
    reference_answer: str,
    answer_points: tuple[str, ...],
    candidate: str,
    *,
    llm: Any | None = None,
) -> JudgeResult:
    """Blind-grade a single candidate answer; never raises on judge failure.

    The grader sees only question/reference/rubric/candidate -- never the
    producing architecture. Returns a :class:`JudgeResult` with populated scores
    on success, or ``failed=True``/``scores=None`` when the structured output is
    missing or unparsable. Token spend is tallied from the raw response when
    available (even on failure) so cost accounting stays accurate.
    """
    judge_llm = _get_judge_llm(llm)
    messages = [
        ("system", _SYSTEM_PROMPT),
        (
            "human",
            _build_human_prompt(question, reference_answer, answer_points, candidate),
        ),
    ]

    try:
        response = judge_llm.invoke(messages)
    except Exception as exc:  # noqa: BLE001 -- judge failure must be non-fatal.
        logger.warning("Judge invocation raised; recording as failure: %s", exc)
        return JudgeResult(
            scores=None,
            failed=True,
            error=str(exc),
            prompt_tokens=0,
            completion_tokens=0,
            est_cost_usd=0.0,
        )

    raw = response.get("raw")
    parsed = response.get("parsed")
    parsing_error = response.get("parsing_error")

    prompt_tokens, completion_tokens = _extract_token_usage(raw)
    price_in, price_out = _judge_prices()
    est_cost = compute_cost(prompt_tokens, completion_tokens, price_in, price_out)

    if parsed is None or parsing_error is not None:
        error = str(parsing_error) if parsing_error is not None else "no parsed output"
        logger.warning("Judge returned unparsable output: %s", error)
        return JudgeResult(
            scores=None,
            failed=True,
            error=error,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            est_cost_usd=est_cost,
        )

    return JudgeResult(
        scores=parsed,
        failed=False,
        error=None,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        est_cost_usd=est_cost,
    )


# ---------------------------------------------------------------------------
# Run-row / dataset helpers.
# ---------------------------------------------------------------------------
def _row_key(row: dict[str, Any]) -> tuple[str, str, int] | None:
    """Return the ``(scenario_id, arch, repeat)`` identity of a run row, or None."""
    scenario_id = row.get("scenario_id")
    arch = row.get("arch")
    repeat = row.get("repeat")
    if scenario_id is None or arch is None or repeat is None:
        return None
    return (str(scenario_id), str(arch), int(repeat))


def _iter_run_rows(runs_path: Path) -> list[dict[str, Any]]:
    """Read every JSON line from a runs file into a list of dicts."""
    if not runs_path.is_file():
        raise FileNotFoundError(f"Runs file not found: {runs_path}")
    rows: list[dict[str, Any]] = []
    for line in runs_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _load_judged_keys(out_path: Path) -> set[tuple[str, str, int]]:
    """Read existing ``(scenario_id, arch, repeat)`` keys from a prior judged file."""
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
        key = _row_key(row)
        if key is not None:
            done.add(key)
    return done


def _build_scenario_index(dataset_path: str | Path | None) -> dict[str, Scenario]:
    """Load the dataset and return a ``{scenario_id: Scenario}`` lookup."""
    path = dataset_path if dataset_path is not None else DEFAULT_SCENARIOS_PATH
    dataset = load_dataset(path)
    return {scenario.id: scenario for scenario in dataset.scenarios}


# ---------------------------------------------------------------------------
# Blind manual-scoring export.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class _ManualRow:
    """One judged candidate prepared for blind manual export."""

    scenario_id: str
    arch: str
    repeat: int
    question: str
    answer: str


def _write_manual_scoring(
    manual_rows: list[_ManualRow],
    manual_csv_path: Path,
    key_csv_path: Path,
) -> None:
    """Write the blind rater CSV and the separate un-blinding key CSV.

    The rater CSV is shuffled (fixed seed), carries opaque ``anon_id`` handles
    and BLANK score columns, and contains no architecture/scenario_id. The key
    CSV is the only artifact that maps ``anon_id -> scenario_id/arch/repeat``.
    """
    shuffled = list(manual_rows)
    random.Random(_SHUFFLE_SEED).shuffle(shuffled)

    for path in (manual_csv_path, key_csv_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    with manual_csv_path.open("w", encoding="utf-8", newline="") as manual_fh, \
            key_csv_path.open("w", encoding="utf-8", newline="") as key_fh:
        manual_writer = csv.DictWriter(manual_fh, fieldnames=list(_MANUAL_COLUMNS))
        key_writer = csv.DictWriter(key_fh, fieldnames=list(_KEY_COLUMNS))
        manual_writer.writeheader()
        key_writer.writeheader()

        for index, row in enumerate(shuffled, start=1):
            anon_id = f"a{index:03d}"
            manual_writer.writerow(
                {
                    "anon_id": anon_id,
                    "question": row.question,
                    "answer": row.answer,
                    "correctness": "",
                    "completeness": "",
                    "relevance": "",
                    "conciseness": "",
                    "notes": "",
                }
            )
            key_writer.writerow(
                {
                    "anon_id": anon_id,
                    "scenario_id": row.scenario_id,
                    "arch": row.arch,
                    "repeat": row.repeat,
                }
            )


# ---------------------------------------------------------------------------
# Post-hoc batch judging.
# ---------------------------------------------------------------------------
def judge_runs(
    runs_path: str | Path,
    *,
    dataset_path: str | Path | None = None,
    out_path: str | Path | None = None,
    manual_csv_path: str | Path | None = None,
    key_csv_path: str | Path | None = None,
    limit: int | None = None,
    resume: bool = False,
    llm: Any | None = None,
) -> JudgeSummary:
    """Judge final-answer quality for every successful run row, post-hoc.

    Reads ``runs.jsonl``, looks each row's scenario up in the dataset, blind-
    grades the candidate against the reference + rubric, and writes an enriched
    JSONL row (original row plus a separate ``"quality"`` key). Error rows are
    skipped. The original ``"score"``/``task_success`` is NEVER modified. Also
    exports the blind manual-scoring CSV pair. Returns a :class:`JudgeSummary`
    with judged/failed/skipped counts and total judge token spend + cost.
    """
    runs_path = Path(runs_path)
    out_path = Path(out_path) if out_path is not None else _DEFAULT_OUT
    manual_csv_path = (
        Path(manual_csv_path) if manual_csv_path is not None else _DEFAULT_MANUAL_CSV
    )
    key_csv_path = Path(key_csv_path) if key_csv_path is not None else _DEFAULT_KEY_CSV

    scenarios = _build_scenario_index(dataset_path)
    rows = _iter_run_rows(runs_path)
    done = _load_judged_keys(out_path) if resume else set()

    summary = JudgeSummary()
    manual_rows: list[_ManualRow] = []
    # Counts every attempted judge_answer call (success OR failure); this is the
    # budget ``--limit`` caps -- an attempt budget, not a success budget.
    attempted_count = 0

    for row in rows:
        if "error" in row:
            summary.skipped_error += 1
            continue

        key = _row_key(row)
        if key is not None and key in done:
            summary.skipped_resume += 1
            continue

        if limit is not None and attempted_count >= limit:
            break

        scenario = scenarios.get(str(row.get("scenario_id")))
        if scenario is None:
            logger.warning(
                "No scenario for id %r; skipping judge.", row.get("scenario_id")
            )
            summary.skipped_error += 1
            continue

        question = row.get("message") or scenario.message
        candidate = row.get("final_answer") or ""
        result = judge_answer(
            question=question,
            reference_answer=scenario.expected.reference_answer,
            answer_points=scenario.expected.answer_points,
            candidate=candidate,
            llm=llm,
        )

        summary.prompt_tokens += result.prompt_tokens
        summary.completion_tokens += result.completion_tokens
        summary.est_cost_usd += result.est_cost_usd
        attempted_count += 1

        enriched = dict(row)
        if result.failed or result.scores is None:
            summary.failed += 1
            enriched["quality"] = {"failed": True, "error": result.error}
        else:
            summary.judged += 1
            enriched["quality"] = result.scores.model_dump()
            manual_rows.append(
                _ManualRow(
                    scenario_id=str(row.get("scenario_id")),
                    arch=str(row.get("arch")),
                    repeat=int(row.get("repeat", 0)),
                    question=question,
                    answer=candidate,
                )
            )

        append_run_metrics(str(out_path), enriched)

    # Only (re)write the rater CSV pair when there is fresh annotation work to
    # export. Writing a header-only CSV here would clobber a prior export and
    # destroy any human annotations already entered against it.
    if manual_rows:
        _write_manual_scoring(manual_rows, manual_csv_path, key_csv_path)
    else:
        logger.info(
            "No newly-judged rows; leaving manual scoring CSV untouched: %s",
            manual_csv_path,
        )

    logger.info(
        "Judge complete: judged=%d failed=%d skipped_error=%d skipped_resume=%d "
        "prompt_tokens=%d completion_tokens=%d est_cost_usd=%.6f",
        summary.judged,
        summary.failed,
        summary.skipped_error,
        summary.skipped_resume,
        summary.prompt_tokens,
        summary.completion_tokens,
        summary.est_cost_usd,
    )
    return summary


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post-hoc LLM-as-judge quality scoring over runs.jsonl "
        "(supplementary; never affects task_success)."
    )
    parser.add_argument(
        "--runs", type=str, default=str(_DEFAULT_RUNS), help="Input runs JSONL path."
    )
    parser.add_argument(
        "--dataset", type=str, default=None, help="Path to the scenarios YAML."
    )
    parser.add_argument(
        "--out", type=str, default=str(_DEFAULT_OUT), help="Enriched JSONL output path."
    )
    parser.add_argument(
        "--manual-csv",
        type=str,
        default=str(_DEFAULT_MANUAL_CSV),
        help="Blind rater-facing manual-scoring CSV path.",
    )
    parser.add_argument(
        "--key-csv",
        type=str,
        default=str(_DEFAULT_KEY_CSV),
        help="Un-blinding key CSV path (the only place arch is recorded).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap attempted judge calls at N (an attempt budget: each call "
        "counts whether it succeeds or fails).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip rows already present in --out by (scenario_id, arch, repeat).",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point: judge runs and print the summary."""
    logging.basicConfig(level=logging.INFO)
    args = _parse_args()
    summary = judge_runs(
        args.runs,
        dataset_path=args.dataset,
        out_path=args.out,
        manual_csv_path=args.manual_csv,
        key_csv_path=args.key_csv,
        limit=args.limit,
        resume=args.resume,
    )
    print(json.dumps(summary.to_dict(), indent=2))  # noqa: T201 -- CLI output.


if __name__ == "__main__":
    main()
