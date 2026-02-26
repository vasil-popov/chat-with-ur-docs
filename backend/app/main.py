# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from datetime import date
import asyncio
import os
import logging

#imports
#MLFLOW tracing
#ENV Vars


@asynccontextmanager
async def lifespan(app: FastAPI):
    #logging setup
    #DB startup
    #Any services to be reused throughout the app
    #Any instances to be reused.. (llm, embedding, chat engines..)
    load_dotenv("../.env")

    logging.info("Starting LangChain Orchestrator...")

    logging.info("Connecting to Finance MCP Server...")
    mcp_client = MultiServerMCPClient({
        "finance_server": {
            "url": "http://localhost:8000/mcp",
            "transport": "http",
        }
    })

    tools = await mcp_client.get_tools()
    logging.info(f"Loaded tools: {[t.name for t in tools]}")

    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview", 
        temperature=0 
    )

    today = date.today().isoformat()
    system_prompt = f"You are a helpful personal assistant. Today's exact date is {today}."

    agent = create_agent(llm, tools, system_prompt=system_prompt)
    yield

app = FastAPI(lifespan=lifespan, title="Life OS LangChain Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Your Next.js URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


