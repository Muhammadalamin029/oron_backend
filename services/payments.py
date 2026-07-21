import httpx
import uuid
import hmac
import hashlib
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, BackgroundTasks

import models
import schemas
from core.config import settings
from core.email import send_bank_transfer_details_email, send_bank_transfer_expired_email
from services.notifications import create_notification
from services.orders import get_order
from services import shipping_info as shipping_info_service


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


def _payment_to_charge_response(payment: models.Payment) -> dict:
    return {
        "payment_id": payment.id,
        "order_id": payment.order_id,
        "reference": payment.reference,
        "status": payment.status,
        "amount": payment.amount,
        "bank_name": payment.bank_name,
        "account_number": payment.account_number,
        "account_name": payment.account_name,
        "expires_at": payment.expires_at,
    }


async def initiate_bank_transfer_charge(db: Session, order_id: str, user_id: str, email: str, background_tasks: BackgroundTasks):
    order = get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if order.status not in ("unpaid", "expired"):
        raise HTTPException(status_code=400, detail="Order is not awaiting payment")

    # Idempotency: reuse an existing still-valid pending charge instead of minting
    # a new Paystack account (and sending a new email) on every page load/refresh.
    existing = (
        db.query(models.Payment)
        .filter(models.Payment.order_id == order_id, models.Payment.status == "pending")
        .order_by(models.Payment.created_at.desc())
        .first()
    )
    if existing and existing.expires_at and existing.expires_at > datetime.now(timezone.utc):
        if order.status == "expired":
            order.status = "unpaid"
            db.commit()
        return _payment_to_charge_response(existing)

    for item in order.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")

    amount_in_kobo = int(order.total_amount * 100)
    if amount_in_kobo <= 0:
        raise HTTPException(status_code=400, detail="Order amount must be greater than zero")

    reference = f"ORD-{order_id[-8:]}-{uuid.uuid4().hex[:8]}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PAYSTACK_CHARGE_EXPIRY_MINUTES)
    meta_payload = None

    # We gracefully fall back to a mock account number if no real key is supplied.
    if settings.PAYSTACK_SECRET_KEY == "sk_test_placeholder":
        bank_name = "Mock Bank"
        account_number = f"90{uuid.uuid4().int % 10**8:08d}"
        account_name = f"ORON/{order_id[-6:]}"
    else:
        url = "https://api.paystack.co/charge"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "email": email,
            "amount": amount_in_kobo,
            "reference": reference,
            "currency": "NGN",
            "bank_transfer": {
                "account_expires_at": expires_at.isoformat(),
            },
            "metadata": {"order_id": order_id},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data)

        if response.status_code != 200:
            print("Paystack Error:", response.text)
            raise HTTPException(status_code=400, detail="Failed to initiate bank transfer with provider")

        response_data = response.json()
        if not response_data.get("status"):
            raise HTTPException(status_code=400, detail=response_data.get("message", "Charge initiation failed"))

        payload = response_data.get("data") or {}
        meta_payload = payload
        # Verified against a live Paystack sandbox call: account details are
        # top-level on `data` (not nested under a `bank_transfer` key — that's
        # only a request param), and `bank` is an object with a `name` field.
        bank_name = (payload.get("bank") or {}).get("name")
        account_number = payload.get("account_number")
        account_name = payload.get("account_name")

        # Paystack's sandbox has been observed to clamp account_expires_at to a
        # shorter window than requested — trust their echoed value when present
        # so our lazy-expiry check matches what Paystack actually enforces.
        returned_expiry = payload.get("account_expires_at")
        if returned_expiry:
            try:
                expires_at = datetime.fromisoformat(returned_expiry.replace("Z", "+00:00"))
            except ValueError:
                pass

    if order.status == "expired":
        order.status = "unpaid"

    db_payment = models.Payment(
        id=str(uuid.uuid4()),
        order_id=order_id,
        amount=order.total_amount,
        provider="paystack",
        reference=reference,
        status="pending",
        method="bank_transfer",
        bank_name=bank_name,
        account_number=account_number,
        account_name=account_name,
        expires_at=expires_at,
        meta=meta_payload,
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    background_tasks.add_task(
        send_bank_transfer_details_email,
        email, order_id, bank_name, account_number, account_name, order.total_amount, expires_at,
    )

    return _payment_to_charge_response(db_payment)


def get_payment_status(db: Session, order_id: str, user_id: str, background_tasks: BackgroundTasks):
    order = get_order(db, order_id)
    if not order or order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    payment = (
        db.query(models.Payment)
        .filter(models.Payment.order_id == order_id)
        .order_by(models.Payment.created_at.desc())
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="No payment initiated for this order")

    # Lazy expiry detection: fires exactly once, since the pending -> expired
    # transition removes the payment from matching this branch again.
    if payment.status == "pending" and payment.expires_at and datetime.now(timezone.utc) > payment.expires_at:
        payment.status = "expired"
        if order.status == "unpaid":
            order.status = "expired"
        db.commit()
        db.refresh(payment)
        db.refresh(order)

        shipping = shipping_info_service.get_order_shipping_info(db, order_id)
        if shipping and shipping.email:
            background_tasks.add_task(send_bank_transfer_expired_email, shipping.email, order_id)

    seconds_remaining = None
    if payment.expires_at:
        seconds_remaining = max(0, int((payment.expires_at - datetime.now(timezone.utc)).total_seconds()))

    return {
        "order_id": order.id,
        "payment_id": payment.id,
        "payment_status": payment.status,
        "order_status": order.status,
        "amount": payment.amount,
        "bank_name": payment.bank_name,
        "account_number": payment.account_number,
        "account_name": payment.account_name,
        "expires_at": payment.expires_at,
        "seconds_remaining": seconds_remaining,
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

        # Guard against "already handled" using != "success" rather than == "pending":
        # the lazy expiry check on the order-details page can flip a payment to
        # "expired" moments before Paystack's webhook confirms the transfer actually
        # landed, and that payment must still be finalizable when the webhook arrives.
        if payment and payment.status != "success":
            payment.status = "success"

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
