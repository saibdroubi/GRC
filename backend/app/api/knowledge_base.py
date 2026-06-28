from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db
from app.errors import ForbiddenError
from app.permissions import WRITE_ROLES, require_role
from app.services import knowledge_base as kb_service

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.post("/documents", response_model=schemas.KnowledgeBaseEntryOut)
def ingest_document(
    payload: schemas.KnowledgeBaseDocumentIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        require_role(current_user, WRITE_ROLES)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    return kb_service.ingest_document(
        db,
        organization_id=current_user.organization_id,
        title=payload.title,
        content=payload.content,
        reformat=payload.reformat,
    )


@router.get("/search", response_model=list[schemas.KnowledgeBaseEntryOut])
def search(
    query: str,
    top_k: int = 5,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return kb_service.search(db, current_user.organization_id, query, top_k)
