from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from services import payments as payments_service
from database.dependencies import get_db, get_current_verified_user, get_current_active_user, get_admin_user

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/initialize")
async def initialize_payment(
    data: schemas.PaymentInitialize, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_verified_user)
):
    return await payments_service.initialize_payment(db, data.order_id, current_user.id, current_user.email)

@router.get("/verify/{reference}")
async def verify_payment(
    reference: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    return await payments_service.verify_payment(db, reference, current_user.id)

@router.get("/my-payments", response_model=List[schemas.Payment])
async def get_user_payments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_verified_user)
):
    return payments_service.get_user_payments(db, current_user.id, skip, limit)

@router.get("/admin/all-payments", response_model=List[schemas.Payment])
async def get_all_payments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user)
):
    return payments_service.get_all_payments(db, skip, limit)

@router.get("/admin/{payment_id}", response_model=schemas.Payment)
async def get_payment_details(
    payment_id: str,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user)
):
    return payments_service.get_payment_by_id(db, payment_id)

@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_paystack_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    if not x_paystack_signature:
        raise HTTPException(status_code=400, detail="Missing signature header")
        
    payload_bytes = await request.body()
    return await payments_service.handle_webhook(db, x_paystack_signature, payload_bytes, background_tasks)
