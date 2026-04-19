import httpx
import uuid
import hmac
import hashlib
import json
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, BackgroundTasks

import models
import schemas
from core.config import settings
from services.notifications import create_notification
from services.orders import get_order

def _finalize_successful_payment(db: Session, order: models.Order):
    """
    Marks order as paid and deducts stock once.
    """
    if order.status == "paid":
        return

    order.status = "paid"
    for item in order.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if product and product.stock >= item.quantity:
            product.stock -= item.quantity

async def initialize_payment(db: Session, order_id: str, user_id: str, email: str):
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending orders can be paid for")

    for item in order.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")
        
    amount_in_kobo = int(order.total_amount * 100)
    if amount_in_kobo <= 0:
        raise HTTPException(status_code=400, detail="Order amount must be greater than zero")

    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    reference = f"ORD-{order_id[-8:]}-{uuid.uuid4().hex[:8]}"
    
    data = {
        "email": email,
        "amount": amount_in_kobo,
        "reference": reference,
        "callback_url": f"{settings.FRONTEND_URL}/checkout/success",
        "metadata": {
            "order_id": order_id
        }
    }
    
    # We gracefully fallback to mock payment if no key is supplied
    if settings.PAYSTACK_SECRET_KEY == "sk_test_placeholder":
        db_payment = models.Payment(
            id=str(uuid.uuid4()),
            order_id=order_id,
            amount=order.total_amount,
            provider="paystack",
            reference=reference,
            status="pending"
        )
        db.add(db_payment)
        db.commit()
        return {
            "authorization_url": "https://paystack.com/mock-checkout",
            "access_code": "mocked_access_code",
            "reference": reference
        }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        
    if response.status_code != 200:
        print("Paystack Error:", response.text)
        raise HTTPException(status_code=400, detail="Failed to initialize payment with provider")
        
    response_data = response.json()
    if not response_data.get("status"):
        raise HTTPException(status_code=400, detail=response_data.get("message", "Payment initialization failed"))
        
    db_payment = models.Payment(
        id=str(uuid.uuid4()),
        order_id=order_id,
        amount=order.total_amount,
        provider="paystack",
        reference=reference,
        status="pending"
    )
    db.add(db_payment)
    db.commit()
    
    auth_url = response_data["data"]["authorization_url"]
    
    return {
        "authorization_url": auth_url,
        "access_code": response_data["data"]["access_code"],
        "reference": reference
    }

async def verify_payment(db: Session, reference: str, user_id: str):
    payment = db.query(models.Payment).filter(models.Payment.reference == reference).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    order = get_order(db, payment.order_id)
    if not order or order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # If we've already marked it successful locally, return it.
    if payment.status == "success":
        return {
            "reference": payment.reference,
            "status": payment.status,
            "amount": payment.amount,
            "order_id": payment.order_id,
            "order_status": order.status,
        }

    # With real keys, verify against Paystack to be deterministic.
    if settings.PAYSTACK_SECRET_KEY == "sk_test_placeholder":
        return {
            "reference": payment.reference,
            "status": payment.status,
            "amount": payment.amount,
            "order_id": payment.order_id,
            "order_status": order.status,
        }

    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to verify payment with provider")

    payload = response.json()
    if not payload.get("status"):
        raise HTTPException(status_code=400, detail=payload.get("message", "Payment verification failed"))

    provider_status = (payload.get("data") or {}).get("status")
    if provider_status == "success":
        payment.status = "success"
        _finalize_successful_payment(db, order)
        notif_data = schemas.NotificationCreate(
            user_id=order.user_id,
            title="Payment Verified",
            message=f"Your payment for order #{order.id[-6:]} has been verified. Status: paid.",
            type="payment",
        )
        create_notification(db, notif_data, background_tasks=None)
    elif provider_status in {"failed", "abandoned", "reversed"}:
        payment.status = "failed"
        db.commit()

    db.refresh(payment)
    db.refresh(order)
    return {
        "reference": payment.reference,
        "status": payment.status,
        "amount": payment.amount,
        "order_id": payment.order_id,
        "order_status": order.status,
    }

async def handle_webhook(db: Session, signature: str, payload_bytes: bytes, background_tasks: BackgroundTasks):
    expected_sign = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload_bytes,
        hashlib.sha512
    ).hexdigest()
    
    if expected_sign != signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(payload_bytes)
    
    event = payload.get("event")
    data = payload.get("data", {})
    
    if event == "charge.success":
        reference = data.get("reference")
        payment = db.query(models.Payment).filter(models.Payment.reference == reference).first()
        
        if payment and payment.status == "pending":
            payment.status = "success"
            
            # Update associated order
            order = db.query(models.Order).filter(models.Order.id == payment.order_id).first()
            if order:
                _finalize_successful_payment(db, order)
                
                notif_data = schemas.NotificationCreate(
                    user_id=order.user_id,
                    title="Payment Successful!",
                    message=f"Your payment for order #{order.id[-6:]} was completely successful. We are now processing your items.",
                    type="payment"
                )
                create_notification(db, notif_data, background_tasks)
            
            db.commit()
            
    return {"status": "ok"}

def get_user_payments(db: Session, user_id: str, skip: int = 0, limit: int = 100):
    """Get payments for a specific user with order details"""
    return (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.order).joinedload(models.Order.items).joinedload(models.OrderItem.product),
            joinedload(models.Payment.order).joinedload(models.Order.user)
        )
        .filter(models.Order.user_id == user_id)
        .order_by(models.Payment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_all_payments(db: Session, skip: int = 0, limit: int = 100):
    """Get all payments with comprehensive order and customer details"""
    return (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.order).joinedload(models.Order.items).joinedload(models.OrderItem.product),
            joinedload(models.Payment.order).joinedload(models.Order.user),
            joinedload(models.Payment.order).joinedload(models.Order.shipping_info)
        )
        .order_by(models.Payment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_payment_by_id(db: Session, payment_id: str):
    """Get a single payment with all related details"""
    payment = (
        db.query(models.Payment)
        .options(
            joinedload(models.Payment.order).joinedload(models.Order.items).joinedload(models.OrderItem.product),
            joinedload(models.Payment.order).joinedload(models.Order.user),
            joinedload(models.Payment.order).joinedload(models.Order.shipping_info),
            joinedload(models.Payment.order).joinedload(models.Order.shipments)
        )
        .filter(models.Payment.id == payment_id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
