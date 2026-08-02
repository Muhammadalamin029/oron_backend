from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

import models
from core.email import send_announcement_message
from database.dependencies import get_admin_user, get_db

router = APIRouter(prefix="/broadcast", tags=["broadcast"])


class BroadcastRequest(BaseModel):
    title: str
    subject: str
    message: str
    include_customers: bool = False
    include_newsletter: bool = False
    custom_recipients: list[EmailStr] = Field(default_factory=list)
    is_html: bool = False
    unsubscribe_url: Optional[str] = None


@router.post("/")
def send_messages(
    payload: BroadcastRequest,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user),
):
    try:
        recipients: list[str] = []

        for email in payload.custom_recipients:
            recipients.append(str(email).strip().lower())

        if payload.include_customers:
            customer_users = (
                db.query(models.User).filter(models.User.is_admin.is_(False)).all()
            )
            for user in customer_users:
                if user.email is not None:
                    recipients.append(user.email.strip().lower())

        if payload.include_newsletter:
            subscribers = db.query(models.NewsletterSubscriber).all()
            for subscriber in subscribers:
                recipients.append(subscriber.email.strip().lower())

        recipients = list(dict.fromkeys(recipients))
        if not recipients:
            raise HTTPException(
                status_code=400, detail="No recipients selected for broadcast."
            )

        for email in recipients:
            send_announcement_message(
                to_email=email,
                subject=payload.subject,
                title=payload.title,
                message=payload.message,
                is_html=payload.is_html,
                unsubscribe_url=payload.unsubscribe_url,
            )

        saved_message = models.BroadcastMessage(
            id=str(uuid4()),
            sent_by_admin_id=admin_user.id,
            subject=payload.subject,
            title=payload.title,
            message=payload.message,
            include_customers=payload.include_customers,
            include_newsletter=payload.include_newsletter,
            recipient_count=len(recipients),
            recipient_emails=recipients,
        )

        db.add(saved_message)
        db.commit()
        db.refresh(saved_message)

        return {
            "status": "ok",
            "detail": "Broadcast sent successfully.",
            "broadcast_id": saved_message.id,
            "recipient_count": len(recipients),
            "include_customers": payload.include_customers,
            "include_newsletter": payload.include_newsletter,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
def get_broadcasts(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user),
):
    broadcasts = (
        db.query(models.BroadcastMessage)
        .order_by(models.BroadcastMessage.created_at.desc())
        .all()
    )

    payload = []
    for item in broadcasts:
        payload.append(
            {
                "id": item.id,
                "subject": item.subject,
                "title": item.title,
                "message": item.message,
                "include_customers": item.include_customers,
                "include_newsletter": item.include_newsletter,
                "recipient_count": item.recipient_count,
                "recipient_emails": item.recipient_emails or [],
                "created_at": (
                    item.created_at.isoformat() if item.created_at is not None else None
                ),
                "sent_by_admin": (
                    item.sent_by_admin.full_name if item.sent_by_admin else "System"
                ),
            }
        )

    return payload
