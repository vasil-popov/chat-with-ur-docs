from typing import List, Optional

from pydantic import BaseModel


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
