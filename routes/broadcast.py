from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

import models
from core.config import settings
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


def _dispatch_broadcast_emails(
    recipients: list[str], subject: str, title: str, message: str, is_html: bool
):
    """Actually sends the emails. Runs as a background task, off the request
    thread — this loop opens a real SMTP connection per recipient, so running
    it inline in the request handler would hang the HTTP response until every
    email finished sending (or the connection timed out)."""
    for email in recipients:
        unsubscribe_url = f"{settings.FRONTEND_URL}/unsubscribe?email={quote(email)}"
        send_announcement_message(
            to_email=email,
            subject=subject,
            title=title,
            message=message,
            is_html=is_html,
            unsubscribe_url=unsubscribe_url,
        )


@router.post("/")
def send_messages(
    payload: BroadcastRequest,
    background_tasks: BackgroundTasks,
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

        background_tasks.add_task(
            _dispatch_broadcast_emails,
            recipients,
            payload.subject,
            payload.title,
            payload.message,
            payload.is_html,
        )

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
