from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, delete

# We import the canonical models here on purpose. `create_engine` in that module
# is lazy (no connection opens at import), seed.py only ever uses the guarded eval
# engine, and every destructive path asserts the eval-DB name -- so importing the
# production models is safe and avoids MetaData table-name collisions that
# duplicating the classes would cause.
from app.db.database import Expense, ExerciseLog, UploadedFile, WorkoutSession
from app.evaluation.dataset.loader import Scenario

# The eval-DB name check is case-insensitive (compares `db_name.lower()`), so this
# marker must stay lowercase.
EVAL_DB_NAME_MARKER = "eval"

# Teardown order respects foreign keys: child rows (exercise_logs reference
# workout_sessions) are deleted before their parents.
_TEARDOWN_MODELS: tuple[type[SQLModel], ...] = (
    ExerciseLog,
    WorkoutSession,
    Expense,
    UploadedFile,
)


@dataclass
class SeededIds:
    """UUIDs created when seeding one scenario, keyed by the scenario's `ref`.

    The harness uses these to resolve ``<ref:...>`` placeholders in expected
    tool args (e.g. the seeded expense id for a delete scenario, or the seeded
    file id for a RAG scenario).
    """

    expense_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    workout_session_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    exercise_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    file_ids: dict[str, uuid.UUID] = field(default_factory=dict)


def _build_eval_database_url() -> tuple[str, str]:
    """Construct the eval DATABASE_URL from EVAL_POSTGRE_* env vars.

    Returns:
        A ``(database_url, database_name)`` tuple.

    Raises:
        RuntimeError: if any required EVAL_POSTGRE_* variable is missing.
    """
    user = os.getenv("EVAL_POSTGRE_USER")
    password = os.getenv("EVAL_POSTGRE_PASS")
    host = os.getenv("EVAL_POSTGRE_IP")
    port = os.getenv("EVAL_POSTGRE_PORT")
    db_name = os.getenv("EVAL_POSTGRE_DB_NAME")

    missing = [
        name
        for name, value in (
            ("EVAL_POSTGRE_USER", user),
            ("EVAL_POSTGRE_PASS", password),
            ("EVAL_POSTGRE_IP", host),
            ("EVAL_POSTGRE_PORT", port),
            ("EVAL_POSTGRE_DB_NAME", db_name),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required eval DB environment variable(s): {missing}. "
            "The eval seeder never falls back to production POSTGRE_* vars."
        )

    url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    return url, str(db_name)


def _assert_eval_database(db_name: str) -> None:
    """Refuse to operate on any database whose name does not contain "eval".

    This is the hard guard that prevents seeding or truncating production.

    Raises:
        RuntimeError: if ``db_name`` is empty or lacks the ``"eval"`` marker.
    """
    if not db_name or EVAL_DB_NAME_MARKER not in db_name.lower():
        raise RuntimeError(
            f"Refusing to seed/teardown a non-eval database: {db_name!r}. "
            f"The database name must contain {EVAL_DB_NAME_MARKER!r}."
        )


def get_eval_engine() -> Engine:
    """Create a fresh engine bound to the validated eval database.

    The eval-name guard runs here so no engine pointed at production is ever
    handed out.

    Raises:
        RuntimeError: if env vars are missing or the DB name is not an eval DB.
    """
    url, db_name = _build_eval_database_url()
    _assert_eval_database(db_name)
    return create_engine(url, echo=False)


def ensure_tables(engine: Engine | None = None) -> None:
    """Create all SQLModel tables in the eval database if they do not exist."""
    eval_engine = engine or get_eval_engine()
    # Guard applies to caller-supplied engines too -- never trust the passed engine.
    _assert_eval_database(str(eval_engine.url.database))
    SQLModel.metadata.create_all(eval_engine)


def _seed_expenses(session: Session, scenario: Scenario, seeded: SeededIds) -> None:
    for row in scenario.setup.expenses:
        expense = Expense(
            amount=row.amount,
            category=row.category,
            description=row.description,
            transaction_date=row.transaction_date,
        )
        session.add(expense)
        session.flush()  # populate the server-side default id
        if row.ref:
            seeded.expense_ids[row.ref] = expense.id


def _seed_workouts(session: Session, scenario: Scenario, seeded: SeededIds) -> None:
    """Seed each workout as one session + one exercise (mirrors log_exercise)."""
    for row in scenario.setup.workouts:
        workout_session = WorkoutSession(
            session_name=row.session_name,
            workout_date=row.workout_date,
        )
        session.add(workout_session)
        session.flush()

        exercise = ExerciseLog(
            session_id=workout_session.id,
            exercise_name=row.exercise_name,
            category=row.category,
            duration_minutes=row.duration_minutes,
            sets=row.sets,
            reps=row.reps,
            weight_kg=row.weight_kg,
            distance_km=row.distance_km,
        )
        session.add(exercise)
        session.flush()
        if row.ref:
            seeded.workout_session_ids[row.ref] = workout_session.id
            seeded.exercise_ids[row.ref] = exercise.id


def _seed_files(session: Session, scenario: Scenario, seeded: SeededIds) -> None:
    for row in scenario.setup.files:
        uploaded = UploadedFile(
            original_name=row.original_name,
            file_path=row.file_path,
            file_type=row.file_type,
            mime_type=row.mime_type,
            category=row.category,
            # An explicit `size_bytes: 0` is treated as "unset" and replaced by the
            # computed byte length (Python falsy semantics) -- intentional for
            # convenience so scenarios rarely need to specify a size.
            size_bytes=row.size_bytes or len(row.extracted_text.encode("utf-8")),
            status=row.status,
            extracted_text=row.extracted_text,
            is_receipt=row.is_receipt,
        )
        session.add(uploaded)
        session.flush()
        if row.ref:
            seeded.file_ids[row.ref] = uploaded.id


def seed_scenario(scenario: Scenario, engine: Engine | None = None) -> SeededIds:
    """Insert a scenario's ``setup`` rows into the eval database.

    Returns the UUIDs of any rows that carried a ``ref`` handle so the harness
    can resolve ``<ref:...>`` placeholders in expected tool args.

    Raises:
        RuntimeError: if the target database is not an eval database.
    """
    eval_engine = engine or get_eval_engine()
    # Guard applies to caller-supplied engines too -- never trust the passed engine.
    _assert_eval_database(str(eval_engine.url.database))
    seeded = SeededIds()

    if scenario.setup.is_empty():
        return seeded

    with Session(eval_engine) as session:
        _seed_expenses(session, scenario, seeded)
        _seed_workouts(session, scenario, seeded)
        _seed_files(session, scenario, seeded)
        session.commit()

    return seeded


def teardown(engine: Engine | None = None) -> None:
    """Delete ALL rows from the eval tables, leaving no residue between runs.

    Respects FK order (exercise_logs before workout_sessions).

    Raises:
        RuntimeError: if the target database is not an eval database.
    """
    eval_engine = engine or get_eval_engine()
    # Guard applies to caller-supplied engines too -- never trust the passed engine.
    _assert_eval_database(str(eval_engine.url.database))
    with Session(eval_engine) as session:
        for model in _TEARDOWN_MODELS:
            session.exec(delete(model))
        session.commit()
