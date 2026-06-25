import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.services import knowledge_base as kb_service

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.post("/documents", response_model=schemas.KnowledgeBaseEntryOut)
def ingest_document(payload: schemas.KnowledgeBaseDocumentIn, db: Session = Depends(get_db)):
    return kb_service.ingest_document(
        db,
        organization_id=payload.organization_id,
        title=payload.title,
        content=payload.content,
        reformat=payload.reformat,
    )


@router.get("/search", response_model=list[schemas.KnowledgeBaseEntryOut])
def search(organization_id: uuid.UUID, query: str, top_k: int = 5, db: Session = Depends(get_db)):
    return kb_service.search(db, organization_id, query, top_k)
