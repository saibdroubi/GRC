import pytest

from app import models
from app.errors import ValidationError
from app.services import actions as actions_service
from tests.factories import make_org_with_gap, make_user


def test_propose_then_approve_completes_and_creates_finding(db_session):
    org, control, gap = make_org_with_gap(db_session)
    approver = make_user(db_session, org, role="admin")

    action = actions_service.propose_action(db_session, org.id, gap.id)
    assert action.status == "pending_approval"
    assert action.proposed_by == "ai"

    approved = actions_service.approve_action(db_session, org.id, action.id, approver.id)
    assert approved.status == "completed"
    assert approved.approved_by_user_id == approver.id
    assert approved.result["success"] is True

    finding = (
        db_session.query(models.Finding)
        .filter_by(control_id=control.id)
        .order_by(models.Finding.created_at.desc())
        .first()
    )
    assert finding is not None
    assert finding.status == "met"


def test_propose_then_reject(db_session):
    org, _control, gap = make_org_with_gap(db_session)
    rejector = make_user(db_session, org, role="admin")

    action = actions_service.propose_action(db_session, org.id, gap.id)
    rejected = actions_service.reject_action(db_session, org.id, action.id, rejector.id)

    assert rejected.status == "rejected"
    assert rejected.approved_by_user_id == rejector.id


def test_propose_is_idempotent_while_action_active(db_session):
    org, _control, gap = make_org_with_gap(db_session)

    first = actions_service.propose_action(db_session, org.id, gap.id)
    second = actions_service.propose_action(db_session, org.id, gap.id)

    assert first.id == second.id


def test_propose_against_non_actionable_gap_rejected(db_session):
    org, _control, gap = make_org_with_gap(db_session, status="remediated")

    with pytest.raises(ValidationError):
        actions_service.propose_action(db_session, org.id, gap.id)


def test_double_approve_rejected(db_session):
    org, _control, gap = make_org_with_gap(db_session)
    approver = make_user(db_session, org, role="admin")

    action = actions_service.propose_action(db_session, org.id, gap.id)
    actions_service.approve_action(db_session, org.id, action.id, approver.id)

    with pytest.raises(ValidationError):
        actions_service.approve_action(db_session, org.id, action.id, approver.id)


def test_reject_after_approval_rejected(db_session):
    org, _control, gap = make_org_with_gap(db_session)
    approver = make_user(db_session, org, role="admin")

    action = actions_service.propose_action(db_session, org.id, gap.id)
    actions_service.approve_action(db_session, org.id, action.id, approver.id)

    with pytest.raises(ValidationError):
        actions_service.reject_action(db_session, org.id, action.id, approver.id)
