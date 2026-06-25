import uuid

from sqlalchemy.orm import Session

from app import models
from app.errors import NotFoundError, ValidationError

VALID_GAP_STATUSES = ("open", "in_progress", "remediated", "risk_accepted")


def list_gaps(db: Session, organization_id: uuid.UUID, status: str | None = None) -> list[models.Gap]:
    query = db.query(models.Gap).filter_by(organization_id=organization_id)
    if status:
        query = query.filter_by(status=status)
    return query.all()


def update_gap_status(db: Session, gap_id: uuid.UUID, new_status: str) -> models.Gap:
    gap = db.get(models.Gap, gap_id)
    if gap is None:
        raise NotFoundError("Gap not found")
    if new_status not in VALID_GAP_STATUSES:
        raise ValidationError(f"Invalid status, must be one of {VALID_GAP_STATUSES}")
    gap.status = new_status
    db.commit()
    db.refresh(gap)
    return gap
