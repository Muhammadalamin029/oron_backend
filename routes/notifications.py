from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from schemas import Notification, User
from services import notifications as notification_service
from database.dependencies import get_db, get_current_active_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/", response_model=List[Notification])
async def get_notifications(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return notification_service.get_user_notifications(db, current_user.id, skip, limit)

@router.patch("/{notification_id}/read", response_model=Notification)
async def mark_read(notification_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    notif = notification_service.mark_notification_read(db, notification_id, current_user.id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif
