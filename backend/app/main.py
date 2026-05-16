import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv("../.env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sqlmodel import SQLModel
    from app.db.database import engine
    from app.deps.dependency_container import di_container_instance
    from app.deps.dependency_factory import get_llm_client, get_mcp_client
    from app.services import embedding_service
    from app.services.agents import build_graph
    from app.tools.rag_tools import search_documents, list_uploaded_files, get_file_summary

    os.makedirs("uploads", exist_ok=True)

    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)

    logger.info("Initializing PGVector vectorstore...")
    try:
        embedding_service.get_vectorstore()
    except Exception as e:
        logger.warning("PGVector init warning (non-fatal): %s", e)

    logger.info("Connecting to MCP server...")
    di_container_instance.mcp_server_client = get_mcp_client()
    di_container_instance.llm_client = get_llm_client()

    mcp_tools = await di_container_instance.mcp_server_client.get_tools()
    logger.info("Loaded MCP tools: %s", [t.name for t in mcp_tools])

    rag_tools = [search_documents, list_uploaded_files, get_file_summary]

    graph = build_graph(di_container_instance.llm_client, mcp_tools, rag_tools)
    di_container_instance.agent_instance = graph

    logger.info("LangGraph Supervisor ready.")
    yield
    logger.info("Shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="Life OS Backend")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["health"])
    async def health() -> dict:
        return {"status": "ok"}

    try:
        from app.api.router import api_router
        app.include_router(api_router, prefix="/api")
    except Exception as e:
        logger.warning("API router not loaded: %s", e)

    return app


app = create_app()
