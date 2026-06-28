"""Confirms chat_agent._dispatch enforces the exact same role gates as the
REST routers (app/chat_agent.py::_TOOL_ROLE_REQUIREMENTS mirrors
app/permissions.py usage in app/api/*.py) -- chat must not be a way to bypass
RBAC that the dashboard enforces. _dispatch checks require_role before
touching tool_input, so an empty dict is safe for the denial cases."""

import pytest

from app.chat_agent import _dispatch
from app.errors import ForbiddenError
from app.permissions import ADMIN_ROLES, WRITE_ROLES
from app.services import actions as actions_service
from tests.factories import make_org_with_gap, make_user

WRITE_GATED_TOOLS = ["update_gap_status", "submit_evidence", "propose_action", "save_to_knowledge_base"]
ADMIN_GATED_TOOLS = [
    "approve_action",
    "reject_action",
    "configure_integration",
    "test_integration_connection",
    "sync_integration_evidence",
]


@pytest.mark.parametrize("tool_name", WRITE_GATED_TOOLS)
def test_viewer_denied_write_gated_tools(db_session, tool_name):
    org, _control, _gap = make_org_with_gap(db_session)
    viewer = make_user(db_session, org, role="viewer")

    with pytest.raises(ForbiddenError):
        _dispatch(db_session, viewer, tool_name, {})


@pytest.mark.parametrize("tool_name", ADMIN_GATED_TOOLS)
def test_analyst_denied_admin_gated_tools(db_session, tool_name):
    org, _control, _gap = make_org_with_gap(db_session)
    analyst = make_user(db_session, org, role="analyst")

    with pytest.raises(ForbiddenError):
        _dispatch(db_session, analyst, tool_name, {})


@pytest.mark.parametrize("tool_name", ADMIN_GATED_TOOLS)
def test_viewer_denied_admin_gated_tools(db_session, tool_name):
    org, _control, _gap = make_org_with_gap(db_session)
    viewer = make_user(db_session, org, role="viewer")

    with pytest.raises(ForbiddenError):
        _dispatch(db_session, viewer, tool_name, {})


def test_analyst_allowed_update_gap_status(db_session):
    org, _control, gap = make_org_with_gap(db_session)
    analyst = make_user(db_session, org, role="analyst")
    assert analyst.role in WRITE_ROLES

    updated = _dispatch(
        db_session, analyst, "update_gap_status", {"gap_id": str(gap.id), "new_status": "in_progress"}
    )
    assert updated.status == "in_progress"


def test_admin_allowed_approve_action(db_session):
    org, _control, gap = make_org_with_gap(db_session)
    admin = make_user(db_session, org, role="admin")
    assert admin.role in ADMIN_ROLES

    action = actions_service.propose_action(db_session, org.id, gap.id)

    approved = _dispatch(db_session, admin, "approve_action", {"action_id": str(action.id)})
    assert approved.status == "completed"
