import uuid

from sqlalchemy.orm import Session

from app import models

SEVERITY_BY_STATUS = {
    "not_met": "high",
    "partial": "medium",
}


def apply_finding(db: Session, organization_id: uuid.UUID, finding: models.Finding) -> None:
    """Recompute ControlScore and Gap state for the control affected by a new Finding."""
    control_id = finding.control_id

    score = (
        db.query(models.ControlScore)
        .filter_by(control_id=control_id, organization_id=organization_id)
        .one_or_none()
    )
    if score is None:
        score = models.ControlScore(
            control_id=control_id,
            organization_id=organization_id,
            status=finding.status,
            confidence=finding.confidence,
        )
        db.add(score)
    else:
        score.status = finding.status
        score.confidence = finding.confidence

    existing_gap = (
        db.query(models.Gap)
        .filter_by(control_id=control_id, organization_id=organization_id, status="open")
        .one_or_none()
    )

    if finding.status in ("met", "not_applicable"):
        if existing_gap is not None:
            existing_gap.status = "remediated"
        return

    severity = SEVERITY_BY_STATUS.get(finding.status, "medium")
    if existing_gap is None:
        gap = models.Gap(
            control_id=control_id,
            organization_id=organization_id,
            severity=severity,
            description=finding.ai_rationale or f"Control evaluated as {finding.status}",
            recommended_action=None,
            status="open",
            linked_finding_ids=[str(finding.id)],
        )
        db.add(gap)
    else:
        existing_gap.severity = severity
        existing_gap.description = finding.ai_rationale or existing_gap.description
        existing_gap.linked_finding_ids = [
            *existing_gap.linked_finding_ids,
            str(finding.id),
        ]


def framework_score(db: Session, framework_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
    controls = (
        db.query(models.Control)
        .join(models.Requirement)
        .filter(models.Requirement.framework_id == framework_id)
        .all()
    )
    control_ids = [c.id for c in controls]
    scores = (
        db.query(models.ControlScore)
        .filter(
            models.ControlScore.control_id.in_(control_ids),
            models.ControlScore.organization_id == organization_id,
        )
        .all()
    )
    by_control = {s.control_id: s for s in scores}

    counts = {"met": 0, "partial": 0, "not_met": 0, "not_applicable": 0, "unscored": 0}
    for c in controls:
        s = by_control.get(c.id)
        counts[s.status if s else "unscored"] += 1

    scorable = counts["met"] + counts["partial"] + counts["not_met"]
    score_pct = round(100 * (counts["met"] + 0.5 * counts["partial"]) / scorable, 1) if scorable else 0.0

    return {"total_controls": len(controls), **counts, "score_pct": score_pct}
