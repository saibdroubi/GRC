import uuid

from sqlalchemy.orm import Session

from app import ai_engine, models
from app.scoring import apply_finding
from app.services import knowledge_base


def record_evidence(
    db: Session,
    organization_id: uuid.UUID,
    evidence_type: str,
    control_hints: list[str],
    extracted_facts: dict,
    connection_id: uuid.UUID | None = None,
    raw_ref: str | None = None,
) -> models.Evidence:
    """Persist a piece of evidence and evaluate it against every control in
    control_hints, updating Findings/ControlScores/Gaps as it goes. Shared by
    the manual evidence endpoint and every integration adapter's sync path."""
    evidence = models.Evidence(
        organization_id=organization_id,
        connection_id=connection_id,
        evidence_type=evidence_type,
        control_hints=control_hints,
        extracted_facts=extracted_facts,
        raw_ref=raw_ref,
    )
    db.add(evidence)
    db.flush()

    for control_id_str in control_hints:
        control = db.get(models.Control, uuid.UUID(control_id_str))
        if control is None:
            continue

        manual_status = extracted_facts.get("status")
        if manual_status in ("met", "partial", "not_met", "not_applicable"):
            status, confidence, rationale = (
                manual_status,
                1.0,
                extracted_facts.get("notes", "Asserted status."),
            )
        else:
            status, confidence, rationale = ai_engine.analyze_evidence_against_control(
                evidence, control
            )

        finding = models.Finding(
            control_id=control.id,
            evidence_id=evidence.id,
            status=status,
            confidence=confidence,
            ai_rationale=rationale,
        )
        db.add(finding)
        db.flush()
        apply_finding(db, organization_id, finding)

    knowledge_base.ingest_from_evidence(db, evidence)

    db.commit()
    db.refresh(evidence)
    return evidence
