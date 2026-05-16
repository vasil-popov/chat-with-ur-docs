import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.database import UploadedFile, get_session
from app.services import extraction, embedding_service

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = "uploads"
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

ALLOWED_MIME_TYPES = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "application/pdf": "pdf",
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
    "application/vnd.ms-excel": "excel",
}


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


def _to_out(f: UploadedFile, include_text: bool = False) -> UploadedFileOut:
    return UploadedFileOut(
        id=str(f.id),
        original_name=f.original_name,
        file_type=f.file_type,
        category=f.category,
        size_bytes=f.size_bytes,
        status=f.status,
        is_receipt=f.is_receipt,
        uploaded_at=f.uploaded_at.isoformat(),
        extracted_text=f.extracted_text if include_text else None,
        error_message=f.error_message,
    )


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form("general"),
    db: Session = Depends(get_session),
):
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")

    mime_type = file.content_type or ""
    file_type = ALLOWED_MIME_TYPES.get(mime_type)
    if not file_type:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {mime_type}")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4()
    ext = os.path.splitext(file.filename or "file")[1]
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    with open(file_path, "wb") as f_out:
        f_out.write(content)

    record = UploadedFile(
        id=file_id,
        original_name=file.filename or "unnamed",
        file_path=file_path,
        file_type=file_type,
        mime_type=mime_type,
        category=category,
        size_bytes=len(content),
        status="processing",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Extract text synchronously
    receipt_proposal = None
    try:
        text = extraction.extract_text(file_path, file_type, mime_type)
        record.extracted_text = text
        record.is_receipt = extraction.is_receipt(text)
        record.status = "ready"
        record.processed_at = datetime.utcnow()

        if record.is_receipt:
            from app.deps.dependency_container import di_container_instance
            llm = di_container_instance.llm_client
            if llm:
                receipt_proposal = extraction.parse_receipt_items(text, llm)

        try:
            embedding_service.embed_file(str(file_id), record.original_name, text)
        except Exception as e:
            logger.warning("Embedding failed for %s: %s", file_id, e)

    except Exception as e:
        logger.error("Extraction failed for %s: %s", file_id, e)
        record.status = "error"
        record.error_message = str(e)

    db.add(record)
    db.commit()
    db.refresh(record)

    out = _to_out(record, include_text=True)
    # Attach receipt proposal if detected
    if receipt_proposal is not None:
        return {**out.model_dump(), "receipt_proposal": receipt_proposal}
    return out


@router.get("", response_model=List[UploadedFileOut])
def list_files(
    category: Optional[str] = None,
    db: Session = Depends(get_session),
):
    stmt = select(UploadedFile).order_by(UploadedFile.uploaded_at.desc())
    if category and category != "all":
        stmt = stmt.where(UploadedFile.category == category)
    return [_to_out(f) for f in db.exec(stmt).all()]


@router.get("/{file_id}", response_model=UploadedFileOut)
def get_file(file_id: str, db: Session = Depends(get_session)):
    try:
        uid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")
    record = db.get(UploadedFile, uid)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    return _to_out(record, include_text=True)


@router.delete("/{file_id}", status_code=204)
def delete_file(file_id: str, db: Session = Depends(get_session)):
    try:
        uid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")
    record = db.get(UploadedFile, uid)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    if os.path.exists(record.file_path):
        os.remove(record.file_path)

    embedding_service.delete_file_embeddings(file_id)

    db.delete(record)
    db.commit()
