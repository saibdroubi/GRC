import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.errors import NotFoundError
from app.services import frameworks as frameworks_service

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


@router.get("", response_model=list[schemas.FrameworkOut])
def list_frameworks(db: Session = Depends(get_db)):
    return frameworks_service.list_frameworks(db)


@router.get("/{framework_id}/requirements", response_model=list[schemas.RequirementOut])
def list_requirements(framework_id: uuid.UUID, db: Session = Depends(get_db)):
    return frameworks_service.list_requirements(db, framework_id)


@router.get("/{framework_id}/controls", response_model=list[schemas.ControlOut])
def list_controls(framework_id: uuid.UUID, db: Session = Depends(get_db)):
    return frameworks_service.list_controls(db, framework_id)


@router.get("/{framework_id}/controls-with-status", response_model=list[schemas.ControlWithStatusOut])
def list_controls_with_status(
    framework_id: uuid.UUID, organization_id: uuid.UUID, db: Session = Depends(get_db)
):
    return frameworks_service.list_controls_with_status(db, framework_id, organization_id)


@router.get("/{framework_id}/score", response_model=schemas.FrameworkScoreOut)
def get_framework_score(
    framework_id: uuid.UUID, organization_id: uuid.UUID, db: Session = Depends(get_db)
):
    try:
        return frameworks_service.get_framework_score(db, framework_id, organization_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
