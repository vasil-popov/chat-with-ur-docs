# mcp_server/expense/tools.py
from database import engine, Expense
from sqlmodel import Session, select, func 
from datetime import date
import uuid
from typing import Optional, List, Dict

def execute_log_expense(amount: float, category: str, description: str, transaction_date: str) -> str:
    """
    Log a new financial expense to the database.
    
    Args:
        amount: The exact cost of the expense (e.g., 5.50)
        category: Broad category (e.g., 'Food', 'Fitness')
        description: Specific details (e.g., 'Protein shake')
        transaction_date: The date in YYYY-MM-DD format
    """
    try:
        parsed_date = date.fromisoformat(transaction_date)
        expense = Expense(
            amount=amount, 
            category=category, 
            description=description, 
            transaction_date=parsed_date
        )
        
        with Session(engine) as session:
            session.add(expense)
            session.commit()
            
        return f"Successfully logged {category} expense of ${amount:.2f}."
    except Exception as e:
        return f"Failed to log expense: {str(e)}"


def execute_get_expenses(start_date: str, end_date: str, category: Optional[str] = None) -> List[Dict]:
    """
    Retrieve expenses within a specific date range. 
    Use this to answer questions about past spending.
    
    Args:
        start_date: The beginning date in YYYY-MM-DD format
        end_date: The ending date in YYYY-MM-DD format
        category: (Optional) Filter by a specific category like 'Food' or 'Fitness'
    """
    try:
        s_date = date.fromisoformat(start_date)
        e_date = date.fromisoformat(end_date)
        
        with Session(engine) as session:
            statement = select(Expense).where(
                Expense.transaction_date >= s_date,
                Expense.transaction_date <= e_date
            )
            
            if category:
                # .ilike() makes it case-insensitive
                statement = statement.where(Expense.category.ilike(f"%{category}%"))
                
            results = session.exec(statement).all()
            
            # output format
            formatted_results = []
            for exp in results:
                formatted_results.append({
                    "id": str(exp.id),
                    "date": exp.transaction_date.isoformat(),
                    "amount": float(exp.amount),
                    "category": exp.category,
                    "description": exp.description
                })
                
            return formatted_results
            
    except Exception as e:
        return [{"error": f"Failed to retrieve expenses: {str(e)}"}]
    
def execute_delete_expense(expense_id: str) -> str:
    """
    Delete a specific expense from the database using its unique ID.
    If you don't know the ID, use get_expenses first to find it.
    
    Args:
        expense_id: The UUID string of the expense to delete.
    """
    try:
        valid_uuid = uuid.UUID(expense_id)
        
        with Session(engine) as session:
            expense = session.get(Expense, valid_uuid)
            
            if not expense:
                return f"Error: No expense found with ID {expense_id}."
            
            session.delete(expense)
            session.commit()
            
            return f"Successfully deleted the {expense.category} expense for {expense.amount}."
            
    except ValueError:
        return "Error: Invalid ID format. Please use get_expenses to find the exact UUID."
    except Exception as e:
        return f"Failed to delete expense: {str(e)}"
    
def execute_get_spending_summary(start_date: str, end_date: str) -> Dict[str, float]:
    """
    Get a summary of total spending grouped by category for a specific date range.
    Use this to answer questions like "How much did I spend on X this month?"
    
    Args:
        start_date: The beginning date in YYYY-MM-DD format
        end_date: The ending date in YYYY-MM-DD format
    """
    try:
        s_date = date.fromisoformat(start_date)
        e_date = date.fromisoformat(end_date)
        
        with Session(engine) as session:
            # we sum spending by category
            statement = select(
                Expense.category, 
                func.sum(Expense.amount).label("total_amount")
            ).where(
                Expense.transaction_date >= s_date,
                Expense.transaction_date <= e_date
            ).group_by(Expense.category)
            
            results = session.exec(statement).all()
            
            summary = {}
            for row in results:
                summary[row[0]] = float(row[1])
                
            return summary
            
    except Exception as e:
        return {"error": f"Failed to calculate summary: {str(e)}"}
