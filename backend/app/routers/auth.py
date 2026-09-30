from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import Credentials, TokenResponse, UserOut
from app.security import create_access_token, hash_password, login_throttle, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    db.refresh(user)
    return {"access_token": create_access_token(user.id), "user": user}


@router.post("/login", response_model=TokenResponse)
def login(payload: Credentials, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower()
    key = ((request.client.host if request.client else "?"), email)
    if login_throttle.blocked(key):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please wait a few minutes and try again.")
    user = db.query(User).filter(User.email == email).first()
    if not verify_password(payload.password, user.password_hash if user else None):
        login_throttle.record_failure(key)
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    login_throttle.reset(key)
    return {"access_token": create_access_token(user.id), "user": user}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
