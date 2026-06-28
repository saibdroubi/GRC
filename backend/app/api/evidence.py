from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db
from app.errors import ForbiddenError
from app.evidence_pipeline import record_evidence
from app.permissions import WRITE_ROLES, require_role

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("", response_model=schemas.EvidenceOut)
def submit_evidence(
    payload: schemas.EvidenceIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Manually submit a piece of evidence and immediately evaluate it against
    every control referenced in control_hints (control IDs as strings)."""
    try:
        require_role(current_user, WRITE_ROLES)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    return record_evidence(
        db,
        organization_id=current_user.organization_id,
        evidence_type=payload.evidence_type,
        control_hints=payload.control_hints,
        extracted_facts=payload.extracted_facts,
        raw_ref=payload.raw_ref,
    )


@router.get("", response_model=list[schemas.EvidenceOut])
def list_evidence(
    db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.Evidence).filter_by(organization_id=current_user.organization_id).all()
