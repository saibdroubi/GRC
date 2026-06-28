"""RBAC permission checks, called from both FastAPI routers (REST) and
app/chat_agent.py (chat) -- kept out of app/services/* so the service layer
stays pure domain logic, with access control as one shared application-layer
concern both surfaces go through identically."""

from app import models
from app.errors import ForbiddenError

ADMIN_ROLES = {"admin", "owner"}
WRITE_ROLES = {"admin", "owner", "analyst"}


def require_role(user: models.User, allowed_roles: set[str]) -> None:
    if user.role not in allowed_roles:
        raise ForbiddenError(
            f"Role '{user.role}' is not permitted to perform this action "
            f"(requires one of: {', '.join(sorted(allowed_roles))})"
        )
