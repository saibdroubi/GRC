import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import adapters, ai_engine, models
from app.errors import NotFoundError, ValidationError
from app.scoring import apply_finding

ACTIONABLE_GAP_STATUSES = ("open", "in_progress")
ACTIVE_ACTION_STATUSES = ("pending_approval", "approved", "executing")


def list_actions(
    db: Session, organization_id: uuid.UUID, status: str | None = None
) -> list[models.Action]:
    query = (
        db.query(models.Action)
        .join(models.Gap)
        .filter(models.Gap.organization_id == organization_id)
    )
    if status:
        query = query.filter(models.Action.status == status)
    return query.all()


def propose_action(db: Session, gap_id: uuid.UUID) -> models.Action:
    """AI proposes a remediation action for an open gap. Lands in
    pending_approval — nothing executes until an admin approves it."""
    gap = db.get(models.Gap, gap_id)
    if gap is None:
        raise NotFoundError("Gap not found")
    if gap.status not in ACTIONABLE_GAP_STATUSES:
        raise ValidationError("Gap is not actionable")

    existing = (
        db.query(models.Action)
        .filter(
            models.Action.gap_id == gap_id,
            models.Action.status.in_(ACTIVE_ACTION_STATUSES),
        )
        .one_or_none()
    )
    if existing is not None:
        return existing

    control = db.get(models.Control, gap.control_id)
    adapter_type, action_type, parameters, rationale = ai_engine.propose_remediation(gap, control)

    action = models.Action(
        gap_id=gap.id,
        adapter_type=adapter_type,
        action_type=action_type,
        parameters={**parameters, "rationale": rationale},
        status="pending_approval",
        proposed_by="ai",
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def approve_action(db: Session, action_id: uuid.UUID, user_id: uuid.UUID) -> models.Action:
    action = db.get(models.Action, action_id)
    if action is None:
        raise NotFoundError("Action not found")
    if action.status != "pending_approval":
        raise ValidationError("Action is not pending approval")

    user = db.get(models.User, user_id)
    if user is None:
        raise NotFoundError("User not found")

    action.approved_by_user_id = user.id
    action.status = "executing"
    db.flush()

    gap = db.get(models.Gap, action.gap_id)
    result = adapters.execute_action(action)
    action.result = result
    action.executed_at = datetime.now(timezone.utc)
    action.status = "completed" if result.get("success") else "failed"

    db.add(
        models.AuditLog(
            organization_id=gap.organization_id,
            actor="user",
            action="approve_action",
            target_type="Action",
            target_id=action.id,
            payload={"approved_by": str(user.id), "result": result},
        )
    )

    if action.status == "completed":
        evidence = models.Evidence(
            organization_id=gap.organization_id,
            control_hints=[str(gap.control_id)],
            evidence_type="api_response",
            extracted_facts={
                "status": "met",
                "notes": f"Closed by approved action {action.id}: {result.get('message')}",
            },
        )
        db.add(evidence)
        db.flush()

        finding = models.Finding(
            control_id=gap.control_id,
            evidence_id=evidence.id,
            status="met",
            confidence=1.0,
            ai_rationale=f"Remediated via approved action ({action.adapter_type}.{action.action_type}).",
        )
        db.add(finding)
        db.flush()
        apply_finding(db, gap.organization_id, finding)

    db.commit()
    db.refresh(action)
    return action


def reject_action(db: Session, action_id: uuid.UUID, user_id: uuid.UUID) -> models.Action:
    action = db.get(models.Action, action_id)
    if action is None:
        raise NotFoundError("Action not found")
    if action.status != "pending_approval":
        raise ValidationError("Action is not pending approval")

    user = db.get(models.User, user_id)
    if user is None:
        raise NotFoundError("User not found")

    action.approved_by_user_id = user.id
    action.status = "rejected"

    gap = db.get(models.Gap, action.gap_id)
    db.add(
        models.AuditLog(
            organization_id=gap.organization_id,
            actor="user",
            action="reject_action",
            target_type="Action",
            target_id=action.id,
            payload={"rejected_by": str(user.id)},
        )
    )

    db.commit()
    db.refresh(action)
    return action
