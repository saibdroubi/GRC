import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.crypto import decrypt_config, encrypt_config
from app.errors import NotFoundError, ValidationError
from app.evidence_pipeline import record_evidence
from app.integrations import registry
import app.integrations  # noqa: F401  (importing the package registers every vendor module)


def list_types() -> list[dict]:
    return [
        {
            "type": d.type,
            "display_name": d.display_name,
            "permissions_help": d.permissions_help,
            "supports_evidence_sync": d.collect_evidence is not None,
            "fields": [
                {
                    "key": f.key,
                    "label": f.label,
                    "type": f.type,
                    "help_text": f.help_text,
                    "required": f.required,
                }
                for f in d.fields
            ],
        }
        for d in registry.list_all()
    ]


def _get_definition(integration_type: str):
    try:
        return registry.get(integration_type)
    except KeyError as e:
        raise NotFoundError(str(e)) from e


def get_connection(
    db: Session, organization_id: uuid.UUID, integration_type: str
) -> models.IntegrationConnection | None:
    return (
        db.query(models.IntegrationConnection)
        .filter_by(organization_id=organization_id, integration_type=integration_type)
        .one_or_none()
    )


def get_status(db: Session, organization_id: uuid.UUID, integration_type: str) -> dict:
    definition = _get_definition(integration_type)
    connection = get_connection(db, organization_id, integration_type)
    config = decrypt_config(connection.config_ciphertext) if connection else {}
    missing = definition.missing_required_fields(config)
    return {
        "type": definition.type,
        "display_name": definition.display_name,
        "configured": connection is not None and not missing,
        "missing_fields": missing,
        "status": connection.status if connection else None,
        "last_sync_at": connection.last_sync_at if connection else None,
    }


def list_statuses(db: Session, organization_id: uuid.UUID) -> list[dict]:
    return [get_status(db, organization_id, d.type) for d in registry.list_all()]


def update_connection_config(
    db: Session, organization_id: uuid.UUID, integration_type: str, partial_config: dict
) -> dict:
    """Merge newly provided fields into the connection's stored (encrypted)
    config. Returns which required fields are still missing, so a chat
    wizard or a form can ask for exactly those next."""
    definition = _get_definition(integration_type)
    connection = get_connection(db, organization_id, integration_type)

    existing_config = decrypt_config(connection.config_ciphertext) if connection else {}
    merged = {**existing_config, **partial_config}

    if connection is None:
        connection = models.IntegrationConnection(
            organization_id=organization_id,
            integration_type=integration_type,
            adapter_type=definition.adapter_type,
            status="disabled",
        )
        db.add(connection)

    connection.config_ciphertext = encrypt_config(merged)
    missing = definition.missing_required_fields(merged)
    connection.status = "disabled" if missing else "active"
    db.commit()

    return {"missing_fields": missing, "configured": not missing}


def test_connection(db: Session, organization_id: uuid.UUID, integration_type: str) -> dict:
    definition = _get_definition(integration_type)
    connection = get_connection(db, organization_id, integration_type)
    if connection is None:
        raise ValidationError(f"{definition.display_name} is not configured yet.")

    config = decrypt_config(connection.config_ciphertext)
    missing = definition.missing_required_fields(config)
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    try:
        result = definition.test_connection(config)
    except Exception as e:
        connection.status = "error"
        db.commit()
        return {"success": False, "message": f"Connection test failed: {e}"}

    connection.status = "active" if result.get("success") else "error"
    db.commit()
    return result


def sync_evidence(
    db: Session,
    organization_id: uuid.UUID,
    integration_type: str,
    control_id: uuid.UUID,
) -> models.Evidence:
    definition = _get_definition(integration_type)
    if definition.collect_evidence is None:
        raise ValidationError(
            f"{definition.display_name} does not support automatic evidence collection yet."
        )

    connection = get_connection(db, organization_id, integration_type)
    if connection is None:
        raise ValidationError(f"{definition.display_name} is not configured yet.")

    config = decrypt_config(connection.config_ciphertext)
    missing = definition.missing_required_fields(config)
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    try:
        facts = definition.collect_evidence(config)
    except Exception as e:
        connection.status = "error"
        db.commit()
        raise ValidationError(f"Evidence sync failed: {e}") from e

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
