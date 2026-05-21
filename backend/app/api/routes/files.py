from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.api.schemas.files import UploadedFileOut
from app.db.database import get_session
from app.exceptions import (
    FileTooLargeError,
    InvalidIDError,
    NotFoundError,
    UnsupportedFileTypeError,
)
from app.services import file_service

router = APIRouter()


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form("general"),
    db: Session = Depends(get_session),
):
    content = await file.read()
    try:
        return await file_service.upload_file(
            db,
            content,
            file.filename or "",
            file.content_type or "",
            category,
        )
    except FileTooLargeError:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))


@router.get("", response_model=List[UploadedFileOut])
def list_files(
    category: Optional[str] = None,
    db: Session = Depends(get_session),
):
    return file_service.list_files(db, category)


@router.get("/{file_id}", response_model=UploadedFileOut)
def get_file(file_id: str, db: Session = Depends(get_session)):
    try:
        return file_service.get_file(db, file_id)
    except InvalidIDError:
        raise HTTPException(status_code=400, detail="Invalid file ID")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@router.delete("/{file_id}", status_code=204)
def delete_file(file_id: str, db: Session = Depends(get_session)):
    try:
        file_service.delete_file(db, file_id)
    except InvalidIDError:
        raise HTTPException(status_code=400, detail="Invalid file ID")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
