from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    actions,
    auth,
    chat,
    evidence,
    frameworks,
    gaps,
    integrations,
    knowledge_base,
    users,
)
from app.errors import AuthenticationError, ForbiddenError, NotFoundError, ValidationError

app = FastAPI(title="GRC Automation Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Safety net: most routers already translate these into HTTPException
# explicitly, but exceptions raised inside a *dependency* (e.g.
# app.auth.get_current_user, which runs before any route body) can't be
# caught by a route's own try/except -- without this they'd surface as a
# raw 500. Centralizing the mapping here means a missed try/except
# anywhere else degrades to the right status code instead of a crash.
_STATUS_BY_ERROR = {
    AuthenticationError: 401,
    ForbiddenError: 403,
    NotFoundError: 404,
    ValidationError: 400,
}

for exc_class, status_code in _STATUS_BY_ERROR.items():

    def _make_handler(code: int):
        async def _handler(request: Request, exc: Exception):
            return JSONResponse(status_code=code, content={"detail": str(exc)})

        return _handler

    app.add_exception_handler(exc_class, _make_handler(status_code))

app.include_router(auth.router)
app.include_router(frameworks.router)
app.include_router(evidence.router)
app.include_router(gaps.router)
app.include_router(actions.router)
app.include_router(users.router)
app.include_router(integrations.router)
app.include_router(chat.router)
app.include_router(knowledge_base.router)


@app.get("/health")
def health():
    return {"status": "ok"}
