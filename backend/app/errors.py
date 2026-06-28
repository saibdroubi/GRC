"""Plain exceptions shared by the service layer.

Routers and the chat agent both call into app/services/*; each translates
these into its own surface (HTTPException for FastAPI, a tool_result error
for the chat agent) instead of every service function knowing about either.
"""


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class ForbiddenError(Exception):
    pass
