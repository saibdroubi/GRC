import uuid

import pytest

from app.errors import NotFoundError, ValidationError
from app.services import gaps as gaps_service
from tests.factories import make_org, make_org_with_gap


def test_valid_status_transition_succeeds(db_session):
    _org, _control, gap = make_org_with_gap(db_session)
    org_id = gap.organization_id

    updated = gaps_service.update_gap_status(db_session, org_id, gap.id, "in_progress")
    assert updated.status == "in_progress"


@pytest.mark.parametrize("status", ["open", "in_progress", "remediated", "risk_accepted"])
def test_all_valid_statuses_accepted(db_session, status):
    _org, _control, gap = make_org_with_gap(db_session)
    updated = gaps_service.update_gap_status(db_session, gap.organization_id, gap.id, status)
    assert updated.status == status


def test_invalid_status_rejected(db_session):
    _org, _control, gap = make_org_with_gap(db_session)

    with pytest.raises(ValidationError):
        gaps_service.update_gap_status(db_session, gap.organization_id, gap.id, "not_a_real_status")


def test_unknown_gap_not_found(db_session):
    org = make_org(db_session)

    with pytest.raises(NotFoundError):
        gaps_service.update_gap_status(db_session, org.id, uuid.uuid4(), "in_progress")
