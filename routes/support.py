from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from services import support as support_service
from services.audit import log_admin_action
from database.dependencies import get_db, get_current_active_user, get_admin_user

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/tickets", response_model=schemas.SupportTicket)
async def create_ticket(
    data: schemas.SupportTicketCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    return support_service.create_ticket(db, current_user, data, background_tasks)


@router.get("/tickets/my", response_model=List[schemas.SupportTicket])
async def my_tickets(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    return support_service.list_my_tickets(db, current_user.id)


@router.get("/tickets/{ticket_id}", response_model=schemas.SupportTicket)
async def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    return support_service.get_ticket(db, ticket_id, current_user.id, is_admin=current_user.is_admin)


@router.post("/tickets/{ticket_id}/messages", response_model=schemas.SupportMessage)
async def add_message(
    ticket_id: str,
    data: schemas.SupportMessageCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    # authorization
    support_service.get_ticket(db, ticket_id, current_user.id, is_admin=current_user.is_admin)
    sender = "admin" if current_user.is_admin else "user"
    sender_name = current_user.full_name if current_user.is_admin else None
    msg = support_service.add_message(db, ticket_id, sender, data.message, background_tasks, sender_name)
    if current_user.is_admin:
        log_admin_action(
            db,
            admin_user_id=current_user.id,
            action="support.message",
            entity_type="support_ticket",
            entity_id=ticket_id,
        )
    return msg


# Admin
@router.get("/tickets", response_model=List[schemas.SupportTicket])
async def all_tickets(db: Session = Depends(get_db), current_admin: models.User = Depends(get_admin_user)):
    return support_service.list_all_tickets(db)


@router.patch("/tickets/{ticket_id}", response_model=schemas.SupportTicket)
async def update_ticket(
    ticket_id: str,
    data: schemas.SupportTicketUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    if not data.status:
        return support_service.get_ticket(db, ticket_id, None, is_admin=True)
    ticket = support_service.update_ticket_status(db, ticket_id, data.status)
    log_admin_action(
        db,
        admin_user_id=current_admin.id,
        action="support.status",
        entity_type="support_ticket",
        entity_id=ticket_id,
        meta={"status": data.status},
    )
    return ticket
