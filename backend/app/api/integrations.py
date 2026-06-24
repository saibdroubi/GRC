import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import get_db
from app.evidence_pipeline import record_evidence
from app.integrations import m365

router = APIRouter(prefix="/integrations/m365", tags=["integrations"])


def _get_or_create_connection(db: Session, organization_id: uuid.UUID) -> models.IntegrationConnection:
    connection = (
        db.query(models.IntegrationConnection)
        .filter_by(organization_id=organization_id, adapter_type="m365")
        .one_or_none()
    )
    if connection is None:
        connection = models.IntegrationConnection(
            organization_id=organization_id,
            adapter_type="m365",
            config={"tenant_id": settings.m365_tenant_id, "client_id": settings.m365_client_id},
            status="active",
        )
        db.add(connection)
        db.flush()
    return connection


@router.get("/status", response_model=schemas.M365StatusOut)
def m365_status(organization_id: uuid.UUID, db: Session = Depends(get_db)):
    configured = bool(settings.m365_tenant_id and settings.m365_client_id and settings.m365_client_secret)
    connection = (
        db.query(models.IntegrationConnection)
        .filter_by(organization_id=organization_id, adapter_type="m365")
        .one_or_none()
    )
    return schemas.M365StatusOut(
        configured=configured,
        connection_id=connection.id if connection else None,
        status=connection.status if connection else None,
        last_sync_at=connection.last_sync_at if connection else None,
    )


@router.post("/sync", response_model=schemas.EvidenceOut)
def sync_mfa_evidence(
    organization_id: uuid.UUID, control_id: uuid.UUID, db: Session = Depends(get_db)
):
    """Pull live Conditional Access policies from Microsoft Graph and record
    the resulting MFA-enforcement evidence against the given control."""
    control = db.get(models.Control, control_id)
    if control is None:
        raise HTTPException(status_code=404, detail="Control not found")

    connection = _get_or_create_connection(db, organization_id)

    try:
        facts = m365.evaluate_mfa_enforcement()
    except m365.M365NotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except m365.M365RequestError as e:
        connection.status = "error"
        db.commit()
        raise HTTPException(status_code=502, detail=str(e)) from e

    connection.status = "active"
    connection.last_sync_at = datetime.now(timezone.utc)
    db.flush()

    return record_evidence(
        db,
        organization_id=organization_id,
        evidence_type="api_response",
        control_hints=[str(control_id)],
        extracted_facts=facts,
        connection_id=connection.id,
    )
