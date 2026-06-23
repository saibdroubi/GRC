import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.scoring import framework_score

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


@router.get("", response_model=list[schemas.FrameworkOut])
def list_frameworks(db: Session = Depends(get_db)):
    return db.query(models.Framework).all()


@router.get("/{framework_id}/requirements", response_model=list[schemas.RequirementOut])
def list_requirements(framework_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(models.Requirement).filter_by(framework_id=framework_id).all()


@router.get("/{framework_id}/controls", response_model=list[schemas.ControlOut])
def list_controls(framework_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.Control)
        .join(models.Requirement)
        .filter(models.Requirement.framework_id == framework_id)
        .all()
    )


@router.get("/{framework_id}/score", response_model=schemas.FrameworkScoreOut)
def get_framework_score(
    framework_id: uuid.UUID, organization_id: uuid.UUID, db: Session = Depends(get_db)
):
    fw = db.get(models.Framework, framework_id)
    if fw is None:
        raise HTTPException(status_code=404, detail="Framework not found")
    result = framework_score(db, framework_id, organization_id)
    return schemas.FrameworkScoreOut(
        framework_id=fw.id, framework_name=fw.name, framework_version=fw.version, **result
    )
