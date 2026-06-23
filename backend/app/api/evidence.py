import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import ai_engine, models, schemas
from app.database import get_db
from app.scoring import apply_finding

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("", response_model=schemas.EvidenceOut)
def submit_evidence(payload: schemas.EvidenceIn, db: Session = Depends(get_db)):
    """Manually submit a piece of evidence and immediately evaluate it against
    every control referenced in control_hints (control IDs as strings)."""
    evidence = models.Evidence(
        organization_id=payload.organization_id,
        evidence_type=payload.evidence_type,
        control_hints=payload.control_hints,
        extracted_facts=payload.extracted_facts,
        raw_ref=payload.raw_ref,
    )
    db.add(evidence)
    db.flush()

    for control_id_str in payload.control_hints:
        control = db.get(models.Control, uuid.UUID(control_id_str))
        if control is None:
            continue

        manual_status = payload.extracted_facts.get("status")
        if manual_status in ("met", "partial", "not_met", "not_applicable"):
            status, confidence, rationale = (
                manual_status,
                1.0,
                payload.extracted_facts.get("notes", "Manually asserted status."),
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
        apply_finding(db, payload.organization_id, finding)

    db.commit()
    db.refresh(evidence)
    return evidence


@router.get("", response_model=list[schemas.EvidenceOut])
def list_evidence(organization_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(models.Evidence).filter_by(organization_id=organization_id).all()
