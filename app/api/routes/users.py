from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.schemas.api import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == body.email))
    if existing:
        existing.preferences = {**existing.preferences, **body.preferences}
        db.commit()
        return UserOut(id=existing.id, email=existing.email, preferences=existing.preferences)
    user = User(email=body.email, preferences=body.preferences)
    db.add(user)
    db.commit()
    return UserOut(id=user.id, email=user.email, preferences=user.preferences)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return UserOut(id=user.id, email=user.email, preferences=user.preferences)
