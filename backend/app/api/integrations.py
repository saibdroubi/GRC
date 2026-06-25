import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import NotFoundError, ValidationError
from app.services import integrations as integrations_service

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("")
def list_integrations(organization_id: uuid.UUID, db: Session = Depends(get_db)):
    return integrations_service.list_statuses(db, organization_id)


@router.get("/{integration_type}")
def get_integration_status(integration_type: str, organization_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return integrations_service.get_status(db, organization_id, integration_type)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{integration_type}/config")
def configure_integration(
    integration_type: str,
    organization_id: uuid.UUID,
    config: dict = Body(...),
    db: Session = Depends(get_db),
):
    try:
        return integrations_service.update_connection_config(db, organization_id, integration_type, config)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{integration_type}/test")
def test_integration(integration_type: str, organization_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        return integrations_service.test_connection(db, organization_id, integration_type)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Connection test failed: {e}") from e


@router.post("/{integration_type}/sync")
def sync_integration(
    integration_type: str,
    organization_id: uuid.UUID,
    control_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        evidence = integrations_service.sync_evidence(db, organization_id, integration_type, control_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sync failed: {e}") from e

    return {
        "id": str(evidence.id),
        "evidence_type": evidence.evidence_type,
        "collected_at": evidence.collected_at,
        "extracted_facts": evidence.extracted_facts,
    }
