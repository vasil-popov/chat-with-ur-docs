from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

# ---------------------------------------------------------------------------
# Known tool inventory. These MUST match the registered MCP tool names
# (mcp_server/main.py) and the LangChain RAG tool names
# (backend/app/tools/rag_tools.py) verbatim. A scenario referencing any other
# name is rejected at load time.
# ---------------------------------------------------------------------------
TRACKING_TOOLS: frozenset[str] = frozenset(
    {
        "log_expense",
        "get_expenses",
        "delete_expense",
        "get_spending_summary",
        "log_exercise",
        "get_workouts",
        "delete_exercise",
        "get_workout_summary",
    }
)
RAG_TOOLS: frozenset[str] = frozenset(
    {
        "search_documents",
        "list_uploaded_files",
        "get_file_summary",
    }
)
KNOWN_TOOLS: frozenset[str] = TRACKING_TOOLS | RAG_TOOLS

ScenarioCategory = Literal["tracking", "rag", "general", "multi_domain", "ambiguous"]
RouteName = Literal["tracking", "rag", "general"]


# ---------------------------------------------------------------------------
# Seed sub-models. These mirror the DB fields in app.db.database so the seeder
# can construct rows directly from validated scenario data.
# ---------------------------------------------------------------------------
class SeedExpense(BaseModel):
    """A row to insert into ``expenses`` before a scenario runs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: float
    category: str
    description: str | None = None
    transaction_date: date
    # Optional stable handle so the harness can reference the seeded id later
    # (e.g. "delete my last expense" scenarios). Resolved to a real UUID by the
    # seeder; the value here is just a lookup key local to the scenario.
    ref: str | None = None


class SeedWorkout(BaseModel):
    """A workout session + single exercise to seed before a scenario runs.

    Mirrors the ``log_exercise`` find-or-create behaviour: one row in
    ``workout_sessions`` and one row in ``exercise_logs``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_name: str = "Daily Workout"
    workout_date: date
    exercise_name: str
    category: str
    duration_minutes: int | None = None
    sets: int | None = None
    reps: int | None = None
    weight_kg: float | None = None
    distance_km: float | None = None
    ref: str | None = None


class SeedFile(BaseModel):
    """An ``uploaded_files`` row to seed for RAG scenarios.

    ``extracted_text`` carries the sample document content so RAG tools have
    real, known text to read. ``status`` defaults to ``"ready"`` so the file is
    treated as processed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    original_name: str
    extracted_text: str
    category: str = "document"
    file_type: str = "txt"
    mime_type: str = "text/plain"
    file_path: str = "eval://seeded"
    size_bytes: int = 0
    status: str = "ready"
    is_receipt: bool = False
    ref: str | None = None


class ScenarioSetup(BaseModel):
    """Rows to seed before a scenario runs. All sections default to empty."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    expenses: tuple[SeedExpense, ...] = ()
    workouts: tuple[SeedWorkout, ...] = ()
    files: tuple[SeedFile, ...] = ()

    def is_empty(self) -> bool:
        """Return True when nothing needs to be seeded for this scenario."""
        return not (self.expenses or self.workouts or self.files)


# ---------------------------------------------------------------------------
# Expected-outcome models (the ground truth the scorer compares against).
# ---------------------------------------------------------------------------
class ToolCall(BaseModel):
    """One expected tool invocation with per-parameter ground-truth args.

    ``args_expected`` holds the values the agent MUST extract from the user
    message. The downstream scorer checks these per parameter, so only the
    parameters that constitute correctness need be listed (e.g. an expense's
    amount/category/date) - not every optional parameter.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    args_expected: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _name_must_be_known(self) -> ToolCall:
        if self.name not in KNOWN_TOOLS:
            raise ValueError(
                f"Unknown tool name {self.name!r} in tool_calls. "
                f"Known tools: {sorted(KNOWN_TOOLS)}"
            )
        return self


class ExpectedOutcome(BaseModel):
    """The annotated expected result for a single scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    route: RouteName | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    clarification_expected: bool = False
    confirmation_expected: bool = False
    no_write_expected: bool = False
    db_effect: dict[str, Any] = Field(default_factory=dict)
    reference_answer: str
    answer_points: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _forbidden_tools_must_be_known(self) -> ExpectedOutcome:
        unknown = [t for t in self.forbidden_tools if t not in KNOWN_TOOLS]
        if unknown:
            raise ValueError(
                f"Unknown tool name(s) {unknown} in forbidden_tools. "
                f"Known tools: {sorted(KNOWN_TOOLS)}"
            )
        return self

    @model_validator(mode="after")
    def _ask_or_confirm_implies_no_write(self) -> ExpectedOutcome:
        if (self.clarification_expected or self.confirmation_expected) and not self.no_write_expected:
            raise ValueError(
                "clarification_expected/confirmation_expected require "
                "no_write_expected=true (asking or confirming must not write)."
            )
        return self


class Scenario(BaseModel):
    """A single annotated benchmark scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    category: ScenarioCategory
    message: str
    history: tuple[Any, ...] = ()
    file_ids: tuple[str, ...] = ()
    setup: ScenarioSetup = Field(default_factory=ScenarioSetup)
    expected: ExpectedOutcome

    @model_validator(mode="after")
    def _general_scenarios_use_no_tools(self) -> Scenario:
        if self.category == "general":
            if self.expected.route != "general":
                raise ValueError(
                    f"Scenario {self.id!r}: general scenarios must route to "
                    f"'general' (got {self.expected.route!r})."
                )
            if self.expected.tool_calls:
                raise ValueError(
                    f"Scenario {self.id!r}: general scenarios must have empty "
                    "tool_calls."
                )
        return self


class Dataset(BaseModel):
    """The full parsed dataset: a fixed reference date plus its scenarios."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_date: date
    scenarios: tuple[Scenario, ...]

    @model_validator(mode="after")
    def _ids_must_be_unique(self) -> Dataset:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for scenario in self.scenarios:
            if scenario.id in seen:
                duplicates.add(scenario.id)
            seen.add(scenario.id)
        if duplicates:
            raise ValueError(f"Duplicate scenario id(s): {sorted(duplicates)}")
        return self


DEFAULT_SCENARIOS_PATH = Path(__file__).with_name("scenarios.yaml")


def load_dataset(path: str | Path = DEFAULT_SCENARIOS_PATH) -> Dataset:
    """Load and validate the full dataset (reference_date + scenarios).

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        ValueError: if the YAML is malformed or any scenario fails validation.
            The wrapped Pydantic error message names the offending field.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Scenario file not found: {file_path}")

    raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(
            f"Scenario file must be a mapping with 'reference_date' and "
            f"'scenarios' keys, got {type(raw).__name__}."
        )

    try:
        return Dataset.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid scenario dataset in {file_path}:\n{exc}") from exc


def load_scenarios(path: str | Path = DEFAULT_SCENARIOS_PATH) -> list[Scenario]:
    """Load, validate, and return just the list of scenarios.

    Convenience wrapper over :func:`load_dataset` for callers that only need the
    scenarios. Use :func:`load_dataset` when you also need ``reference_date``.
    """
    return list(load_dataset(path).scenarios)
