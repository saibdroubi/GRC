import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import NotFoundError, ValidationError
from app.services import actions as actions_service

router = APIRouter(tags=["actions"])


@router.post("/gaps/{gap_id}/actions", response_model=schemas.ActionOut)
def propose_action(gap_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return actions_service.propose_action(db, gap_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/actions", response_model=list[schemas.ActionOut])
def list_actions(organization_id: uuid.UUID, status: str | None = None, db: Session = Depends(get_db)):
    return actions_service.list_actions(db, organization_id, status)


@router.post("/actions/{action_id}/approve", response_model=schemas.ActionOut)
def approve_action(action_id: uuid.UUID, user_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return actions_service.approve_action(db, action_id, user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/actions/{action_id}/reject", response_model=schemas.ActionOut)
def reject_action(action_id: uuid.UUID, user_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return actions_service.reject_action(db, action_id, user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
