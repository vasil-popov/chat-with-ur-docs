from sqlmodel import SQLModel, Field, Session, create_engine
from datetime import date
from typing import Optional
import uuid
from dotenv import load_dotenv
import os
from pathlib import Path

current_file = Path(__file__)
env = current_file.parents[2] / ".env"

load_dotenv(env)

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


DATABASE_URL = f"postgresql://{POSTGRE_USER}:{POSTGRE_PASS}@{POSTGRE_IP}:{POSTGRE_PORT}/{POSTGRE_DB_NAME}"

# echo for debug
engine = create_engine(DATABASE_URL, echo=True)

def init_db():
    #create the tables in Postgres if they do not exist
    SQLModel.metadata.create_all(engine)

if __name__ == "__main__":
    init_db()
    print("Database tables created successfully!")