import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import NotFoundError, ValidationError
from app.services import gaps as gaps_service

router = APIRouter(prefix="/gaps", tags=["gaps"])


@router.get("", response_model=list[schemas.GapOut])
def list_gaps(
    organization_id: uuid.UUID,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return gaps_service.list_gaps(db, organization_id, status)


@router.patch("/{gap_id}", response_model=schemas.GapOut)
def update_gap_status(gap_id: uuid.UUID, new_status: str, db: Session = Depends(get_db)):
    try:
        return gaps_service.update_gap_status(db, gap_id, new_status)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
