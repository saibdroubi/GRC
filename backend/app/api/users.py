import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import auth, models
from app.database import get_db

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.User).filter_by(organization_id=current_user.organization_id).all()
