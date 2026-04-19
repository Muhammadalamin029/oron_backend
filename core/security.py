from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import jwt
from passlib.context import CryptContext

from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _create_token(*, data: dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    to_encode = dict(data)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire, "type": token_type})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(data=data, expires_delta=expires_delta, token_type="access")


def create_refresh_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    # default: 7 days
    if expires_delta is None:
        expires_delta = timedelta(days=7)
    return _create_token(data=data, expires_delta=expires_delta, token_type="refresh")


def create_verification_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    # default: 24 hours
    if expires_delta is None:
        expires_delta = timedelta(hours=24)
    return _create_token(data=data, expires_delta=expires_delta, token_type="verify")

