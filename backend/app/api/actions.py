import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import adapters, ai_engine, models, schemas
from app.database import get_db
from app.scoring import apply_finding

router = APIRouter(tags=["actions"])


@router.post("/gaps/{gap_id}/actions", response_model=schemas.ActionOut)
def propose_action(gap_id: uuid.UUID, db: Session = Depends(get_db)):
    """AI proposes a remediation action for an open gap. Lands in
    pending_approval — nothing executes until an admin approves it."""
    gap = db.get(models.Gap, gap_id)
    if gap is None:
        raise HTTPException(status_code=404, detail="Gap not found")
    if gap.status not in ("open", "in_progress"):
        raise HTTPException(status_code=400, detail="Gap is not actionable")

    existing = (
        db.query(models.Action)
        .filter(
            models.Action.gap_id == gap_id,
            models.Action.status.in_(["pending_approval", "approved", "executing"]),
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


@router.get("/actions", response_model=list[schemas.ActionOut])
def list_actions(organization_id: uuid.UUID, status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Action).join(models.Gap).filter(models.Gap.organization_id == organization_id)
    if status:
        query = query.filter(models.Action.status == status)
    return query.all()


@router.post("/actions/{action_id}/approve", response_model=schemas.ActionOut)
def approve_action(action_id: uuid.UUID, user_id: uuid.UUID, db: Session = Depends(get_db)):
    action = db.get(models.Action, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Action is not pending approval")

    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

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


@router.post("/actions/{action_id}/reject", response_model=schemas.ActionOut)
def reject_action(action_id: uuid.UUID, user_id: uuid.UUID, db: Session = Depends(get_db)):
    action = db.get(models.Action, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Action is not pending approval")

    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

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
