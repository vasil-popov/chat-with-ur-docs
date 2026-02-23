# mcp_server/main.py
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
import uvicorn

from expenses.tools import (
    execute_log_expense, 
    execute_get_expenses,
    execute_delete_expense,       
    execute_get_spending_summary  
)

from exercises.tools import (
    execute_log_exercise,
    execute_get_workouts,
    execute_delete_exercise,
    execute_get_workout_summary
)

app = FastAPI(title="Life OS Tool Engine")
mcp = FastMCP("Life_OS_Tools")

# Expense tools
mcp.add_tool(execute_log_expense, name="log_expense")
mcp.add_tool(execute_get_expenses, name="get_expenses")
mcp.add_tool(execute_delete_expense, name="delete_expense")
mcp.add_tool(execute_get_spending_summary, name="get_spending_summary")

# Exercise tools
mcp.add_tool(execute_log_exercise, name="log_exercise")
mcp.add_tool(execute_get_workouts, name="get_workouts")
mcp.add_tool(execute_delete_exercise, name="delete_exercise")
mcp.add_tool(execute_get_workout_summary, name="get_workout_summary")

app.mount("/mcp", mcp.sse_app())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)