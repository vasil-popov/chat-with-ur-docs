from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.schemas.expenses import ExpenseCreate, ExpenseOut, ExpenseUpdate
from app.db.database import get_session
from app.exceptions import InvalidIDError, NotFoundError
from app.services import expense_service

router = APIRouter()


@router.get("", response_model=List[ExpenseOut])
def list_expenses(
    start_date: str,
    end_date: str,
    category: Optional[str] = None,
    db: Session = Depends(get_session),
):
    return expense_service.list_expenses(db, start_date, end_date, category)


@router.post("", response_model=ExpenseOut, status_code=201)
def create_expense(data: ExpenseCreate, db: Session = Depends(get_session)):
    return expense_service.create_expense(db, data)


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: str, data: ExpenseUpdate, db: Session = Depends(get_session)):
    try:
        return expense_service.update_expense(db, expense_id, data)
    except InvalidIDError:
        raise HTTPException(status_code=400, detail="Invalid expense ID")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Expense not found")


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: str, db: Session = Depends(get_session)):
    try:
        expense_service.delete_expense(db, expense_id)
    except InvalidIDError:
        raise HTTPException(status_code=400, detail="Invalid expense ID")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Expense not found")


@router.post("/bulk", response_model=List[ExpenseOut], status_code=201)
def bulk_create_expenses(items: List[ExpenseCreate], db: Session = Depends(get_session)):
    return expense_service.bulk_create_expenses(db, items)
