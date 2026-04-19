import uuid
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, BackgroundTasks

import models
import schemas
from core.email import send_dispute_email
from core.config import settings


def get_my_disputes(db: Session, user_id: str):
    return (
        db.query(models.Dispute)
        .options(joinedload(models.Dispute.order))
        .filter(models.Dispute.user_id == user_id)
        .order_by(models.Dispute.created_at.desc())
        .all()
    )


def get_all_disputes(db: Session):
    return (
        db.query(models.Dispute)
        .options(joinedload(models.Dispute.order), joinedload(models.Dispute.user))
        .order_by(models.Dispute.created_at.desc())
        .all()
    )


def create_dispute(db: Session, user_id: str, data: schemas.DisputeCreate, background_tasks: BackgroundTasks = None):
    order = db.query(models.Order).filter(models.Order.id == data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    existing = (
        db.query(models.Dispute)
        .filter(models.Dispute.order_id == data.order_id, models.Dispute.user_id == user_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="A dispute already exists for this order")

    dispute = models.Dispute(
        id=str(uuid.uuid4()),
        user_id=user_id,
        order_id=data.order_id,
        reason=data.reason,
        description=data.description or "",
        status="open",
        resolution_note="",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    
    # Send email notifications
    if background_tasks:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            # Send confirmation to user
            background_tasks.add_task(
                send_dispute_email,
                user.email,
                dispute.id,
                order.id,
                data.reason,
                data.description or "",
                is_admin=False
            )
            
            # Send notification to admin
            admin_email = settings.EMAILS_FROM_EMAIL
            background_tasks.add_task(
                send_dispute_email,
                admin_email,
                dispute.id,
                order.id,
                data.reason,
                data.description or "",
                is_admin=True
            )
    
    return dispute


def update_dispute(db: Session, dispute_id: str, data: schemas.DisputeUpdate):
    dispute = db.query(models.Dispute).filter(models.Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(dispute, key, value)
    db.commit()
    db.refresh(dispute)
    return dispute

