import secrets
import uuid
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, BackgroundTasks

import models
import schemas
from core.config import settings
from services import auth as auth_service
from services import shipping_info as shipping_info_service
from services import payments as payments_service

RESERVED_SLUGS = {"admin", "sessions"}


def session_url(order_id: str) -> str:
    return f"{settings.FRONTEND_URL}/pay/session/{order_id}"


def _generate_unique_slug(db: Session) -> str:
    while True:
        slug = secrets.token_urlsafe(12)
        if slug in RESERVED_SLUGS:
            continue
        if not db.query(models.PaymentLink.id).filter(models.PaymentLink.slug == slug).first():
            return slug


def _link_query(db: Session):
    return db.query(models.PaymentLink).options(
        joinedload(models.PaymentLink.items).joinedload(models.PaymentLinkItem.product).joinedload(models.Product.category),
    )


# ---- Admin CRUD ----

def create_payment_link(db: Session, admin_user_id: str, data: schemas.PaymentLinkCreate) -> models.PaymentLink:
    link = models.PaymentLink(
        id=str(uuid.uuid4()),
        title=data.title,
        slug=_generate_unique_slug(db),
        created_by=admin_user_id,
        is_active=data.is_active,
    )
    db.add(link)
    db.flush()
    for item in data.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        db.add(models.PaymentLinkItem(
            id=str(uuid.uuid4()),
            payment_link_id=link.id,
            product_id=item.product_id,
            default_quantity=item.default_quantity,
        ))
    db.commit()
    return _link_query(db).filter(models.PaymentLink.id == link.id).first()


def list_payment_links(db: Session, skip: int = 0, limit: int = 100):
    return _link_query(db).order_by(models.PaymentLink.created_at.desc()).offset(skip).limit(limit).all()


def get_payment_link_admin(db: Session, payment_link_id: str) -> models.PaymentLink:
    link = _link_query(db).filter(models.PaymentLink.id == payment_link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Payment link not found")
    return link


def update_payment_link(db: Session, payment_link_id: str, data: schemas.PaymentLinkUpdate) -> models.PaymentLink:
    link = get_payment_link_admin(db, payment_link_id)
    if data.title is not None:
        link.title = data.title
    if data.is_active is not None:
        link.is_active = data.is_active
    if data.items is not None:
        if not data.items:
            raise HTTPException(status_code=400, detail="A payment link needs at least one product")
        # Full replace — simplest correct approach, avoids add/remove/quantity-diff edge cases.
        db.query(models.PaymentLinkItem).filter(models.PaymentLinkItem.payment_link_id == link.id).delete()
        for item in data.items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
            db.add(models.PaymentLinkItem(
                id=str(uuid.uuid4()),
                payment_link_id=link.id,
                product_id=item.product_id,
                default_quantity=item.default_quantity,
            ))
    db.commit()
    return get_payment_link_admin(db, payment_link_id)


def delete_payment_link(db: Session, payment_link_id: str):
    link = get_payment_link_admin(db, payment_link_id)
    db.delete(link)  # ondelete=SET NULL on Order.payment_link_id keeps order history intact
    db.commit()
    return {"ok": True}


def list_payment_link_orders(db: Session, payment_link_id: str, skip: int = 0, limit: int = 100):
    get_payment_link_admin(db, payment_link_id)  # 404 if the link itself doesn't exist
    return (
        db.query(models.Order)
        .options(
            joinedload(models.Order.items).joinedload(models.OrderItem.product).joinedload(models.Product.category),
            joinedload(models.Order.shipping_info),
            joinedload(models.Order.shipments),
            joinedload(models.Order.user),
        )
        .filter(models.Order.payment_link_id == payment_link_id)
        .order_by(models.Order.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ---- Public ----

def get_payment_link_by_slug(db: Session, slug: str) -> models.PaymentLink:
    link = _link_query(db).filter(
        models.PaymentLink.slug == slug,
        models.PaymentLink.is_active == True,
    ).first()
    if not link or not link.items:
        raise HTTPException(status_code=404, detail="Payment link not found")
    return link


async def guest_link_checkout(
    db: Session, slug: str, data: schemas.PaymentLinkCheckoutRequest, background_tasks: BackgroundTasks,
) -> dict:
    link = get_payment_link_by_slug(db, slug)
    allowed_ids = {i.product_id for i in link.items}

    if not data.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    submitted_ids = {i.product_id for i in data.items}
    if submitted_ids != allowed_ids:
        raise HTTPException(status_code=400, detail="All products on this payment link must be included in the order")

    for item in data.items:
        if item.quantity < 1:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1")

    full_name = f"{data.shipping.first_name} {data.shipping.last_name}".strip()
    user = auth_service.find_or_create_guest_account(db, data.shipping.email, full_name)
    # Intentionally no create_set_password_token / send_verify_and_set_password_email here —
    # this is the one deliberate deviation from guest_checkout()'s pattern: no login is ever
    # expected for this flow, so the customer must never be sent a "verify your email" gate.

    order = models.Order(
        id=str(uuid.uuid4()), user_id=user.id, total_amount=0.0, status="unpaid", payment_link_id=link.id,
    )
    db.add(order)
    db.flush()

    total_amount = 0.0
    for item in data.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
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

    charge = await payments_service.initiate_bank_transfer_charge(
        db, order.id, user.id, user.email, background_tasks,
        order_url=session_url(order.id),
    )
    return {**charge, "email": user.email}
