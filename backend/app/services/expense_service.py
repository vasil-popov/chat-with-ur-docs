import uuid
from datetime import date

from sqlmodel import Session, select

from app.api.schemas.expenses import ExpenseCreate, ExpenseOut, ExpenseUpdate
from app.db.database import Expense
from app.exceptions import InvalidIDError, NotFoundError


def _to_out(e: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=str(e.id),
        date=e.transaction_date.isoformat(),
        amount=e.amount,
        category=e.category,
        description=e.description,
    )


def list_expenses(
    db: Session,
    start_date: str,
    end_date: str,
    category: str | None,
) -> list[ExpenseOut]:
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


def create_expense(db: Session, data: ExpenseCreate) -> ExpenseOut:
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


def update_expense(db: Session, expense_id: str, data: ExpenseUpdate) -> ExpenseOut:
    try:
        uid = uuid.UUID(expense_id)
    except ValueError as exc:
        raise InvalidIDError(expense_id) from exc

    expense = db.get(Expense, uid)
    if not expense:
        raise NotFoundError(expense_id)

    expense.amount = data.amount
    expense.category = data.category
    expense.description = data.description
    expense.transaction_date = date.fromisoformat(data.transaction_date)

    db.add(expense)
    db.commit()
    db.refresh(expense)
    return _to_out(expense)


def delete_expense(db: Session, expense_id: str) -> None:
    try:
        uid = uuid.UUID(expense_id)
    except ValueError as exc:
        raise InvalidIDError(expense_id) from exc

    expense = db.get(Expense, uid)
    if not expense:
        raise NotFoundError(expense_id)

    db.delete(expense)
    db.commit()


def bulk_create_expenses(db: Session, items: list[ExpenseCreate]) -> list[ExpenseOut]:
    created: list[ExpenseOut] = []
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
