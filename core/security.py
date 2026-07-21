from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import jwt
import bcrypt

from core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


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


def create_set_password_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    # default: 48 hours — longer than the verify-only token since this also gates completing a purchase
    if expires_delta is None:
        expires_delta = timedelta(hours=48)
    return _create_token(data=data, expires_delta=expires_delta, token_type="set_password")

