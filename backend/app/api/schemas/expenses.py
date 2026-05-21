from typing import Optional

from pydantic import BaseModel


class ExpenseCreate(BaseModel):
    amount: float
    category: str
    description: Optional[str] = None
    transaction_date: str


class ExpenseUpdate(BaseModel):
    amount: float
    category: str
    description: Optional[str] = None
    transaction_date: str


class ExpenseOut(BaseModel):
    id: str
    date: str
    amount: float
    category: str
    description: Optional[str]
