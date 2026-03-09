# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from langchain.agents import create_agent
from datetime import date
import asyncio
import os
import logging
from app.deps.dependency_container import di_container_instance
from app.deps.dependency_factory import get_llm_client, get_mcp_client

import logging
import sys

# Configure logging to write to stdout immediately
logging.basicConfig(
    stream=sys.stdout, 
    level=logging.DEBUG
)

load_dotenv("../.env")

#imports
#MLFLOW tracing
#ENV Vars


@asynccontextmanager
async def lifespan(app: FastAPI):
    #logging setup
    #DB startup
    #Any services to be reused throughout the app
    #Any instances to be reused.. (llm, embedding, chat engines..)
    #DI container variables from a factory
    #app.state.var_name
    #yield
    #shutdown process started dispose of db engine etc

    logging.info("Starting LangChain Orchestrator...")
    logging.info("Connecting to Finance MCP Server...")

    di_container_instance.mcp_server_client = get_mcp_client()
    di_container_instance.llm_client = get_llm_client()

    tools = await di_container_instance.mcp_server_client.get_tools()
    logging.info(f"Loaded tools: {[t.name for t in tools]}")


    today = date.today().isoformat()
    system_prompt = f"You are a helpful personal assistant. Today's exact date is {today}."

    di_container_instance.agent_instance = create_agent(di_container_instance.llm_client, tools, system_prompt=system_prompt)
    
    yield

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="Life OS LangChain Backend")

    @app.get("/healthz", tags=["health"])
    async def health() -> dict[str, str]: 
        return {"status": "ok"}

    try:
        
        from app.api.router import api_router
        app.include_router(api_router, prefix="/api")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"], # Your Next.js URL
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    except Exception as e:
        logging.warning("Api router not loaded: %s", e)

    return app

app = create_app()