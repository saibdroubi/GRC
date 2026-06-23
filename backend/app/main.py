from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import evidence, frameworks, gaps

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


@app.get("/health")
def health():
    return {"status": "ok"}
