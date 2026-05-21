from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.schemas.exercises import ExerciseCreate, ExerciseOut, WorkoutSessionOut
from app.db.database import get_session
from app.exceptions import InvalidIDError, NotFoundError
from app.services import exercise_service

router = APIRouter()


@router.get("", response_model=List[WorkoutSessionOut])
def list_workouts(
    start_date: str,
    end_date: str,
    db: Session = Depends(get_session),
):
    return exercise_service.list_workouts(db, start_date, end_date)


@router.post("", response_model=ExerciseOut, status_code=201)
def create_exercise(data: ExerciseCreate, db: Session = Depends(get_session)):
    return exercise_service.create_exercise(db, data)


@router.delete("/{exercise_id}", status_code=204)
def delete_exercise(exercise_id: str, db: Session = Depends(get_session)):
    try:
        exercise_service.delete_exercise(db, exercise_id)
    except InvalidIDError:
        raise HTTPException(status_code=400, detail="Invalid exercise ID")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Exercise not found")
