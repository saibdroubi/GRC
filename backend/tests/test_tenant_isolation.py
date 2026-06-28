"""Regression tests for the three IDOR fixes made during the auth/RBAC pass:
cross-org access to a gap, an action, or a chat session must come back as
NotFoundError/404 -- never a 403, which would itself leak that the resource
exists in someone else's tenant."""

import pytest

from app.errors import NotFoundError
from app.services import actions as actions_service
from app.services import gaps as gaps_service
from tests.factories import login, make_org, make_org_with_gap, make_user


def test_update_gap_status_cross_org_not_found(db_session):
    _org, _control, gap = make_org_with_gap(db_session)
    other_org = make_org(db_session, "Other Org")

    with pytest.raises(NotFoundError):
        gaps_service.update_gap_status(db_session, other_org.id, gap.id, "in_progress")


def test_propose_action_cross_org_not_found(db_session):
    _org, _control, gap = make_org_with_gap(db_session)
    other_org = make_org(db_session, "Other Org")

    with pytest.raises(NotFoundError):
        actions_service.propose_action(db_session, other_org.id, gap.id)


def test_approve_action_cross_org_not_found(db_session):
    org, _control, gap = make_org_with_gap(db_session)
    action = actions_service.propose_action(db_session, org.id, gap.id)

    other_org = make_org(db_session, "Other Org")
    other_user = make_user(db_session, other_org)

    with pytest.raises(NotFoundError):
        actions_service.approve_action(db_session, other_org.id, action.id, other_user.id)


def test_reject_action_cross_org_not_found(db_session):
    org, _control, gap = make_org_with_gap(db_session)
    action = actions_service.propose_action(db_session, org.id, gap.id)

    other_org = make_org(db_session, "Other Org")
    other_user = make_user(db_session, other_org)

    with pytest.raises(NotFoundError):
        actions_service.reject_action(db_session, other_org.id, action.id, other_user.id)


def test_chat_session_not_readable_by_other_user(client, db_session):
    org = make_org(db_session)
    make_user(db_session, org, email="owner@example.com", password="correct-password-123")
    make_user(db_session, org, email="snooper@example.com", password="correct-password-123")

    login(client, "owner@example.com", "correct-password-123")
    created = client.post("/chat/sessions")
    assert created.status_code == 200
    session_id = created.json()["id"]

    login(client, "snooper@example.com", "correct-password-123")
    res = client.get(f"/chat/sessions/{session_id}/messages")
    assert res.status_code == 404
