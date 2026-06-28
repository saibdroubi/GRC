"""Password hashing and server-side session management.

Sessions over JWT: an opaque random token, SHA-256 hashed before storage, set
in an httpOnly/Secure/SameSite=Strict cookie. Revocation is just deleting the
row -- no key rotation or blocklist needed. SameSite=Strict is a strong, simple
CSRF mitigation for a cookie that's only ever used for fetch-based API calls
(never as a cross-site navigation target), which is why this pass doesn't also
need a separate CSRF token.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Cookie, Depends
from sqlalchemy.orm import Session as DBSession

from app import models
from app.database import get_db
from app.errors import AuthenticationError

SESSION_COOKIE_NAME = "session_token"
SESSION_TTL = timedelta(days=7)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: DBSession, user: models.User) -> str:
    token = secrets.token_urlsafe(32)
    session = models.Session(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=datetime.now(timezone.utc) + SESSION_TTL,
    )
    db.add(session)
    db.commit()
    return token


def invalidate_session(db: DBSession, token: str) -> None:
    db.query(models.Session).filter_by(token_hash=_hash_token(token)).delete()
    db.commit()


def _get_user_from_token(db: DBSession, token: str) -> models.User:
    session = db.query(models.Session).filter_by(token_hash=_hash_token(token)).one_or_none()
    if session is None:
        raise AuthenticationError("Invalid or expired session")
    if session.expires_at < datetime.now(timezone.utc).replace(tzinfo=session.expires_at.tzinfo):
        db.delete(session)
        db.commit()
        raise AuthenticationError("Invalid or expired session")

    user = db.get(models.User, session.user_id)
    if user is None:
        raise AuthenticationError("Invalid or expired session")
    return user


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: DBSession = Depends(get_db),
) -> models.User:
    if not session_token:
        raise AuthenticationError("Not authenticated")
    return _get_user_from_token(db, session_token)


def check_account_lockout(user: models.User) -> None:
    if user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(
        tzinfo=user.locked_until.tzinfo
    ):
        raise AuthenticationError("Account temporarily locked due to repeated failed logins")


def record_failed_login(db: DBSession, user: models.User) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + LOCKOUT_DURATION
        user.failed_login_attempts = 0
    db.commit()


def record_successful_login(db: DBSession, user: models.User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
