from sqlmodel import SQLModel, Field, Session, create_engine
from datetime import date
from typing import Optional
import uuid
from dotenv import load_dotenv
import os
from pathlib import Path


load_dotenv(".env")

POSTGRE_USER = os.getenv("POSTGRE_USER")
POSTGRE_PASS = os.getenv("POSTGRE_PASS")
POSTGRE_IP = os.getenv("POSTGRE_IP", "127.0.0.1")
POSTGRE_PORT = os.getenv("POSTGRE_PORT", "5432")
POSTGRE_DB_NAME = os.getenv("POSTGRE_DB_NAME")

class Expense(SQLModel, table=True):
    __tablename__ = "expenses"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    amount: float = Field(nullable=False)
    category: str = Field(nullable=False, max_length=50)
    description: Optional[str] = Field(default=None)
    transaction_date: date = Field(index=True)

class WorkoutSession(SQLModel, table=True):
    """The overall workout event (The Parent)"""
    __tablename__ = "workout_sessions"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_name: str = Field(nullable=False, max_length=100) # e.g., "Push Day", "5K Run"
    workout_date: date = Field(index=True)

class ExerciseLog(SQLModel, table=True):
    """The individual movements within a session (The Child)"""
    __tablename__ = "exercise_logs"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    
    session_id: uuid.UUID = Field(foreign_key="workout_sessions.id", index=True)
    
    exercise_name: str = Field(nullable=False, max_length=100) 
    category: str = Field(nullable=False, max_length=50) 
    
    duration_minutes: Optional[int] = Field(default=None)
    
    # Strength Metrics
    sets: Optional[int] = Field(default=None)
    reps: Optional[int] = Field(default=None)
    weight_kg: Optional[float] = Field(default=None)
    
    # Cardio Metrics
    distance_km: Optional[float] = Field(default=None)

DATABASE_URL = f"postgresql://{POSTGRE_USER}:{POSTGRE_PASS}@{POSTGRE_IP}:{POSTGRE_PORT}/{POSTGRE_DB_NAME}"

# Echo for debug
engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    # create the tables in Postgres if they do not exist
    SQLModel.metadata.create_all(engine)

if __name__ == "__main__":
    init_db()
    print("Database tables created successfully!")