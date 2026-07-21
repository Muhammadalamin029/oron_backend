import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks

import models
import schemas
from services import auth as auth_service
from services import shipping_info as shipping_info_service
from core.security import create_set_password_token
from core.email import send_verify_and_set_password_email


def guest_checkout(db: Session, data: schemas.GuestCheckoutRequest, background_tasks: BackgroundTasks):
    """
    Creates a guest account (or reuses an abandoned one), an unpaid order with
    priced/stock-checked items, and shipping info, in one atomic call — a
    first-time guest has no bearer token yet, so this can't be split across the
    existing authenticated create-order + upsert-shipping calls.
    """
    full_name = f"{data.shipping.first_name} {data.shipping.last_name}".strip()
    user = auth_service.find_or_create_guest_account(db, data.shipping.email, full_name)

    if not data.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    order = models.Order(id=str(uuid.uuid4()), user_id=user.id, total_amount=0.0, status="unpaid")
    db.add(order)
    db.flush()

    total_amount = 0.0
    for item in data.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1")
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")

        total_amount += product.price * item.quantity
        db.add(models.OrderItem(
            id=str(uuid.uuid4()),
            order_id=order.id,
            product_id=product.id,
            quantity=item.quantity,
            price=product.price,
        ))

    order.total_amount = total_amount
    db.commit()
    db.refresh(order)

    shipping_info_service.upsert_order_shipping_info(db, order.id, data.shipping)

    token = create_set_password_token(data={"sub": user.email, "order_id": order.id})
    background_tasks.add_task(send_verify_and_set_password_email, user.email, token)

    return {
        "order_id": order.id,
        "email": user.email,
        "message": "Check your email to verify your account and set a password.",
    }
