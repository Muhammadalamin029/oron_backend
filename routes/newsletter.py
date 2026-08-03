from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from uuid import uuid4

import models
from database.dependencies import get_admin_user, get_db

router = APIRouter(prefix="/newsletter", tags=["newsletter"])


class SubscribeRequest(BaseModel):
    email: EmailStr


@router.post("/subscribe")
def subscribe(
    payload: SubscribeRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    existing = (
        db.query(models.NewsletterSubscriber)
        .filter(models.NewsletterSubscriber.email == email)
        .first()
    )
    if existing:
        return {"status": "ok", "detail": "You're already on the list!"}

    subscriber = models.NewsletterSubscriber(id=str(uuid4()), email=email)
    db.add(subscriber)
    db.commit()

    return {"status": "ok", "detail": "You're on the list!"}


@router.post("/unsubscribe")
def unsubscribe(
    payload: SubscribeRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    subscriber = (
        db.query(models.NewsletterSubscriber)
        .filter(models.NewsletterSubscriber.email == email)
        .first()
    )
    if subscriber:
        db.delete(subscriber)
        db.commit()

    # Always report success — whether or not this email was actually
    # subscribed, the end state the visitor wants (not receiving further
    # emails) is now true, and this avoids leaking subscription status.
    return {"status": "ok", "detail": "You have been unsubscribed."}


@router.get("/")
def list_subscribers(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user),
):
    subscribers = (
        db.query(models.NewsletterSubscriber)
        .order_by(models.NewsletterSubscriber.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "email": s.email,
            "created_at": s.created_at.isoformat() if s.created_at is not None else None,
        }
        for s in subscribers
    ]
