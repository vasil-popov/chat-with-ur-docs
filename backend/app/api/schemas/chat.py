from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    stream: Optional[bool] = False
    client_session_id: Optional[str] = None
    client_ip: Optional[str] = None
    file_ids: Optional[List[str]] = None