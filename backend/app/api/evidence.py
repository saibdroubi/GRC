import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.evidence_pipeline import record_evidence

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("", response_model=schemas.EvidenceOut)
def submit_evidence(payload: schemas.EvidenceIn, db: Session = Depends(get_db)):
    """Manually submit a piece of evidence and immediately evaluate it against
    every control referenced in control_hints (control IDs as strings)."""
    return record_evidence(
        db,
        organization_id=payload.organization_id,
        evidence_type=payload.evidence_type,
        control_hints=payload.control_hints,
        extracted_facts=payload.extracted_facts,
        raw_ref=payload.raw_ref,
    )


@router.get("", response_model=list[schemas.EvidenceOut])
def list_evidence(organization_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(models.Evidence).filter_by(organization_id=organization_id).all()
