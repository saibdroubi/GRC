from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db
from app.errors import AuthenticationError

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=auth.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=int(auth.SESSION_TTL.total_seconds()),
    )


@router.post("/signup", response_model=schemas.CurrentUserOut)
def signup(payload: schemas.SignupIn, response: Response, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter_by(email=payload.email).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    org = models.Organization(name=payload.organization_name, deployment_mode="cloud")
    db.add(org)
    db.flush()

    user = models.User(
        organization_id=org.id,
        name=payload.name,
        email=payload.email,
        role="admin",
        password_hash=auth.hash_password(payload.password),
    )
    db.add(user)
    db.commit()

    token = auth.create_session(db, user)
    _set_session_cookie(response, token)

    return schemas.CurrentUserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        organization_id=org.id,
        organization_name=org.name,
    )


@router.post("/login", response_model=schemas.CurrentUserOut)
def login(payload: schemas.LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=payload.email).one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    try:
        auth.check_account_lockout(user)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    if not auth.verify_password(payload.password, user.password_hash):
        auth.record_failed_login(db, user)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    auth.record_successful_login(db, user)
    token = auth.create_session(db, user)
    _set_session_cookie(response, token)

    return schemas.CurrentUserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        organization_id=user.organization_id,
        organization_name=user.organization.name,
    )


@router.post("/logout")
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if session_token:
        auth.invalidate_session(db, session_token)
    response.delete_cookie(auth.SESSION_COOKIE_NAME)
    return {"status": "logged_out"}


@router.get("/me", response_model=schemas.CurrentUserOut)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return schemas.CurrentUserOut(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        organization_id=current_user.organization_id,
        organization_name=current_user.organization.name,
    )
