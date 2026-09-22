import uuid
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import Document, DocumentStatus, User
from app.database.session import get_db
from app.dependencies import (
    PHASE1_BYPASS_USER_ID,
    PHASE1_BYPASS_WORKSPACE_ID,
    get_current_user,
)
from app.services.dify_service import DifyServiceError, dify_service
from app.services.parser_service import parser_service

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()


class DocumentUploadResponse(BaseModel):
    id: str
    title: str
    status: DocumentStatus
    dify_document_id: str | None = None


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    category: Annotated[Optional[str], Form()] = None,
    workspace_id: Annotated[Optional[str], Form()] = None,
    current_user: Annotated[User, Depends(get_current_user)] = ...,
    db: Annotated[Session, Depends(get_db)] = ...,
) -> DocumentUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    # PHASE 1: Auth bypass — use default workspace, skip membership check
    workspace_uuid = uuid.UUID(workspace_id) if workspace_id else PHASE1_BYPASS_WORKSPACE_ID
    # verify_workspace_access(db, user_id=current_user.id, workspace_id=workspace_uuid)

    # PHASE 1: Skip workspace DB lookup — use default Dify dataset from settings
    # workspace = db.get(Workspace, workspace_uuid)
    # if not workspace:
    #     raise HTTPException(status_code=404, detail="Workspace not found")
    dataset_id = settings.dify_default_dataset_id

    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=413, detail="File exceeds upload limit")

    document = Document(
        title=file.filename,
        category=category,
        status=DocumentStatus.PROCESSING,
        original_filename=file.filename,
        owner_id=current_user.id or PHASE1_BYPASS_USER_ID,
        workspace_id=workspace_uuid,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        parsed = parser_service.parse_pdf_bytes(file_bytes, file.filename)

        dify_result = await dify_service.create_document_by_text(
            dataset_id=dataset_id,
            name=parsed["title"],
            text=parsed["markdown"],
            metadata={
                "category": category,
                "workspace_id": str(workspace_uuid),
                "document_id": str(document.id),
                **parsed["metadata"],
            },
        )

        document.status = DocumentStatus.COMPLETED
        document.title = parsed["title"]
        document.dify_document_id = dify_result.get("document", {}).get("id")
        db.commit()
        db.refresh(document)

    except (DifyServiceError, Exception) as exc:
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Document ingestion failed: {exc}",
        ) from exc

    return DocumentUploadResponse(
        id=str(document.id),
        title=document.title,
        status=document.status,
        dify_document_id=document.dify_document_id,
    )
