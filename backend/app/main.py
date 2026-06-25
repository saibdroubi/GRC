from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    actions,
    chat,
    evidence,
    frameworks,
    gaps,
    integrations,
    knowledge_base,
    organizations,
    users,
)

app = FastAPI(title="GRC Automation Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(frameworks.router)
app.include_router(evidence.router)
app.include_router(gaps.router)
app.include_router(organizations.router)
app.include_router(actions.router)
app.include_router(users.router)
app.include_router(integrations.router)
app.include_router(chat.router)
app.include_router(knowledge_base.router)


@app.get("/health")
def health():
    return {"status": "ok"}
