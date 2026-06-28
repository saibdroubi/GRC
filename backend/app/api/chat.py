import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, chat_agent, models, schemas
from app.database import get_db
from app.errors import ForbiddenError, NotFoundError

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_owned_session(db: Session, session_id: uuid.UUID, current_user: models.User) -> models.ChatSession:
    """Chat sessions are private to the user who started them -- look up by
    id AND owner together so this can't be used to read/post into someone
    else's conversation by guessing a session_id (IDOR)."""
    session = db.get(models.ChatSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise NotFoundError("Chat session not found")
    return session


@router.post("/sessions", response_model=schemas.ChatSessionOut)
def create_session(
    db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    session = models.ChatSession(
        organization_id=current_user.organization_id, user_id=current_user.id
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[schemas.ChatSessionOut])
def list_sessions(
    db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    return (
        db.query(models.ChatSession)
        .filter_by(user_id=current_user.id)
        .order_by(models.ChatSession.created_at.desc())
        .all()
    )


@router.get("/sessions/{session_id}/messages", response_model=list[schemas.ChatMessageOut])
def list_messages(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        _get_owned_session(db, session_id, current_user)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return (
        db.query(models.ChatMessage)
        .filter_by(session_id=session_id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )


@router.post("/sessions/{session_id}/messages", response_model=schemas.ChatMessageOut)
def post_message(
    session_id: uuid.UUID,
    payload: schemas.ChatMessageIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        _get_owned_session(db, session_id, current_user)
        return chat_agent.run_chat_turn(db, session_id, payload.content, current_user)
    except chat_agent.ChatNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
