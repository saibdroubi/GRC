import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db
from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.permissions import WRITE_ROLES, require_role
from app.services import gaps as gaps_service

router = APIRouter(prefix="/gaps", tags=["gaps"])


@router.get("", response_model=list[schemas.GapOut])
def list_gaps(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return gaps_service.list_gaps(db, current_user.organization_id, status)


@router.patch("/{gap_id}", response_model=schemas.GapOut)
def update_gap_status(
    gap_id: uuid.UUID,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        require_role(current_user, WRITE_ROLES)
        return gaps_service.update_gap_status(db, current_user.organization_id, gap_id, new_status)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
