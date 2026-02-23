# mcp_server/exercises/tools.py
from database import engine, WorkoutSession, ExerciseLog
from sqlmodel import Session, select, func
from datetime import date
import uuid
from typing import Optional, List, Dict

def execute_log_exercise(
    exercise_name: str, 
    category: str, 
    workout_date: str, 
    session_name: str = "Daily Workout", 
    duration_minutes: Optional[int] = None,
    sets: Optional[int] = None,
    reps: Optional[int] = None,
    weight_kg: Optional[float] = None,
    distance_km: Optional[float] = None
) -> str:
    """
    Log a single exercise movement. If a workout session for this date 
    already exists, it will automatically append to it.
    
    Args:
        exercise_name: The specific movement (e.g., 'Bench Press', 'Running')
        category: Broad category ('Strength', 'Cardio', etc.)
        workout_date: Date in YYYY-MM-DD format
        session_name: The overarching workout name (e.g., 'Leg Day', 'Morning Run'). 
                      Defaults to 'Daily Workout' if not specified.
        ... (metrics)
    """
    try:
        parsed_date = date.fromisoformat(workout_date)
        
        with Session(engine) as session:
            # FIND OR CREATE THE PARENT SESSION
            statement = select(WorkoutSession).where(
                WorkoutSession.workout_date == parsed_date,
                WorkoutSession.session_name == session_name
            )
            workout_session = session.exec(statement).first()
            
            # If it doesn't exist, create it
            if not workout_session:
                workout_session = WorkoutSession(
                    session_name=session_name, 
                    workout_date=parsed_date
                )
                session.add(workout_session)
                session.commit()
                session.refresh(workout_session)
                
            # CREATE THE CHILD EXERCISE LOG
            exercise_log = ExerciseLog(
                session_id=workout_session.id, # Link to the parent
                exercise_name=exercise_name,
                category=category,
                duration_minutes=duration_minutes,
                sets=sets,
                reps=reps,
                weight_kg=weight_kg,
                distance_km=distance_km
            )
            
            session.add(exercise_log)
            session.commit()
            
            return f"Successfully logged {exercise_name} to '{session_name}' on {workout_date}."
            
    except Exception as e:
        return f"Failed to log exercise: {str(e)}"
    
def execute_get_workouts(start_date: str, end_date: str) -> List[Dict]:
    """
    Retrieve all workout sessions and their specific exercises within a date range.
    
    Args:
        start_date: The beginning date in YYYY-MM-DD format
        end_date: The ending date in YYYY-MM-DD format
    """
    try:
        s_date = date.fromisoformat(start_date)
        e_date = date.fromisoformat(end_date)
        
        with Session(engine) as session:
            # Get the Parent Sessions
            statement = select(WorkoutSession).where(
                WorkoutSession.workout_date >= s_date,
                WorkoutSession.workout_date <= e_date
            )
            sessions = session.exec(statement).all()
            
            result = []
            for ws in sessions:
                # For each session, get the Child Exercises
                ex_statement = select(ExerciseLog).where(ExerciseLog.session_id == ws.id)
                exercises = session.exec(ex_statement).all()
                
                session_data = {
                    "session_id": str(ws.id),
                    "session_name": ws.session_name,
                    "date": ws.workout_date.isoformat(),
                    "exercises": []
                }
                
                for ex in exercises:
                    session_data["exercises"].append({
                        "exercise_id": str(ex.id),
                        "name": ex.exercise_name,
                        "category": ex.category,
                        "duration": ex.duration_minutes,
                        "sets": ex.sets,
                        "reps": ex.reps,
                        "weight_kg": ex.weight_kg,
                        "distance_km": ex.distance_km
                    })
                
                result.append(session_data)
                
            return result
    except Exception as e:
        return [{"error": f"Failed to retrieve workouts: {str(e)}"}]
    
def execute_delete_exercise(exercise_id: str) -> str:
    """
    Delete a specific exercise log from the database using its unique ID.
    Use get_workouts first to find the exact exercise_id.
    
    Args:
        exercise_id: The UUID string of the exercise log to delete.
    """
    try:
        valid_uuid = uuid.UUID(exercise_id)
        
        with Session(engine) as session:
            exercise = session.get(ExerciseLog, valid_uuid)
            
            if not exercise:
                return f"Error: No exercise found with ID {exercise_id}."
            
            name = exercise.exercise_name
            session.delete(exercise)
            session.commit()
            
            return f"Successfully deleted the exercise: {name}."
            
    except ValueError:
        return "Error: Invalid ID format. Use get_workouts to find the exact UUID."
    except Exception as e:
        return f"Failed to delete exercise: {str(e)}"
    
def execute_get_workout_summary(start_date: str, end_date: str) -> Dict[str, float]:
    """
    Get a high-level summary of fitness metrics (total distance, total duration)
    for a given date range.
    
    Args:
        start_date: The beginning date in YYYY-MM-DD format
        end_date: The ending date in YYYY-MM-DD format
    """
    try:
        s_date = date.fromisoformat(start_date)
        e_date = date.fromisoformat(end_date)
        
        with Session(engine) as session:
            # table join to filter exercises by the parent session date
            statement = select(
                func.sum(ExerciseLog.duration_minutes).label("total_duration"),
                func.sum(ExerciseLog.distance_km).label("total_distance")
            ).join(WorkoutSession).where(
                WorkoutSession.workout_date >= s_date,
                WorkoutSession.workout_date <= e_date
            )
            
            result = session.exec(statement).first()
            
            return {
                "total_duration_minutes": float(result[0] or 0),
                "total_distance_km": float(result[1] or 0)
            }
            
    except Exception as e:
        return {"error": f"Failed to calculate workout summary: {str(e)}"}