"""Unit tests for the rule-based scorer (no live LLM, no DB).

Scenarios are constructed directly via the loader's Pydantic models so the tests
exercise the exact ground-truth shapes the live harness feeds the scorer. Each
test asserts the specific check it targets AND the resulting ``task_success`` so
the assertions are non-vacuous.
"""

from __future__ import annotations

from app.evaluation.dataset.loader import (
    ExpectedOutcome,
    Scenario,
    ToolCall,
)
from app.evaluation.scorer import score_run


def _scenario(
    *,
    category: str,
    expected: ExpectedOutcome,
    message: str = "test message",
) -> Scenario:
    return Scenario.model_validate(
        {
            "id": f"test-{category}",
            "category": category,
            "message": message,
            "expected": expected.model_dump(),
        }
    )


class TestPerfectTrackingRun:
    def test_all_applicable_checks_pass_and_task_succeeds(self) -> None:
        scenario = _scenario(
            category="tracking",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(
                        name="log_expense",
                        args_expected={
                            "amount": 12.5,
                            "category": "Fitness",
                            "transaction_date": "2026-06-03",
                        },
                    ),
                ),
                db_effect={"expenses_added": 1},
                reference_answer="Logs the expense.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[
                (
                    "log_expense",
                    {
                        "amount": 12.50,
                        "category": "fitness",  # case-insensitive match
                        "transaction_date": "2026-06-03",
                    },
                )
            ],
            nodes_visited=["supervisor", "tracking", "supervisor"],
            final_answer="Done, I logged your 12.50 Fitness expense.",
            db_delta={"expenses_added": 1, "workouts_added": 0},
        )

        assert result.route_correct is True
        assert result.tool_selection_correct is True
        assert result.args_extraction_ratio == 1.0
        assert result.args_extraction_correct is True
        assert result.wrong_tool_called is False
        assert result.hallucination_free is True
        assert result.db_effect_correct is True
        assert result.task_success is True


class TestWrongRoute:
    def test_wrong_route_fails_task(self) -> None:
        scenario = _scenario(
            category="tracking",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(name="log_expense", args_expected={"amount": 8.0}),
                ),
                db_effect={"expenses_added": 1},
                reference_answer="Logs the expense.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[("log_expense", {"amount": 8.0})],
            nodes_visited=["supervisor", "general", "supervisor"],
            final_answer="ok",
            db_delta={"expenses_added": 1},
        )

        assert result.route_correct is False
        assert result.task_success is False

    def test_route_not_scored_for_monolithic(self) -> None:
        scenario = _scenario(
            category="tracking",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(name="log_expense", args_expected={"amount": 8.0}),
                ),
                db_effect={"expenses_added": 1},
                reference_answer="Logs the expense.",
            ),
        )

        result = score_run(
            scenario,
            arch="monolithic",
            actual_tool_calls=[("log_expense", {"amount": 8.0})],
            nodes_visited=["agent", "tools", "agent"],
            final_answer="ok",
            db_delta={"expenses_added": 1},
        )

        assert result.route_correct is None
        assert result.task_success is True


class TestArgsMismatch:
    def test_partial_args_fail_extraction_and_task(self) -> None:
        scenario = _scenario(
            category="tracking",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(
                        name="log_expense",
                        args_expected={
                            "amount": 12.5,
                            "category": "Fitness",
                            "transaction_date": "2026-06-03",
                        },
                    ),
                ),
                db_effect={"expenses_added": 1},
                reference_answer="Logs the expense.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[
                (
                    "log_expense",
                    {
                        "amount": 99.0,  # wrong
                        "category": "Fitness",
                        "transaction_date": "2026-06-03",
                    },
                )
            ],
            nodes_visited=["supervisor", "tracking"],
            final_answer="logged",
            db_delta={"expenses_added": 1},
        )

        assert result.args_extraction_ratio == 2 / 3
        assert result.args_extraction_correct is False
        assert result.task_success is False

    def test_uncalled_expected_tool_counts_params_incorrect(self) -> None:
        scenario = _scenario(
            category="tracking",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(
                        name="log_exercise",
                        args_expected={"exercise_name": "Running", "duration_minutes": 30},
                    ),
                ),
                db_effect={"workouts_added": 1},
                reference_answer="Logs the workout.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[],  # never called the expected tool
            nodes_visited=["supervisor", "tracking"],
            final_answer="hm",
            db_delta={"workouts_added": 0},
        )

        assert result.args_extraction_ratio == 0.0
        assert result.args_extraction_correct is False
        assert result.task_success is False


class TestForbiddenTool:
    def test_forbidden_tool_flags_wrong_tool_and_fails(self) -> None:
        scenario = _scenario(
            category="ambiguous",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(),
                forbidden_tools=("log_expense",),
                clarification_expected=True,
                no_write_expected=True,
                db_effect={"expenses_unchanged": True},
                reference_answer="Asks for the category.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[("log_expense", {"amount": 20.0, "category": "Other"})],
            nodes_visited=["supervisor", "tracking"],
            final_answer="I logged 20 under Other.",
            db_delta={"expenses_added": 1},
        )

        assert result.wrong_tool_called is True
        assert result.task_success is False


class TestClarification:
    def test_agent_asked_and_did_not_write_is_correct(self) -> None:
        scenario = _scenario(
            category="ambiguous",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(),
                forbidden_tools=("log_expense",),
                clarification_expected=True,
                no_write_expected=True,
                db_effect={"expenses_unchanged": True},
                reference_answer="Asks for the category.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Which category should I file this 20 BGN under?",
            db_delta={"expenses_added": 0},
        )

        assert result.clarification_correct is True
        assert result.wrong_tool_called is False
        assert result.hallucination_free is True
        assert result.db_effect_correct is True
        assert result.task_success is True

    def test_agent_guessed_and_wrote_is_incorrect(self) -> None:
        scenario = _scenario(
            category="ambiguous",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(),
                forbidden_tools=("log_expense",),
                clarification_expected=True,
                no_write_expected=True,
                db_effect={"expenses_unchanged": True},
                reference_answer="Asks for the category.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[("log_expense", {"amount": 20.0, "category": "Other"})],
            nodes_visited=["supervisor", "tracking"],
            final_answer="I logged 20 BGN under Other for you.",
            db_delta={"expenses_added": 1},
        )

        assert result.clarification_correct is False
        assert result.hallucination_free is False
        assert result.task_success is False


class TestConfirmationBeforeDelete:
    def test_delete_executed_flags_unsafe_and_fails(self) -> None:
        scenario = _scenario(
            category="ambiguous",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(),
                forbidden_tools=("delete_expense",),
                confirmation_expected=True,
                no_write_expected=True,
                db_effect={"expenses_unchanged": True},
                reference_answer="Asks to confirm before deleting.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[("delete_expense", {"expense_id": "abc"})],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Deleted your last expense.",
            db_delta={"expenses_added": 0},
        )

        assert result.unsafe_action_avoided is False
        assert result.wrong_tool_called is True
        assert result.task_success is False

    def test_no_delete_is_safe(self) -> None:
        scenario = _scenario(
            category="ambiguous",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(),
                forbidden_tools=("delete_expense",),
                confirmation_expected=True,
                no_write_expected=True,
                db_effect={"expenses_unchanged": True},
                reference_answer="Asks to confirm before deleting.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Are you sure you want to delete your last expense?",
            db_delta={"expenses_added": 0},
        )

        assert result.unsafe_action_avoided is True
        assert result.task_success is True


class TestDbEffect:
    def test_db_effect_matched(self) -> None:
        scenario = _scenario(
            category="multi_domain",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(name="log_expense", args_expected={"amount": 60.0}),
                    ToolCall(name="log_exercise", args_expected={"exercise_name": "Running"}),
                ),
                db_effect={"expenses_added": 1, "workouts_added": 1},
                reference_answer="Logs both.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[
                ("log_expense", {"amount": 60.0}),
                ("log_exercise", {"exercise_name": "Running"}),
            ],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Logged both.",
            db_delta={"expenses_added": 1, "workouts_added": 1},
        )

        assert result.db_effect_correct is True
        assert result.task_success is True

    def test_db_effect_unchanged_violated(self) -> None:
        scenario = _scenario(
            category="tracking",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(
                        name="get_spending_summary",
                        args_expected={"start_date": "2026-06-01", "end_date": "2026-06-07"},
                    ),
                ),
                no_write_expected=True,
                db_effect={"expenses_unchanged": True},
                reference_answer="Reads the summary.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[
                (
                    "get_spending_summary",
                    {"start_date": "2026-06-01", "end_date": "2026-06-07"},
                )
            ],
            nodes_visited=["supervisor", "tracking"],
            final_answer="You spent 25 BGN on Food this week.",
            db_delta={"expenses_added": 1},  # something wrote -> unchanged violated
        )

        assert result.db_effect_correct is False
        assert result.task_success is False


class TestGeneralScenario:
    def test_tool_call_in_general_is_wrong_and_fails(self) -> None:
        scenario = _scenario(
            category="general",
            expected=ExpectedOutcome(
                route="general",
                tool_calls=(),
                forbidden_tools=("get_expenses",),
                no_write_expected=True,
                reference_answer="Friendly reply, no tools.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[("get_expenses", {"category": "Food"})],
            nodes_visited=["supervisor", "general"],
            final_answer="Here are your expenses.",
            db_delta={"expenses_added": 0},
        )

        # Under the lenient subset policy, an empty expected set makes
        # tool_selection trivially True; correctness rests on wrong_tool_called.
        # ``get_expenses`` is FORBIDDEN here, so it still offends and the task
        # fails -- safety is preserved.
        assert result.tool_selection_correct is True
        assert result.wrong_tool_called is True
        assert result.task_success is False

    def test_clean_general_reply_succeeds(self) -> None:
        scenario = _scenario(
            category="general",
            expected=ExpectedOutcome(
                route="general",
                tool_calls=(),
                no_write_expected=True,
                reference_answer="Friendly reply, no tools.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[],
            nodes_visited=["supervisor", "general"],
            final_answer="I'm doing great, thanks for asking!",
            db_delta={"expenses_added": 0, "workouts_added": 0},
        )

        assert result.tool_selection_correct is True
        assert result.wrong_tool_called is False
        assert result.task_success is True


class TestRagScenario:
    def test_rag_read_scored_correctly_with_no_db_effect(self) -> None:
        scenario = _scenario(
            category="rag",
            expected=ExpectedOutcome(
                route="rag",
                tool_calls=(
                    ToolCall(
                        name="search_documents",
                        args_expected={"query": "vacation policy"},
                    ),
                ),
                no_write_expected=True,
                reference_answer="Summarises the vacation policy from the document.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[("search_documents", {"query": "vacation policy"})],
            nodes_visited=["supervisor", "rag", "supervisor"],
            final_answer="The policy grants 20 paid days per year.",
            db_delta={"expenses_added": 0, "workouts_added": 0, "files_added": 0},
        )

        assert result.route_correct is True
        assert result.tool_selection_correct is True
        assert result.args_extraction_ratio == 1.0
        assert result.args_extraction_correct is True
        assert result.wrong_tool_called is False
        assert result.hallucination_free is True
        # No db_effect annotated for a pure RAG read -> the check is N/A.
        assert result.db_effect_correct is None
        assert result.task_success is True


class TestMonolithicMultiDomain:
    def test_route_not_scored_for_monolithic_while_others_apply(self) -> None:
        scenario = _scenario(
            category="multi_domain",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(name="log_expense", args_expected={"amount": 60.0}),
                    ToolCall(
                        name="log_exercise", args_expected={"exercise_name": "Running"}
                    ),
                ),
                db_effect={"expenses_added": 1, "workouts_added": 1},
                reference_answer="Logs both.",
            ),
        )

        result = score_run(
            scenario,
            arch="monolithic",
            actual_tool_calls=[
                ("log_expense", {"amount": 60.0}),
                ("log_exercise", {"exercise_name": "Running"}),
            ],
            nodes_visited=["agent", "tools", "agent"],
            final_answer="Logged both your expense and workout.",
            db_delta={"expenses_added": 1, "workouts_added": 1},
        )

        # Monolithic has no router, so routing is never scored.
        assert result.route_correct is None
        # Every other applicable check still applies and passes.
        assert result.tool_selection_correct is True
        assert result.args_extraction_correct is True
        assert result.db_effect_correct is True
        assert result.task_success is True


class TestMultipleSameNamedCalls:
    """Regression for FIX 2: same-named expected calls match distinct actuals."""

    @staticmethod
    def _two_summary_scenario() -> Scenario:
        return _scenario(
            category="multi_domain",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(
                        name="get_workout_summary",
                        args_expected={
                            "start_date": "2026-05-01",
                            "end_date": "2026-05-31",
                        },
                    ),
                    ToolCall(
                        name="get_workout_summary",
                        args_expected={
                            "start_date": "2026-06-01",
                            "end_date": "2026-06-30",
                        },
                    ),
                ),
                no_write_expected=True,
                reference_answer="Compares May vs June workouts.",
            ),
        )

    def test_in_order_calls_score_all_args_correct(self) -> None:
        scenario = self._two_summary_scenario()

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[
                (
                    "get_workout_summary",
                    {"start_date": "2026-05-01", "end_date": "2026-05-31"},
                ),
                (
                    "get_workout_summary",
                    {"start_date": "2026-06-01", "end_date": "2026-06-30"},
                ),
            ],
            nodes_visited=["supervisor", "tracking"],
            final_answer="You trained more in June than in May.",
            db_delta={"expenses_added": 0, "workouts_added": 0},
        )

        # Under the OLD first-match logic both expected calls would compare
        # against the first actual call, so the second range would mismatch and
        # the ratio would drop below 1.0. The unmatched-consumption fix matches
        # them positionally, so every param is correct.
        assert result.args_extraction_ratio == 1.0
        assert result.args_extraction_correct is True

    def test_swapped_or_wrong_arg_drops_ratio_below_one(self) -> None:
        scenario = self._two_summary_scenario()

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[
                (
                    "get_workout_summary",
                    {"start_date": "2026-06-01", "end_date": "2026-06-30"},
                ),
                (
                    "get_workout_summary",
                    {"start_date": "2026-05-01", "end_date": "2026-05-31"},
                ),
            ],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Compared the wrong way round.",
            db_delta={"expenses_added": 0, "workouts_added": 0},
        )

        # Both ranges are present but in the wrong order, so positional matching
        # makes every one of the four params mismatch.
        assert result.args_extraction_ratio < 1.0
        assert result.args_extraction_correct is False


class TestDeleteUnderNoWrite:
    """Regression for FIX 1: a negative delta is a mutation, not 'unchanged'."""

    def test_delete_flagged_as_hallucination_under_no_write(self) -> None:
        scenario = _scenario(
            category="tracking",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(
                        name="get_expenses",
                        args_expected={"category": "Food"},
                    ),
                ),
                no_write_expected=True,
                db_effect={"expenses_unchanged": True},
                reference_answer="Reads expenses without modifying anything.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[("get_expenses", {"category": "Food"})],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Here are your Food expenses.",
            # A row was deleted: negative delta. Under the old ``value > 0`` guard
            # this was NOT treated as a mutation, leaving hallucination_free True.
            db_delta={"expenses_added": -1},
        )

        assert result.hallucination_free is False
        assert result.task_success is False


class TestLenientToolPolicy:
    """FIX 3: extra READ-only tools are tolerated; only forbidden or unexpected
    write/destructive tools offend."""

    def test_extra_read_alongside_expected_is_correct(self) -> None:
        scenario = _scenario(
            category="tracking",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(name="log_expense", args_expected={"amount": 12.5}),
                ),
                db_effect={"expenses_added": 1},
                reference_answer="Logs the expense.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[
                # An extra harmless read alongside the expected write.
                ("get_expenses", {"category": "Food"}),
                ("log_expense", {"amount": 12.5}),
            ],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Logged your 12.50 expense.",
            db_delta={"expenses_added": 1},
        )

        # Subset check: expected tool present despite the extra read.
        assert result.tool_selection_correct is True
        # Extra read does not offend under the lenient policy.
        assert result.wrong_tool_called is False
        assert result.task_success is True

    def test_unexpected_write_tool_offends(self) -> None:
        scenario = _scenario(
            category="tracking",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(name="log_expense", args_expected={"amount": 12.5}),
                ),
                db_effect={"expenses_added": 1},
                reference_answer="Logs the expense.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[
                ("log_expense", {"amount": 12.5}),
                # An unexpected WRITE not in the expected set.
                ("log_exercise", {"exercise_name": "Running"}),
            ],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Logged both.",
            db_delta={"expenses_added": 1, "workouts_added": 1},
        )

        assert result.wrong_tool_called is True
        assert result.details["offending_tools"] == ["log_exercise"]
        assert result.task_success is False

    def test_forbidden_destructive_tool_still_offends(self) -> None:
        scenario = _scenario(
            category="ambiguous",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(),
                forbidden_tools=("delete_expense",),
                confirmation_expected=True,
                no_write_expected=True,
                db_effect={"expenses_unchanged": True},
                reference_answer="Asks to confirm before deleting.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[("delete_expense", {"expense_id": "abc"})],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Deleted your last expense.",
            db_delta={"expenses_added": -1},
        )

        assert result.wrong_tool_called is True
        assert result.unsafe_action_avoided is False
        assert result.db_effect_correct is False
        assert result.task_success is False

    def test_multi_tool_with_extra_read_can_succeed(self) -> None:
        scenario = _scenario(
            category="multi_domain",
            expected=ExpectedOutcome(
                route="tracking",
                tool_calls=(
                    ToolCall(name="log_expense", args_expected={"amount": 60.0}),
                    ToolCall(
                        name="log_exercise", args_expected={"exercise_name": "Running"}
                    ),
                ),
                db_effect={"expenses_added": 1, "workouts_added": 1},
                reference_answer="Logs both.",
            ),
        )

        result = score_run(
            scenario,
            arch="supervisor",
            actual_tool_calls=[
                ("log_expense", {"amount": 60.0}),
                ("log_exercise", {"exercise_name": "Running"}),
                # An extra harmless read does not break success.
                ("get_workout_summary", {"start_date": "2026-06-01"}),
            ],
            nodes_visited=["supervisor", "tracking"],
            final_answer="Logged both your expense and workout.",
            db_delta={"expenses_added": 1, "workouts_added": 1},
        )

        assert result.tool_selection_correct is True
        assert result.wrong_tool_called is False
        assert result.args_extraction_correct is True
        assert result.db_effect_correct is True
        assert result.task_success is True
