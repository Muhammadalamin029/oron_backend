import uuid
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, BackgroundTasks

import models
import schemas
from core.email import send_support_ticket_email, send_support_reply_email
from core.config import settings


def create_ticket(db: Session, current_user: models.User, data: schemas.SupportTicketCreate, background_tasks: BackgroundTasks = None):
    ticket = models.SupportTicket(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        email=current_user.email,
        subject=data.subject,
        status="open",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    msg = models.SupportMessage(
        id=str(uuid.uuid4()),
        ticket_id=ticket.id,
        sender="user",
        message=data.message,
    )
    db.add(msg)
    db.commit()
    
    # Send email notifications
    if background_tasks:
        # Send confirmation to user
        background_tasks.add_task(
            send_support_ticket_email,
            current_user.email,
            ticket.id,
            data.subject,
            data.message,
            is_admin=False
        )
        
        # Send notification to admin
        admin_email = settings.EMAILS_FROM_EMAIL  # or a dedicated admin email
        background_tasks.add_task(
            send_support_ticket_email,
            admin_email,
            ticket.id,
            data.subject,
            data.message,
            is_admin=True
        )
    
    return get_ticket(db, ticket.id, current_user.id, is_admin=False)


def get_ticket(db: Session, ticket_id: str, user_id: str | None, *, is_admin: bool):
    q = (
        db.query(models.SupportTicket)
        .options(joinedload(models.SupportTicket.messages))
        .filter(models.SupportTicket.id == ticket_id)
    )
    ticket = q.first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not is_admin and ticket.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return ticket


def list_my_tickets(db: Session, user_id: str):
    return (
        db.query(models.SupportTicket)
        .filter(models.SupportTicket.user_id == user_id)
        .order_by(models.SupportTicket.created_at.desc())
        .all()
    )


def list_all_tickets(db: Session):
    return (
        db.query(models.SupportTicket)
        .options(joinedload(models.SupportTicket.user))
        .order_by(models.SupportTicket.created_at.desc())
        .all()
    )


def add_message(db: Session, ticket_id: str, sender: str, message: str, background_tasks: BackgroundTasks = None, sender_name: str = None):
    ticket = db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    msg = models.SupportMessage(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        sender=sender,
        message=message,
    )
    db.add(msg)
    # update ticket status
    if sender == "admin":
        ticket.status = "answered"
    else:
        ticket.status = "open"
    db.commit()
    
    # Send email notifications
    if background_tasks:
        if sender == "admin" and ticket.user:
            # Send reply to user
            background_tasks.add_task(
                send_support_reply_email,
                ticket.user.email,
                ticket.id,
                ticket.subject,
                message,
                sender_name or "ORON Support Team",
                is_admin=False
            )
        elif sender == "user":
            # Send notification to admin
            admin_email = settings.EMAILS_FROM_EMAIL
            background_tasks.add_task(
                send_support_reply_email,
                admin_email,
                ticket.id,
                ticket.subject,
                message,
                sender_name or ticket.user.full_name if ticket.user else "Customer",
                is_admin=True
            )
    
    return msg


def update_ticket_status(db: Session, ticket_id: str, status: str):
    ticket = db.query(models.SupportTicket).filter(models.SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = status
    db.commit()
    db.refresh(ticket)
    return ticket

