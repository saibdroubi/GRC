import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/gaps", tags=["gaps"])


@router.get("", response_model=list[schemas.GapOut])
def list_gaps(
    organization_id: uuid.UUID,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Gap).filter_by(organization_id=organization_id)
    if status:
        query = query.filter_by(status=status)
    return query.all()


@router.patch("/{gap_id}", response_model=schemas.GapOut)
def update_gap_status(gap_id: uuid.UUID, new_status: str, db: Session = Depends(get_db)):
    gap = db.get(models.Gap, gap_id)
    if gap is None:
        raise HTTPException(status_code=404, detail="Gap not found")
    if new_status not in ("open", "in_progress", "remediated", "risk_accepted"):
        raise HTTPException(status_code=400, detail="Invalid status")
    gap.status = new_status
    db.commit()
    db.refresh(gap)
    return gap
