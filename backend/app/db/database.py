import os
import uuid
from datetime import date, datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Session, create_engine

POSTGRE_USER = os.getenv("POSTGRE_USER")
POSTGRE_PASS = os.getenv("POSTGRE_PASS")
POSTGRE_IP = os.getenv("POSTGRE_IP", "127.0.0.1")
POSTGRE_PORT = os.getenv("POSTGRE_PORT", "5432")
POSTGRE_DB_NAME = os.getenv("POSTGRE_DB_NAME")

DATABASE_URL = f"postgresql://{POSTGRE_USER}:{POSTGRE_PASS}@{POSTGRE_IP}:{POSTGRE_PORT}/{POSTGRE_DB_NAME}"

engine = create_engine(DATABASE_URL, echo=False)


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    amount: float = Field(nullable=False)
    category: str = Field(nullable=False, max_length=50)
    description: Optional[str] = Field(default=None)
    transaction_date: date = Field(index=True)


class WorkoutSession(SQLModel, table=True):
    __tablename__ = "workout_sessions"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_name: str = Field(nullable=False, max_length=100)
    workout_date: date = Field(index=True)


class ExerciseLog(SQLModel, table=True):
    __tablename__ = "exercise_logs"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="workout_sessions.id", index=True)
    exercise_name: str = Field(nullable=False, max_length=100)
    category: str = Field(nullable=False, max_length=50)
    duration_minutes: Optional[int] = Field(default=None)
    sets: Optional[int] = Field(default=None)
    reps: Optional[int] = Field(default=None)
    weight_kg: Optional[float] = Field(default=None)
    distance_km: Optional[float] = Field(default=None)


class UploadedFile(SQLModel, table=True):
    __tablename__ = "uploaded_files"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    original_name: str = Field(max_length=255)
    file_path: str = Field(max_length=512)
    file_type: str = Field(max_length=20)   # 'image'|'pdf'|'txt'|'excel'
    mime_type: str = Field(max_length=100)
    category: str = Field(default="general", max_length=50)
    size_bytes: int
    status: str = Field(default="processing")  # 'processing'|'ready'|'error'
    extracted_text: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    is_receipt: bool = Field(default=False)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = Field(default=None)


def get_session():
    with Session(engine) as session:
        yield session
