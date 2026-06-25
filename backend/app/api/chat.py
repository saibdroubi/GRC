import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import chat_agent, models, schemas
from app.database import get_db
from app.errors import NotFoundError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=schemas.ChatSessionOut)
def create_session(payload: schemas.ChatSessionIn, db: Session = Depends(get_db)):
    session = models.ChatSession(organization_id=payload.organization_id, user_id=payload.user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[schemas.ChatSessionOut])
def list_sessions(organization_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.ChatSession)
        .filter_by(organization_id=organization_id)
        .order_by(models.ChatSession.created_at.desc())
        .all()
    )


@router.get("/sessions/{session_id}/messages", response_model=list[schemas.ChatMessageOut])
def list_messages(session_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(models.ChatMessage)
        .filter_by(session_id=session_id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )


@router.post("/sessions/{session_id}/messages", response_model=schemas.ChatMessageOut)
def post_message(session_id: uuid.UUID, payload: schemas.ChatMessageIn, db: Session = Depends(get_db)):
    try:
        return chat_agent.run_chat_turn(db, session_id, payload.content)
    except chat_agent.ChatNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
