from typing import Optional

from pydantic import BaseModel


class UploadedFileOut(BaseModel):
    id: str
    original_name: str
    file_type: str
    category: str
    size_bytes: int
    status: str
    is_receipt: bool
    uploaded_at: str
    extracted_text: Optional[str] = None
    error_message: Optional[str] = None
