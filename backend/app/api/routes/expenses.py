import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.database import Expense, get_session

router = APIRouter()


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


def _to_out(e: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=str(e.id),
        date=e.transaction_date.isoformat(),
        amount=e.amount,
        category=e.category,
        description=e.description,
    )


@router.get("", response_model=List[ExpenseOut])
def list_expenses(
    start_date: str,
    end_date: str,
    category: Optional[str] = None,
    db: Session = Depends(get_session),
):
    stmt = (
        select(Expense)
        .where(
            Expense.transaction_date >= date.fromisoformat(start_date),
            Expense.transaction_date <= date.fromisoformat(end_date),
        )
        .order_by(Expense.transaction_date.desc())
    )
    if category:
        stmt = stmt.where(Expense.category.ilike(f"%{category}%"))
    return [_to_out(e) for e in db.exec(stmt).all()]


@router.post("", response_model=ExpenseOut, status_code=201)
def create_expense(data: ExpenseCreate, db: Session = Depends(get_session)):
    expense = Expense(
        amount=data.amount,
        category=data.category,
        description=data.description,
        transaction_date=date.fromisoformat(data.transaction_date),
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return _to_out(expense)


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: str, data: ExpenseUpdate, db: Session = Depends(get_session)):
    try:
        uid = uuid.UUID(expense_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expense ID")

    expense = db.get(Expense, uid)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    expense.amount = data.amount
    expense.category = data.category
    expense.description = data.description
    expense.transaction_date = date.fromisoformat(data.transaction_date)

    db.add(expense)
    db.commit()
    db.refresh(expense)
    return _to_out(expense)


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: str, db: Session = Depends(get_session)):
    try:
        uid = uuid.UUID(expense_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expense ID")

    expense = db.get(Expense, uid)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    db.delete(expense)
    db.commit()


@router.post("/bulk", response_model=List[ExpenseOut], status_code=201)
def bulk_create_expenses(items: List[ExpenseCreate], db: Session = Depends(get_session)):
    created = []
    for data in items:
        expense = Expense(
            amount=data.amount,
            category=data.category,
            description=data.description,
            transaction_date=date.fromisoformat(data.transaction_date),
        )
        db.add(expense)
        db.flush()
        created.append(_to_out(expense))
    db.commit()
    return created
