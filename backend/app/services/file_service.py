import asyncio
import logging
import os
import uuid
from datetime import datetime

from sqlmodel import Session, select

from app.api.schemas.files import UploadedFileOut
from app.db.database import UploadedFile
from app.exceptions import (
    FileTooLargeError,
    InvalidIDError,
    NotFoundError,
    UnsupportedFileTypeError,
)
from app.services import embedding_service, extraction

logger = logging.getLogger(__name__)

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


def _write_file(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


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


async def upload_file(
    db: Session,
    content: bytes,
    filename: str,
    mime_type: str,
    category: str,
) -> dict:
    if len(content) > MAX_SIZE_BYTES:
        raise FileTooLargeError("File too large (max 5 MB)")

    file_type = ALLOWED_MIME_TYPES.get(mime_type)
    if not file_type:
        raise UnsupportedFileTypeError(f"Unsupported file type: {mime_type}")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4()
    ext = os.path.splitext(filename or "file")[1]
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    await asyncio.to_thread(_write_file, file_path, content)

    record = UploadedFile(
        id=file_id,
        original_name=filename or "unnamed",
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
    if receipt_proposal is not None:
        return {**out.model_dump(), "receipt_proposal": receipt_proposal}
    return out.model_dump()


def list_files(db: Session, category: str | None) -> list[UploadedFileOut]:
    stmt = select(UploadedFile).order_by(UploadedFile.uploaded_at.desc())
    if category and category != "all":
        stmt = stmt.where(UploadedFile.category == category)
    return [_to_out(f) for f in db.exec(stmt).all()]


def get_file(db: Session, file_id: str) -> UploadedFileOut:
    try:
        uid = uuid.UUID(file_id)
    except ValueError as exc:
        raise InvalidIDError(file_id) from exc

    record = db.get(UploadedFile, uid)
    if not record:
        raise NotFoundError(file_id)
    return _to_out(record, include_text=True)


def delete_file(db: Session, file_id: str) -> None:
    try:
        uid = uuid.UUID(file_id)
    except ValueError as exc:
        raise InvalidIDError(file_id) from exc

    record = db.get(UploadedFile, uid)
    if not record:
        raise NotFoundError(file_id)

    if os.path.exists(record.file_path):
        os.remove(record.file_path)

    embedding_service.delete_file_embeddings(file_id)

    db.delete(record)
    db.commit()
