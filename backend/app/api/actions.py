import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db
from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.permissions import ADMIN_ROLES, WRITE_ROLES, require_role
from app.services import actions as actions_service

router = APIRouter(tags=["actions"])


@router.post("/gaps/{gap_id}/actions", response_model=schemas.ActionOut)
def propose_action(
    gap_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        require_role(current_user, WRITE_ROLES)
        return actions_service.propose_action(db, current_user.organization_id, gap_id)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/actions", response_model=list[schemas.ActionOut])
def list_actions(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return actions_service.list_actions(db, current_user.organization_id, status)


@router.post("/actions/{action_id}/approve", response_model=schemas.ActionOut)
def approve_action(
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        require_role(current_user, ADMIN_ROLES)
        return actions_service.approve_action(
            db, current_user.organization_id, action_id, current_user.id
        )
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/actions/{action_id}/reject", response_model=schemas.ActionOut)
def reject_action(
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        require_role(current_user, ADMIN_ROLES)
        return actions_service.reject_action(
            db, current_user.organization_id, action_id, current_user.id
        )
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
