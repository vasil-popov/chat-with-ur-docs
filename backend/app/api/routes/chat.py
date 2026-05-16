import uuid as _uuid

from fastapi import APIRouter, Depends
from app.api.schemas.chat import ChatRequest
from app.deps.dependency_container import di_container_instance

router = APIRouter()


def _augment_with_files(message: str, file_ids: list[str]) -> str:
    """Prepend extracted text from each file so the agent can read the actual content."""
    from sqlmodel import Session
    from app.db.database import UploadedFile, engine

    contexts = []
    with Session(engine) as db:
        for fid in file_ids:
            try:
                record = db.get(UploadedFile, _uuid.UUID(fid))
                if record and record.extracted_text:
                    contexts.append(
                        f"[Attached file: {record.original_name}]\n{record.extracted_text[:3000]}"
                    )
            except Exception:
                pass

    if not contexts:
        return message

    return "\n\n---\n\n".join(contexts) + f"\n\n---\n\nUser request: {message}"


@router.post("", summary="Chat API")
async def chat(
    req: ChatRequest,
    agent=Depends(di_container_instance.get_agent_instance),
):
    try:
        user_message = (
            _augment_with_files(req.message, req.file_ids)
            if req.file_ids
            else req.message
        )

        initial_state = {"messages": [("user", user_message)]}
        config = {"recursion_limit": 8}
        response = await agent.ainvoke(initial_state, config=config)

        raw_content = response["messages"][-1].content
        if isinstance(raw_content, str):
            final_message = raw_content
        elif isinstance(raw_content, list):
            text_blocks = [b.get("text", "") for b in raw_content if isinstance(b, dict) and "text" in b]
            final_message = "\n".join(text_blocks)
        else:
            final_message = str(raw_content)

        tools_used = []
        for msg in response["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_used.append(tc["name"])

        return {
            "role": "assistant",
            "content": final_message,
            "metadata": {"tools_executed": list(set(tools_used))},
        }

    except Exception as e:
        return {"role": "assistant", "content": f"System Error: {str(e)}", "metadata": {"tools_executed": []}}
