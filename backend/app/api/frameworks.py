import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db
from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.permissions import ADMIN_ROLES, require_role
from app.services import framework_ingestion
from app.services import frameworks as frameworks_service

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


@router.get("", response_model=list[schemas.FrameworkOut])
def list_frameworks(
    db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    return frameworks_service.list_frameworks(db)


@router.get("/{framework_id}/requirements", response_model=list[schemas.RequirementOut])
def list_requirements(
    framework_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return frameworks_service.list_requirements(db, framework_id)


@router.get("/{framework_id}/controls", response_model=list[schemas.ControlOut])
def list_controls(
    framework_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return frameworks_service.list_controls(db, framework_id)


@router.get("/{framework_id}/controls-with-status", response_model=list[schemas.ControlWithStatusOut])
def list_controls_with_status(
    framework_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return frameworks_service.list_controls_with_status(db, framework_id, current_user.organization_id)


@router.get("/{framework_id}/score", response_model=schemas.FrameworkScoreOut)
def get_framework_score(
    framework_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        return frameworks_service.get_framework_score(db, framework_id, current_user.organization_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/ingest")
async def ingest_framework(
    name: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Upload an official framework document (PDF or .txt) and have Claude
    extract structured Requirements/Controls into a draft Framework for
    review. Nothing is fabricated -- only what's in the uploaded document."""
    try:
        require_role(current_user, ADMIN_ROLES)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    file_bytes = await file.read()
    is_pdf = (file.content_type == "application/pdf") or file.filename.lower().endswith(".pdf")

    try:
        framework, requirement_count, control_count = framework_ingestion.ingest_framework_document(
            db, name, version, file_bytes, is_pdf
        )
    except framework_ingestion.FrameworkIngestionNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "framework_id": str(framework.id),
        "status": framework.status,
        "requirements_extracted": requirement_count,
        "controls_extracted": control_count,
    }


@router.post("/{framework_id}/approve", response_model=schemas.FrameworkOut)
def approve_framework(
    framework_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        require_role(current_user, ADMIN_ROLES)
        return framework_ingestion.approve_framework(db, framework_id)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
