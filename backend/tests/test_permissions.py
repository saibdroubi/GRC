import pytest

from app import models
from app.errors import ForbiddenError
from app.permissions import ADMIN_ROLES, WRITE_ROLES, require_role


def _user_with_role(role: str) -> models.User:
    return models.User(role=role)


@pytest.mark.parametrize("role", ["admin", "owner", "analyst"])
def test_write_roles_allowed(role):
    require_role(_user_with_role(role), WRITE_ROLES)


@pytest.mark.parametrize("role", ["viewer"])
def test_write_roles_denied(role):
    with pytest.raises(ForbiddenError):
        require_role(_user_with_role(role), WRITE_ROLES)


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admin_roles_allowed(role):
    require_role(_user_with_role(role), ADMIN_ROLES)


@pytest.mark.parametrize("role", ["analyst", "viewer"])
def test_admin_roles_denied(role):
    with pytest.raises(ForbiddenError):
        require_role(_user_with_role(role), ADMIN_ROLES)
