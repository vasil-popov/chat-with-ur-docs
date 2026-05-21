import json
import logging
import uuid as _uuid
from typing import AsyncGenerator

from sqlmodel import Session

from app.db.database import UploadedFile

logger = logging.getLogger(__name__)

# Node/chain names that are internal to LangGraph — not shown to the user
_INTERNAL_NAMES = frozenset({
    "supervisor", "tracking", "rag", "LangGraph", "RunnableSequence",
    "RunnableLambda", "RunnableParallel", "__start__", "__end__",
    "ChatPromptTemplate", "ChannelWrite", "ChannelRead", "ToolNode",
})


def augment_with_files(db: Session, message: str, file_ids: list[str]) -> str:
    """Prepend extracted text from each file so the agent can read the actual content."""
    contexts = []
    for fid in file_ids:
        try:
            record = db.get(UploadedFile, _uuid.UUID(fid))
            if record and record.extracted_text:
                contexts.append(
                    f"[Attached file: {record.original_name}]\n{record.extracted_text[:3000]}"
                )
        except Exception as exc:
            logger.warning("Could not attach file %s: %s", fid, exc)

    if not contexts:
        return message
    return "\n\n---\n\n".join(contexts) + f"\n\n---\n\nUser request: {message}"


def extract_content(msg) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and "text" in b)
    return str(content) if content else ""


async def stream_chat(
    agent,
    message: str,
    file_ids: list[str],
    db: Session,
) -> AsyncGenerator[str, None]:
    user_message = augment_with_files(db, message, file_ids) if file_ids else message
    initial_state = {"messages": [("user", user_message)]}
    config = {"recursion_limit": 8}

    tools_seen: list[str] = []
    last_content: str = ""

    try:
        async for event in agent.astream_events(initial_state, config=config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_tool_start" and name and name not in _INTERNAL_NAMES:
                if name not in tools_seen:
                    tools_seen.append(name)
                    yield f"data: {json.dumps({'type': 'tool', 'name': name})}\n\n"

            elif kind == "on_chain_end":
                output = event.get("data", {}).get("output") or {}
                if isinstance(output, dict):
                    msgs = output.get("messages", [])
                    if msgs:
                        candidate = extract_content(msgs[-1])
                        if candidate.strip():
                            last_content = candidate

        yield f"data: {json.dumps({'type': 'done', 'content': last_content, 'tools': tools_seen})}\n\n"

    except Exception as e:
        logger.error("SSE stream error: %s", e)
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


async def invoke_chat(
    agent,
    message: str,
    file_ids: list[str],
    db: Session,
) -> dict:
    try:
        user_message = augment_with_files(db, message, file_ids) if file_ids else message
        response = await agent.ainvoke(
            {"messages": [("user", user_message)]},
            config={"recursion_limit": 8},
        )
        final_message = extract_content(response["messages"][-1])
        tools_used = []
        for msg in response["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_used.append(tc["name"])
        return {"role": "assistant", "content": final_message, "metadata": {"tools_executed": list(set(tools_used))}}
    except Exception as e:
        return {"role": "assistant", "content": f"System Error: {str(e)}", "metadata": {"tools_executed": []}}
