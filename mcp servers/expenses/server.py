from mcp.server.fastmcp import FastMCP
from sqlmodel import Session
from datetime import date
from database import engine, Expense

mcp = FastMCP("Finance")

@mcp.tool()
def log_expense(amount: float, category: str, description: str, transaction_date: str) -> str:
    """
    Log a new financial expense to the database.
    
    Args:
        amount: The exact cost of the expense (e.g., 5.50)
        category: Broad category (e.g., 'Food', 'Fitness', 'Transport')
        description: Specific details extracted from the user (e.g., 'Protein shake')
        transaction_date: The date the expense occurred in YYYY-MM-DD format
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
            
        return f"Successfully logged {category} expense of ${amount:.2f} for {description}."
    
    except ValueError:
        return "Error: transaction_date must be in YYYY-MM-DD format."
    except Exception as e:
        return f"Failed to log expense: {str(e)}"

if __name__ == "__main__":

    mcp.run()