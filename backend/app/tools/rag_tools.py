from typing import List, Optional
from langchain_core.tools import tool
from app.services import embedding_service


@tool
def search_documents(query: str, file_ids: Optional[List[str]] = None) -> str:
    """Search over uploaded documents using semantic similarity. Optionally restrict to specific file IDs."""
    results = embedding_service.search(query, file_ids=file_ids, k=5)
    if not results:
        return "No relevant documents found."
    parts = []
    for doc, score in results:
        file_name = doc.metadata.get("file_name", "unknown")
        parts.append(f"[Source: {file_name}, score={score:.2f}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


@tool
def list_uploaded_files(category: Optional[str] = None) -> str:
    """List all uploaded files, optionally filtered by category (general, receipt, document, spreadsheet, image)."""
    from sqlmodel import Session, select
    from app.db.database import UploadedFile, engine

    with Session(engine) as session:
        stmt = select(UploadedFile).order_by(UploadedFile.uploaded_at.desc())
        if category:
            stmt = stmt.where(UploadedFile.category == category)
        files = session.exec(stmt).all()

    if not files:
        return "No uploaded files found."
    lines = [f"- {f.original_name} (id={f.id}, type={f.file_type}, status={f.status}, is_receipt={f.is_receipt})" for f in files]
    return "\n".join(lines)


@tool
def get_file_summary(file_id: str) -> str:
    """Get the extracted text / summary of an uploaded file by its ID."""
    from sqlmodel import Session
    from app.db.database import UploadedFile, engine

    with Session(engine) as session:
        record = session.get(UploadedFile, __import__("uuid").UUID(file_id))
    if not record:
        return f"File {file_id} not found."
    if not record.extracted_text:
        return f"File {record.original_name} has no extracted text yet (status: {record.status})."
    return f"File: {record.original_name}\n\n{record.extracted_text[:3000]}"
