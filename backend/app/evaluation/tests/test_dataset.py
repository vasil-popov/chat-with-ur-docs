"""Unit tests for the golden benchmark dataset loader and seed safety guard.

These run with NO live LLM and NO live database. They cover:
  * the bundled scenarios.yaml parses and meets coverage (>=5 per category);
  * malformed inputs raise clear errors (duplicate id, unknown tool name,
    clarification without no_write, bad category, general-with-tools);
  * the seed safety guard refuses any database whose name lacks "eval".
"""

from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.evaluation.dataset import seed
from app.evaluation.dataset.loader import (
    KNOWN_TOOLS,
    ScenarioSetup,
    SeedExpense,
    SeedFile,
    SeedWorkout,
    load_dataset,
    load_scenarios,
)

DATASET_PATH = Path(__file__).resolve().parents[1] / "dataset" / "scenarios.yaml"
CATEGORIES = ("tracking", "rag", "general", "multi_domain", "ambiguous")
MIN_PER_CATEGORY = 5


def _write_yaml(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "scenarios.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


class TestBundledDataset:
    def test_bundled_dataset_loads(self) -> None:
        dataset = load_dataset(DATASET_PATH)
        assert dataset.reference_date.isoformat() == "2026-06-03"
        assert len(dataset.scenarios) >= MIN_PER_CATEGORY * len(CATEGORIES)

    def test_at_least_five_per_category(self) -> None:
        scenarios = load_scenarios(DATASET_PATH)
        for category in CATEGORIES:
            count = sum(1 for s in scenarios if s.category == category)
            assert count >= MIN_PER_CATEGORY, f"{category} has only {count}"

    def test_all_referenced_tools_are_known(self) -> None:
        for scenario in load_scenarios(DATASET_PATH):
            for call in scenario.expected.tool_calls:
                assert call.name in KNOWN_TOOLS
            for forbidden in scenario.expected.forbidden_tools:
                assert forbidden in KNOWN_TOOLS

    def test_ask_or_confirm_scenarios_are_no_write(self) -> None:
        for scenario in load_scenarios(DATASET_PATH):
            exp = scenario.expected
            if exp.clarification_expected or exp.confirmation_expected:
                assert exp.no_write_expected


class TestMalformedInputs:
    def test_duplicate_id_raises(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
            reference_date: "2026-06-03"
            scenarios:
              - id: dup-001
                category: general
                message: "hi"
                expected:
                  route: general
                  reference_answer: "greets"
              - id: dup-001
                category: general
                message: "hello"
                expected:
                  route: general
                  reference_answer: "greets"
            """,
        )
        with pytest.raises(ValueError, match="Duplicate scenario id"):
            load_dataset(path)

    def test_unknown_tool_name_raises(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
            reference_date: "2026-06-03"
            scenarios:
              - id: bad-tool-001
                category: tracking
                message: "log it"
                expected:
                  route: tracking
                  tool_calls:
                    - name: not_a_real_tool
                      args_expected: {amount: 5.0}
                  reference_answer: "logs"
            """,
        )
        with pytest.raises(ValueError, match="Unknown tool name"):
            load_dataset(path)

    def test_clarification_without_no_write_raises(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
            reference_date: "2026-06-03"
            scenarios:
              - id: bad-clarify-001
                category: ambiguous
                message: "log 20 for yesterday"
                expected:
                  route: tracking
                  clarification_expected: true
                  no_write_expected: false
                  reference_answer: "asks for category"
            """,
        )
        with pytest.raises(ValueError, match="no_write_expected"):
            load_dataset(path)

    def test_unknown_category_raises(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
            reference_date: "2026-06-03"
            scenarios:
              - id: bad-cat-001
                category: nonsense
                message: "hi"
                expected:
                  route: general
                  reference_answer: "x"
            """,
        )
        with pytest.raises(ValueError):
            load_dataset(path)

    def test_general_with_tool_calls_raises(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
            reference_date: "2026-06-03"
            scenarios:
              - id: bad-general-001
                category: general
                message: "hi"
                expected:
                  route: general
                  tool_calls:
                    - name: log_expense
                      args_expected: {amount: 1.0}
                  reference_answer: "x"
            """,
        )
        with pytest.raises(ValueError, match="empty"):
            load_dataset(path)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_dataset(tmp_path / "does_not_exist.yaml")


class TestSeedSafetyGuard:
    def test_assert_rejects_non_eval_name(self) -> None:
        with pytest.raises(RuntimeError, match="non-eval database"):
            seed._assert_eval_database("production_db")

    def test_assert_rejects_empty_name(self) -> None:
        with pytest.raises(RuntimeError, match="non-eval database"):
            seed._assert_eval_database("")

    def test_assert_accepts_eval_name(self) -> None:
        seed._assert_eval_database("life_os_eval")  # must not raise

    def test_get_eval_engine_refuses_non_eval_db(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EVAL_POSTGRE_USER", "u")
        monkeypatch.setenv("EVAL_POSTGRE_PASS", "p")
        monkeypatch.setenv("EVAL_POSTGRE_IP", "127.0.0.1")
        monkeypatch.setenv("EVAL_POSTGRE_PORT", "5432")
        monkeypatch.setenv("EVAL_POSTGRE_DB_NAME", "production")
        with pytest.raises(RuntimeError, match="non-eval database"):
            seed.get_eval_engine()

    def test_get_eval_engine_requires_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in (
            "EVAL_POSTGRE_USER",
            "EVAL_POSTGRE_PASS",
            "EVAL_POSTGRE_IP",
            "EVAL_POSTGRE_PORT",
            "EVAL_POSTGRE_DB_NAME",
        ):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(RuntimeError, match="Missing required eval DB"):
            seed.get_eval_engine()

    def test_teardown_rejects_caller_supplied_non_eval_engine(self) -> None:
        # A caller passing a production engine directly must still be rejected by
        # the guard, before any Session is opened. The engine never connects
        # because the guard raises first.
        production_engine = create_engine(
            "postgresql://u:p@h:5432/life-tracker"
        )
        with pytest.raises(RuntimeError, match="non-eval database"):
            seed.teardown(engine=production_engine)


class TestScenarioSetupIsEmpty:
    def test_default_setup_is_empty(self) -> None:
        assert ScenarioSetup().is_empty() is True

    def test_setup_with_expenses_is_not_empty(self) -> None:
        setup = ScenarioSetup(
            expenses=(
                SeedExpense(
                    amount=5.0,
                    category="Food",
                    transaction_date=date(2026, 6, 3),
                ),
            )
        )
        assert setup.is_empty() is False

    def test_setup_with_workouts_is_not_empty(self) -> None:
        setup = ScenarioSetup(
            workouts=(
                SeedWorkout(
                    workout_date=date(2026, 6, 3),
                    exercise_name="Running",
                    category="Cardio",
                ),
            )
        )
        assert setup.is_empty() is False

    def test_setup_with_files_is_not_empty(self) -> None:
        setup = ScenarioSetup(
            files=(
                SeedFile(original_name="doc.txt", extracted_text="hello"),
            )
        )
        assert setup.is_empty() is False


class TestReferenceDateWeekWindow:
    def test_reference_date_falls_in_documented_iso_week(self) -> None:
        # The YAML documents reference_date 2026-06-03 as a Wednesday inside the
        # ISO Mon-Sun "this week" window 2026-06-01..2026-06-07. Assert this so
        # the week-window assumption fails loudly if the date is ever changed
        # inconsistently.
        reference_date = load_dataset(DATASET_PATH).reference_date
        assert reference_date == date(2026, 6, 3)
        assert date(2026, 6, 1) <= reference_date <= date(2026, 6, 7)
        assert reference_date.isoweekday() == 3  # Wednesday
