import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.database import ExerciseLog, WorkoutSession, get_session

router = APIRouter()


class ExerciseCreate(BaseModel):
    exercise_name: str
    category: str
    workout_date: str
    session_name: str = "Daily Workout"
    duration_minutes: Optional[int] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    distance_km: Optional[float] = None


class ExerciseOut(BaseModel):
    exercise_id: str
    name: str
    category: str
    duration: Optional[int]
    sets: Optional[int]
    reps: Optional[int]
    weight_kg: Optional[float]
    distance_km: Optional[float]


class WorkoutSessionOut(BaseModel):
    session_id: str
    session_name: str
    date: str
    exercises: List[ExerciseOut]


@router.get("", response_model=List[WorkoutSessionOut])
def list_workouts(
    start_date: str,
    end_date: str,
    db: Session = Depends(get_session),
):
    sessions = db.exec(
        select(WorkoutSession)
        .where(
            WorkoutSession.workout_date >= date.fromisoformat(start_date),
            WorkoutSession.workout_date <= date.fromisoformat(end_date),
        )
        .order_by(WorkoutSession.workout_date.desc())
    ).all()

    result = []
    for ws in sessions:
        exercises = db.exec(
            select(ExerciseLog).where(ExerciseLog.session_id == ws.id)
        ).all()
        result.append(
            WorkoutSessionOut(
                session_id=str(ws.id),
                session_name=ws.session_name,
                date=ws.workout_date.isoformat(),
                exercises=[
                    ExerciseOut(
                        exercise_id=str(ex.id),
                        name=ex.exercise_name,
                        category=ex.category,
                        duration=ex.duration_minutes,
                        sets=ex.sets,
                        reps=ex.reps,
                        weight_kg=ex.weight_kg,
                        distance_km=ex.distance_km,
                    )
                    for ex in exercises
                ],
            )
        )
    return result


@router.post("", status_code=201)
def create_exercise(data: ExerciseCreate, db: Session = Depends(get_session)):
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

    return ExerciseOut(
        exercise_id=str(exercise.id),
        name=exercise.exercise_name,
        category=exercise.category,
        duration=exercise.duration_minutes,
        sets=exercise.sets,
        reps=exercise.reps,
        weight_kg=exercise.weight_kg,
        distance_km=exercise.distance_km,
    )


@router.delete("/{exercise_id}", status_code=204)
def delete_exercise(exercise_id: str, db: Session = Depends(get_session)):
    try:
        uid = uuid.UUID(exercise_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid exercise ID")

    exercise = db.get(ExerciseLog, uid)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    db.delete(exercise)
    db.commit()
