import uuid
from datetime import date

from sqlmodel import Session, select

from app.api.schemas.exercises import ExerciseCreate, ExerciseOut, WorkoutSessionOut
from app.db.database import ExerciseLog, WorkoutSession
from app.exceptions import InvalidIDError, NotFoundError


def _exercise_to_out(ex: ExerciseLog) -> ExerciseOut:
    return ExerciseOut(
        exercise_id=str(ex.id),
        name=ex.exercise_name,
        category=ex.category,
        duration=ex.duration_minutes,
        sets=ex.sets,
        reps=ex.reps,
        weight_kg=ex.weight_kg,
        distance_km=ex.distance_km,
    )


def _session_to_out(ws: WorkoutSession, exercises: list[ExerciseLog]) -> WorkoutSessionOut:
    return WorkoutSessionOut(
        session_id=str(ws.id),
        session_name=ws.session_name,
        date=ws.workout_date.isoformat(),
        exercises=[_exercise_to_out(ex) for ex in exercises],
    )


def list_workouts(
    db: Session,
    start_date: str,
    end_date: str,
) -> list[WorkoutSessionOut]:
    sessions = db.exec(
        select(WorkoutSession)
        .where(
            WorkoutSession.workout_date >= date.fromisoformat(start_date),
            WorkoutSession.workout_date <= date.fromisoformat(end_date),
        )
        .order_by(WorkoutSession.workout_date.desc())
    ).all()

    result: list[WorkoutSessionOut] = []
    for ws in sessions:
        exercises = db.exec(
            select(ExerciseLog).where(ExerciseLog.session_id == ws.id)
        ).all()
        result.append(_session_to_out(ws, exercises))
    return result


def create_exercise(db: Session, data: ExerciseCreate) -> ExerciseOut:
    parsed_date = date.fromisoformat(data.workout_date)

    ws = db.exec(
        select(WorkoutSession).where(
            WorkoutSession.workout_date == parsed_date,
            WorkoutSession.session_name == data.session_name,
        )
    ).first()

    if not ws:
        ws = WorkoutSession(session_name=data.session_name, workout_date=parsed_date)
        db.add(ws)
        db.commit()
        db.refresh(ws)

    exercise = ExerciseLog(
        session_id=ws.id,
        exercise_name=data.exercise_name,
        category=data.category,
        duration_minutes=data.duration_minutes,
        sets=data.sets,
        reps=data.reps,
        weight_kg=data.weight_kg,
        distance_km=data.distance_km,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)

    return _exercise_to_out(exercise)


def delete_exercise(db: Session, exercise_id: str) -> None:
    try:
        uid = uuid.UUID(exercise_id)
    except ValueError as exc:
        raise InvalidIDError(exercise_id) from exc

    exercise = db.get(ExerciseLog, uid)
    if not exercise:
        raise NotFoundError(exercise_id)

    db.delete(exercise)
    db.commit()
