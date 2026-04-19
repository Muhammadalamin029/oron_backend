import uuid
from sqlalchemy.orm import Session
from typing import Optional

import models


def log_admin_action(
    db: Session,
    *,
    admin_user_id: str,
    action: str,
    entity_type: str,
    entity_id: str = "",
    meta: dict | None = None,
):
    """Log admin actions for audit trail"""
    entry = models.AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_user_id=admin_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id or "",
        meta=meta,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def log_user_activity(
    db: Session,
    *,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str = "",
    meta: dict | None = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Log user activities for security and analytics"""
    # Note: This would require a UserActivityLog model to be added to models.py
    # For now, we'll use a simple print statement for demonstration
    print(f"User Activity: {user_id} - {action} on {entity_type} ({entity_id})")
    if meta:
        print(f"Meta: {meta}")
    if ip_address:
        print(f"IP: {ip_address}")
    if user_agent:
        print(f"User Agent: {user_agent}")


def log_security_event(
    db: Session,
    *,
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: dict | None = None,
):
    """Log security-related events"""
    security_data = {
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "details": details,
    }
    
    # Log as admin action if user_id is provided and is admin
    if user_id:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user and user.is_admin:
            log_admin_action(
                db,
                admin_user_id=user_id,
                action=f"security.{event_type}",
                entity_type="security_event",
                meta=security_data,
            )
    
    print(f"Security Event: {event_type} - User: {user_id} - IP: {ip_address}")
    if details:
        print(f"Details: {details}")


def log_api_usage(
    db: Session,
    *,
    endpoint: str,
    method: str,
    user_id: Optional[str] = None,
    response_status: int,
    response_time_ms: Optional[int] = None,
    ip_address: Optional[str] = None,
):
    """Log API usage for monitoring and analytics"""
    usage_data = {
        "endpoint": endpoint,
        "method": method,
        "user_id": user_id,
        "response_status": response_status,
        "response_time_ms": response_time_ms,
        "ip_address": ip_address,
    }
    
    # Only log errors and slow requests as admin actions
    if response_status >= 400 or (response_time_ms and response_time_ms > 5000):
        log_admin_action(
            db,
            admin_user_id=user_id or "system",
            action="api.warning",
            entity_type="api_usage",
            meta=usage_data,
        )
    
    print(f"API Usage: {method} {endpoint} - {response_status} - {response_time_ms}ms")

