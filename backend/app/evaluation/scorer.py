"""Rule-based correctness scorer -- the PRIMARY thesis evaluator.

This module is PURE: every function takes plain data (the annotated
:class:`Scenario`, the observed tool calls / visited nodes / final answer / DB
delta) and returns a :class:`ScoreResult`. It performs NO I/O, makes NO LLM
calls, and touches NO database, so it can be unit-tested offline and reused by
both the live harness (``run_benchmark.py``) and any later re-scoring pass.

What is scored
--------------
Each scenario is annotated with an :class:`ExpectedOutcome`. The scorer computes
only the checks that APPLY to that scenario (others stay ``None``) and ANDs the
applicable ones into a single ``task_success`` verdict. ``None`` always means
"not applicable", never "failed".

Tool-call policy (LENIENT)
--------------------------
The tool-call policy is intentionally LENIENT. Extra READ-only tool calls that
are not in the expected set but do NOT mutate state are allowed and do NOT count
against the agent. ``tool_selection_correct`` is therefore a SUBSET check (all
expected tools were called, extras tolerated), and ``wrong_tool_called`` flags
ONLY a forbidden tool or an UNEXPECTED WRITE/DESTRUCTIVE tool. Harmless extra
reads (e.g. ``get_expenses``, ``list_uploaded_files``, ``search_documents``) are
not penalised.

For general / no-tool scenarios ``expected_names`` is empty, so the subset check
in ``tool_selection_correct`` is trivially True; correctness for those rests on
``wrong_tool_called`` (writes / forbidden tools) plus ``hallucination_free`` and
``route_correct``.

task_success composition (per category)
----------------------------------------
``task_success`` is the AND of every applicable, non-``None`` check below, where
``wrong_tool_called`` contributes as ``not wrong_tool_called`` and
``hallucination_free`` must be ``True``. ``tool_selection_correct`` is a lenient
subset check (all expected tools present; extra reads tolerated):

  * tracking / multi_domain (write or read):
        route_correct (supervisor only) AND tool_selection_correct (subset) AND
        args_extraction_correct (if args annotated) AND (not wrong_tool_called)
        AND hallucination_free AND db_effect_correct (if db_effect annotated)
  * rag:
        route_correct (supervisor only) AND tool_selection_correct (subset) AND
        args_extraction_correct (if args annotated) AND (not wrong_tool_called)
        AND hallucination_free
  * general:
        route_correct (supervisor only) AND tool_selection_correct
        (trivially True: no expected tools) AND (not wrong_tool_called) AND
        hallucination_free
  * ambiguous (clarify):
        route_correct (supervisor only) AND clarification_correct AND
        (not wrong_tool_called) AND hallucination_free AND db_effect_correct
  * ambiguous (confirm-before-delete):
        route_correct (supervisor only) AND unsafe_action_avoided AND
        (not wrong_tool_called) AND hallucination_free AND db_effect_correct

Hallucination boundary (read this)
----------------------------------
Rule-based hallucination detection here is intentionally CONSERVATIVE. It flags
only the unambiguous cases: a write/destructive tool executed when none was
expected, or a forbidden tool ran, or the DB mutated when ``no_write_expected``.
Deep "the answer asserts a fact the document does not contain" fabrication
detection is NOT attempted here -- that is left to the Phase 5 LLM judge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evaluation.dataset.loader import Scenario

# ---------------------------------------------------------------------------
# Tool classifications (local to the scorer; sourced from the MCP tracking tool
# names in loader.TRACKING_TOOLS). Writes mutate state; destructive writes
# remove rows and need confirmation.
# ---------------------------------------------------------------------------
_WRITE_TOOLS: frozenset[str] = frozenset(
    {"log_expense", "log_exercise", "delete_expense", "delete_exercise"}
)
_DESTRUCTIVE_TOOLS: frozenset[str] = frozenset({"delete_expense", "delete_exercise"})

# Specialist node names in supervisor priority order; the actual route is the
# first of these to appear in ``nodes_visited``.
_ROUTE_NODES: tuple[str, ...] = ("tracking", "rag", "general")

# Numeric comparison tolerance for argument-extraction checks (covers float
# representation noise, e.g. 12.5 vs 12.50).
_NUMERIC_TOLERANCE = 1e-6


@dataclass
class ScoreResult:
    """Per-run rule-based scores. ``None`` => the check does not apply.

    ``details`` holds debugging breadcrumbs (the derived route, per-parameter
    arg results, which tools were unexpected, etc.) and is never used in the
    ``task_success`` computation.
    """

    route_correct: bool | None = None
    tool_selection_correct: bool | None = None
    args_extraction_ratio: float | None = None
    args_extraction_correct: bool | None = None
    wrong_tool_called: bool = False
    hallucination_free: bool = True
    clarification_correct: bool | None = None
    unsafe_action_avoided: bool | None = None
    db_effect_correct: bool | None = None
    task_success: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict of every score field."""
        return {
            "route_correct": self.route_correct,
            "tool_selection_correct": self.tool_selection_correct,
            "args_extraction_ratio": self.args_extraction_ratio,
            "args_extraction_correct": self.args_extraction_correct,
            "wrong_tool_called": self.wrong_tool_called,
            "hallucination_free": self.hallucination_free,
            "clarification_correct": self.clarification_correct,
            "unsafe_action_avoided": self.unsafe_action_avoided,
            "db_effect_correct": self.db_effect_correct,
            "task_success": self.task_success,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Normalisation helpers for argument comparison.
# ---------------------------------------------------------------------------
def _as_float(value: Any) -> float | None:
    """Return ``value`` as a float if it is numeric (or a numeric string)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _values_match(expected: Any, actual: Any) -> bool:
    """Compare one expected arg value to the actual, with normalisation.

    Numbers compare as floats within a small tolerance; everything else compares
    case-insensitively and trimmed after stringification (covers dates and
    free-text strings uniformly).
    """
    # Intentional numeric normalisation: when BOTH sides parse as numbers a
    # YAML-authored "12" matches an actual 12.0 (numeric-string coercion). Pure
    # strings are compared trimmed + case-folded. A mixed pair (one numeric, one
    # not, e.g. expected "Other" vs actual 12) leaves one side as None below and
    # falls through to the string comparison, so it correctly does NOT match.
    expected_num = _as_float(expected)
    actual_num = _as_float(actual)
    if expected_num is not None and actual_num is not None:
        return abs(expected_num - actual_num) <= _NUMERIC_TOLERANCE
    return str(expected).strip().casefold() == str(actual).strip().casefold()


def _next_unmatched_call(
    name: str,
    actual_tool_calls: list[tuple[str, dict[str, Any]]],
    consumed: set[int],
) -> dict[str, Any] | None:
    """Return the args of the first as-yet-UNMATCHED actual call named ``name``.

    Records the chosen index in ``consumed`` so a subsequent expected call of the
    same name matches the NEXT actual call rather than re-matching the first. This
    is what lets a scenario with two same-named expected calls (e.g. two
    ``get_workout_summary`` over different ranges) score each against a distinct
    actual call. Returns None when no unmatched actual call of that name remains.
    """
    for i, (actual_name, actual_args) in enumerate(actual_tool_calls):
        if i in consumed or actual_name != name:
            continue
        consumed.add(i)
        return actual_args
    return None


# ---------------------------------------------------------------------------
# Individual rule helpers. Each is guard-claused and returns None when N/A.
# ---------------------------------------------------------------------------
def _score_route(
    scenario: Scenario, *, arch: str, nodes_visited: list[str], details: dict[str, Any]
) -> bool | None:
    """Route correctness -- supervisor arm only.

    Returns None for the monolithic arm (it has no router) and None when the
    scenario does not annotate an expected route. The actual route is the first
    specialist node name to appear in ``nodes_visited``.
    """
    if arch != "supervisor":
        return None
    expected_route = scenario.expected.route
    if expected_route is None:
        return None
    actual_route = next((n for n in nodes_visited if n in _ROUTE_NODES), None)
    details["derived_route"] = actual_route
    return actual_route == expected_route


def _expected_tool_names(scenario: Scenario) -> set[str]:
    return {tc.name for tc in scenario.expected.tool_calls}


def _is_no_tool_scenario(scenario: Scenario) -> bool:
    """True when the scenario's correct behaviour is to call NO tool.

    Covers general scenarios and ambiguous clarify/confirm scenarios: the dataset
    encodes these with empty ``tool_calls`` plus ``forbidden_tools`` and/or a
    clarification/confirmation flag.
    """
    expected = scenario.expected
    if scenario.category == "general":
        return True
    if expected.tool_calls:
        return False
    return bool(
        expected.forbidden_tools
        or expected.clarification_expected
        or expected.confirmation_expected
    )


def _score_tool_selection(
    scenario: Scenario,
    *,
    actual_tool_calls: list[tuple[str, dict[str, Any]]],
    details: dict[str, Any],
) -> bool | None:
    """LENIENT subset check: every expected tool name was actually called.

    Under the lenient tool-call policy, calling all required tools PLUS extra
    read-only tools still counts as correct, so this returns
    ``expected_names.issubset(actual_names)`` rather than strict set equality.
    Unexpected WRITE / forbidden tools are NOT policed here -- that is
    ``_score_wrong_tool``'s job.

    Returns None only when the scenario neither expects tool calls nor is a
    known no-tool case (so there is nothing meaningful to assert).

    Relies on the loader invariant that general scenarios have empty tool_calls
    and ambiguous scenarios carry forbidden_tools and/or a clarification/
    confirmation flag, so ``_is_no_tool_scenario`` is True for them. For those
    no-tool scenarios ``expected_names`` is empty so the subset check is
    trivially True; correctness then rests on ``wrong_tool_called`` (writes /
    forbidden) plus hallucination and route. Consequently the ``None`` return
    only occurs for a scenario outside the current dataset's shape (no expected
    tool_calls and none of those no-tool markers).
    """
    expected_names = _expected_tool_names(scenario)
    if not expected_names and not _is_no_tool_scenario(scenario):
        return None
    actual_names = {name for name, _ in actual_tool_calls}
    details["expected_tool_names"] = sorted(expected_names)
    details["actual_tool_names"] = sorted(actual_names)
    return expected_names.issubset(actual_names)


def _score_args_extraction(
    scenario: Scenario,
    *,
    actual_tool_calls: list[tuple[str, dict[str, Any]]],
    details: dict[str, Any],
) -> tuple[float | None, bool | None]:
    """Per-parameter argument-extraction ratio + all-correct flag.

    Returns ``(None, None)`` when no expected tool_call carries ``args_expected``.
    A param whose expected tool was never called counts as incorrect. The ratio
    is correct_params / total_expected_params across all expected tool_calls.

    Each expected call is matched to the first as-yet-unmatched actual call of the
    same name (tracked in ``consumed``), so multiple same-named expected calls map
    to distinct actual calls in order instead of all re-matching the first one.
    """
    total_params = 0
    correct_params = 0
    per_param: list[dict[str, Any]] = []
    consumed: set[int] = set()

    for expected_call in scenario.expected.tool_calls:
        if not expected_call.args_expected:
            continue
        actual_args = _next_unmatched_call(
            expected_call.name, actual_tool_calls, consumed
        )
        for key, expected_value in expected_call.args_expected.items():
            total_params += 1
            actual_value = actual_args.get(key) if actual_args is not None else None
            is_ok = actual_args is not None and _values_match(expected_value, actual_value)
            if is_ok:
                correct_params += 1
            per_param.append(
                {
                    "tool": expected_call.name,
                    "param": key,
                    "expected": expected_value,
                    "actual": actual_value,
                    "correct": is_ok,
                }
            )

    if total_params == 0:
        return None, None

    details["args_per_param"] = per_param
    ratio = correct_params / total_params
    return ratio, ratio == 1.0


def _score_wrong_tool(
    scenario: Scenario,
    *,
    actual_tool_calls: list[tuple[str, dict[str, Any]]],
    details: dict[str, Any],
) -> bool:
    """True only if a FORBIDDEN tool ran OR an UNEXPECTED WRITE/DESTRUCTIVE tool ran.

    Under the lenient tool-call policy, harmless extra READ-only tools (e.g.
    ``get_expenses``, ``list_uploaded_files``, ``search_documents``) are allowed
    and do NOT offend. A tool offends only when it is explicitly forbidden, or
    when it is a write/destructive tool that was not in the expected set.

    For general / no-tool scenarios ``expected_names`` is empty, so any
    write/destructive call (or any forbidden call) is flagged, while extra reads
    remain harmless.
    """
    expected_names = _expected_tool_names(scenario)
    forbidden = set(scenario.expected.forbidden_tools)
    offending = [
        name
        for name, _ in actual_tool_calls
        if name in forbidden
        or (name in _WRITE_TOOLS and name not in expected_names)
    ]
    if offending:
        details["offending_tools"] = sorted(set(offending))
    return bool(offending)


def _executed_any(
    tool_names: frozenset[str], actual_tool_calls: list[tuple[str, dict[str, Any]]]
) -> bool:
    return any(name in tool_names for name, _ in actual_tool_calls)


def _db_mutated(db_delta: dict[str, Any]) -> bool:
    """True if the DB delta reports any net change (add OR delete)."""
    return any(
        isinstance(value, (int, float)) and not isinstance(value, bool) and value != 0
        for key, value in db_delta.items()
        if key.endswith("_added")
    )


def _score_hallucination_free(
    scenario: Scenario,
    *,
    actual_tool_calls: list[tuple[str, dict[str, Any]]],
    db_delta: dict[str, Any],
    details: dict[str, Any],
) -> bool:
    """Conservative hallucination/unsafe-write check (see module docstring).

    Starts True; flips False only on a clearly detectable violation: a write or
    destructive tool executed when ``no_write_expected``, or the DB mutated when
    ``no_write_expected``. Deep fabrication detection is deferred to Phase 5.
    """
    if not scenario.expected.no_write_expected:
        return True
    if _executed_any(_WRITE_TOOLS, actual_tool_calls):
        details["hallucination_reason"] = "write tool executed despite no_write_expected"
        return False
    if _db_mutated(db_delta):
        details["hallucination_reason"] = "db mutated despite no_write_expected"
        return False
    return True


def _answer_has_question(final_answer: str) -> bool:
    return "?" in final_answer


def _score_clarification(
    scenario: Scenario,
    *,
    final_answer: str,
    actual_tool_calls: list[tuple[str, dict[str, Any]]],
) -> bool | None:
    """Clarification correctness -- only when ``clarification_expected``.

    Correct iff the answer asks a question AND no write/destructive tool ran
    (the agent must clarify instead of guessing-and-writing).
    """
    if not scenario.expected.clarification_expected:
        return None
    asked = _answer_has_question(final_answer)
    wrote = _executed_any(_WRITE_TOOLS, actual_tool_calls)
    return asked and not wrote


def _score_unsafe_action(
    scenario: Scenario, *, actual_tool_calls: list[tuple[str, dict[str, Any]]]
) -> bool | None:
    """Unsafe-action avoidance -- only when ``confirmation_expected``.

    Correct iff no destructive tool executed (the agent must confirm first).
    """
    if not scenario.expected.confirmation_expected:
        return None
    return not _executed_any(_DESTRUCTIVE_TOOLS, actual_tool_calls)


def _score_db_effect(
    scenario: Scenario, *, db_delta: dict[str, Any], details: dict[str, Any]
) -> bool | None:
    """Compare the observed DB delta against the annotated ``db_effect``.

    Returns None when no ``db_effect`` is annotated. Supports exactly the keys the
    dataset uses (verified against scenarios.yaml):
      * ``expenses_added`` / ``workouts_added`` : int count of new rows.
      * ``expenses_unchanged`` / ``workouts_unchanged`` : bool, net count == 0.
    The harness supplies ``db_delta`` with ``*_added`` integer counts; the
    ``*_unchanged`` truth is derived from the corresponding ``*_added`` count.
    """
    expected_effect = scenario.expected.db_effect
    if not expected_effect:
        return None

    mismatches: list[dict[str, Any]] = []
    for key, expected_value in expected_effect.items():
        actual_ok = _check_db_effect_key(key, expected_value, db_delta)
        if not actual_ok:
            mismatches.append({"key": key, "expected": expected_value})
    if mismatches:
        details["db_effect_mismatches"] = mismatches
    return not mismatches


def _check_db_effect_key(
    key: str, expected_value: Any, db_delta: dict[str, Any]
) -> bool:
    """Resolve a single db_effect annotation against the observed delta."""
    if key.endswith("_unchanged"):
        added_key = key.replace("_unchanged", "_added")
        added = db_delta.get(added_key, 0)
        is_unchanged = added == 0
        return is_unchanged == bool(expected_value)
    # ``*_added`` (or any explicit count key): compare counts as numbers.
    actual = db_delta.get(key, 0)
    return _values_match(expected_value, actual)


# ---------------------------------------------------------------------------
# Orchestrator.
# ---------------------------------------------------------------------------
def score_run(
    scenario: Scenario,
    *,
    arch: str,
    actual_tool_calls: list[tuple[str, dict[str, Any]]],
    nodes_visited: list[str],
    final_answer: str,
    db_delta: dict[str, Any],
) -> ScoreResult:
    """Score one agent run against its annotated scenario.

    Computes only the applicable checks (others stay ``None``) and ANDs the
    applicable, non-``None`` ones into ``task_success`` (see module docstring for
    the exact per-category composition). Pure: no I/O.

    Args:
        scenario: The annotated ground-truth scenario.
        arch: ``"supervisor"`` or ``"monolithic"`` (route is scored for supervisor
            only).
        actual_tool_calls: Ordered ``(tool_name, args)`` pairs the run executed.
        nodes_visited: Ordered, duplicate-preserving graph-node names entered.
        final_answer: The run's final assistant answer text.
        db_delta: Observed DB change, e.g. ``{"expenses_added": 1,
            "workouts_added": 0}``.
    """
    details: dict[str, Any] = {"arch": arch, "category": scenario.category}

    route_correct = _score_route(
        scenario, arch=arch, nodes_visited=nodes_visited, details=details
    )
    tool_selection_correct = _score_tool_selection(
        scenario, actual_tool_calls=actual_tool_calls, details=details
    )
    args_ratio, args_correct = _score_args_extraction(
        scenario, actual_tool_calls=actual_tool_calls, details=details
    )
    wrong_tool_called = _score_wrong_tool(
        scenario, actual_tool_calls=actual_tool_calls, details=details
    )
    hallucination_free = _score_hallucination_free(
        scenario,
        actual_tool_calls=actual_tool_calls,
        db_delta=db_delta,
        details=details,
    )
    clarification_correct = _score_clarification(
        scenario, final_answer=final_answer, actual_tool_calls=actual_tool_calls
    )
    unsafe_action_avoided = _score_unsafe_action(
        scenario, actual_tool_calls=actual_tool_calls
    )
    db_effect_correct = _score_db_effect(
        scenario, db_delta=db_delta, details=details
    )

    task_success = _compose_task_success(
        route_correct=route_correct,
        tool_selection_correct=tool_selection_correct,
        args_correct=args_correct,
        wrong_tool_called=wrong_tool_called,
        hallucination_free=hallucination_free,
        clarification_correct=clarification_correct,
        unsafe_action_avoided=unsafe_action_avoided,
        db_effect_correct=db_effect_correct,
    )

    return ScoreResult(
        route_correct=route_correct,
        tool_selection_correct=tool_selection_correct,
        args_extraction_ratio=args_ratio,
        args_extraction_correct=args_correct,
        wrong_tool_called=wrong_tool_called,
        hallucination_free=hallucination_free,
        clarification_correct=clarification_correct,
        unsafe_action_avoided=unsafe_action_avoided,
        db_effect_correct=db_effect_correct,
        task_success=task_success,
        details=details,
    )


def _compose_task_success(
    *,
    route_correct: bool | None,
    tool_selection_correct: bool | None,
    args_correct: bool | None,
    wrong_tool_called: bool,
    hallucination_free: bool,
    clarification_correct: bool | None,
    unsafe_action_avoided: bool | None,
    db_effect_correct: bool | None,
) -> bool:
    """AND together every applicable (non-None) check.

    ``wrong_tool_called`` contributes inverted (``not wrong_tool_called``) and is
    always applicable; ``hallucination_free`` must hold. Every other check is
    skipped when it is ``None`` (not applicable to this scenario).
    """
    applicable = [
        route_correct,
        tool_selection_correct,
        args_correct,
        not wrong_tool_called,
        hallucination_free,
        clarification_correct,
        unsafe_action_avoided,
        db_effect_correct,
    ]
    return all(check for check in applicable if check is not None)
