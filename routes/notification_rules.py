from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database.dependencies import get_admin_user, get_db
from services.audit import log_admin_action

router = APIRouter(prefix="/notification-rules", tags=["notification-rules"])


class NotificationRuleUpdate(BaseModel):
    notify_customers: bool
    notify_newsletter: bool


def _serialize(rule: models.NotificationRule) -> dict:
    return {
        "action": rule.action,
        "notify_customers": rule.notify_customers,
        "notify_newsletter": rule.notify_newsletter,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at is not None else None,
    }


@router.get("/")
def list_rules(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user),
):
    rules = db.query(models.NotificationRule).all()
    return [_serialize(r) for r in rules]


@router.post("/{action}")
def upsert_rule(
    action: str,
    payload: NotificationRuleUpdate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user),
):
    rule = (
        db.query(models.NotificationRule)
        .filter(models.NotificationRule.action == action)
        .first()
    )
    if rule:
        rule.notify_customers = payload.notify_customers
        rule.notify_newsletter = payload.notify_newsletter
    else:
        rule = models.NotificationRule(
            action=action,
            notify_customers=payload.notify_customers,
            notify_newsletter=payload.notify_newsletter,
        )
        db.add(rule)

    db.commit()
    db.refresh(rule)

    log_admin_action(
        db,
        admin_user_id=admin_user.id,
        action="notification_rule.upsert",
        entity_type="notification_rule",
        entity_id=action,
        meta={
            "notify_customers": payload.notify_customers,
            "notify_newsletter": payload.notify_newsletter,
        },
    )

    return _serialize(rule)
