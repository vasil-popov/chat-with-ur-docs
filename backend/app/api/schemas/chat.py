from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str
    stream: Optional[bool] = False
    client_session_id: Optional[str] = None
    client_ip: Optional[str] = None
    file_ids: Optional[List[str]] = None
    arch: Literal["supervisor", "monolithic"] = Field(
        default="supervisor",
        description="Agent architecture to handle the request (thesis comparison arm).",
    )