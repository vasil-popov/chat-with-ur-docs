import asyncio
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from datetime import date
from langchain.agents import create_agent
from dotenv import load_dotenv
from pathlib import Path

current_file = Path(__file__)
env = current_file.parents[2] / ".env"
expenses_mcp = "C:/Users/vasil/Desktop/Diplomna/chat-with-ur-docs/backend/mcp servers/expenses/server.py"

load_dotenv(env)

async def main():
    print("Starting LangChain Orchestrator...")
    
    # 1. Configure the MCP Client
    mcp_client = MultiServerMCPClient({
        "finance_server": {
            "url": "http://localhost:8000/mcp",
            "transport": "http",
        }
    })
    
    # 2. Load the tools
    # Notice we removed the 'async with mcp_client:' block!
    print("Connecting to Finance MCP Server...")
    tools = await mcp_client.get_tools()
    print(f"Loaded tools: {[t.name for t in tools]}")
    
    # 3. Initialize Gemini Flash
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview", 
        temperature=0 
    )

    today = date.today().isoformat()
    system_prompt = f"You are a helpful personal assistant. Today's exact date is {today}."
    
    # 4. Create the Agent
    agent = create_agent(llm, tools, system_prompt=system_prompt)
    
    # 5. Send the test prompt!
    prompt = "I paid 20 euro for gas today"
    print(f"\nUser: {prompt}\n")
    print("Agent is thinking...\n")
    
    # Execute the agent
    response = await agent.ainvoke({"messages": [("user", prompt)]})
    
    # 6. Print the entire conversation history
    for msg in response["messages"]:
        msg.pretty_print()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    asyncio.run(main())