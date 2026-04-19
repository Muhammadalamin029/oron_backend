import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks
import models
import schemas
from core.security import verify_password, get_password_hash
from core.config import settings
from jose import jwt, JWTError
from core.security import create_access_token, create_verification_token
from core.email import send_verification_email
from services.audit import log_user_activity, log_security_event
from datetime import timedelta

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(
    db: Session,
    user: schemas.UserCreate,
    background_tasks: BackgroundTasks = None,
    *,
    is_admin: bool = False,
    is_verified: bool = False,
    is_active: bool = True,
    send_verification: bool = True
):
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        id=str(uuid.uuid4()),
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        is_active=is_active,
        is_admin=is_admin,
        is_verified=is_verified
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Log user registration
    log_user_activity(
        db,
        user_id=db_user.id,
        action="user.registered",
        entity_type="user",
        entity_id=db_user.id,
        meta={"email": db_user.email, "is_admin": is_admin}
    )
    
    if background_tasks and send_verification and not is_verified:
        # 24 hours validity
        token = create_verification_token(data={"sub": db_user.email})
        background_tasks.add_task(send_verification_email, db_user.email, token)
        
    return db_user

def verify_email(db: Session, token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None:
            raise HTTPException(status_code=400, detail="Invalid verification token: missing email")
        if token_type != "verify":
            if token_type == "access":
                raise HTTPException(status_code=400, detail="Invalid token type. Please use the verification link sent to your email, not your access token.")
            else:
                raise HTTPException(status_code=400, detail="Invalid verification token: wrong token type")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
        
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
        
    if user.is_verified:
        return {"msg": "Email already verified"}
        
    user.is_verified = True
    db.commit()
    
    # Log email verification
    log_user_activity(
        db,
        user_id=user.id,
        action="user.verified",
        entity_type="user",
        entity_id=user.id,
        meta={"email": user.email}
    )
    
    return {"msg": "Email successfully verified"}

def resend_verification_email(db: Session, email: str, background_tasks: BackgroundTasks):
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email already verified")
    
    # Generate new verification token (24 hours validity)
    token = create_verification_token(data={"sub": user.email})
    background_tasks.add_task(send_verification_email, user.email, token)
    
    # Log resend verification
    log_user_activity(
        db,
        user_id=user.id,
        action="user.verification_resent",
        entity_type="user",
        entity_id=user.id,
        meta={"email": user.email}
    )
    
    return {"msg": "Verification email sent successfully"}

def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user
