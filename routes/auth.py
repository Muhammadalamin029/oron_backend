from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List

from schemas import UserCreate, AuthResponse, User, RefreshTokenRequest, UserUpdate, ResendVerificationRequest
from services import auth as auth_service
from database.dependencies import get_db, get_current_active_user, get_admin_user
from core.security import create_access_token, create_refresh_token
import models
from core.config import settings
from jose import jwt, JWTError
from utils.rate_limit import rate_limiter

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=User)
async def register(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limiter.limit(key="auth.register", max_requests=10, window_seconds=60)),
):
    # Public registration must never allow admin creation via request payload
    return auth_service.create_user(
        db=db,
        user=user_data,
        background_tasks=background_tasks,
        is_admin=False,
        is_verified=False,
        is_active=True,
        send_verification=True,
    )

@router.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    return auth_service.verify_email(db, token)

@router.post("/resend-verification")
async def resend_verification(
    request: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limiter.limit(key="auth.resend_verification", max_requests=3, window_seconds=300)),
):
    return auth_service.resend_verification_email(db, request.email, background_tasks)

@router.post("/login", response_model=AuthResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limiter.limit(key="auth.login", max_requests=15, window_seconds=60)),
):
    user = auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer", "user": user}

@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        decoded = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_type = decoded.get("type")
        email = decoded.get("sub")
        if token_type != "refresh" or not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not user.is_active:
        raise credentials_exception

    access_token = create_access_token(data={"sub": user.email})
    new_refresh_token = create_refresh_token(data={"sub": user.email})
    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "bearer", "user": user}

@router.post("/logout")
async def logout():
    return {"ok": True}

@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    return current_user

@router.get("/verification-status")
async def get_verification_status(current_user: User = Depends(get_current_active_user)):
    return {"is_verified": current_user.is_verified, "email": current_user.email}

@router.patch("/profile", response_model=User)
async def update_profile(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_update.model_dump(exclude_unset=True, exclude={"email"})  # Don't allow email changes
    for key, value in update_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user

@router.get("/users", response_model=List[User])
async def list_users(db: Session = Depends(get_db), current_admin: User = Depends(get_admin_user)):
    return db.query(models.User).all()
