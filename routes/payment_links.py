from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from services import payment_links as payment_links_service
from services import payments as payments_service
from services import orders as orders_service
from database.dependencies import get_db, get_admin_user
from utils.rate_limit import rate_limiter

router = APIRouter(prefix="/payment-links", tags=["payment-links"])


def _get_link_order_or_404(db: Session, order_id: str) -> models.Order:
    """
    Authorizes public /sessions/{order_id}/* calls by the order_id itself
    (an unguessable UUID) rather than a logged-in session — the same trust
    model Stripe/PayPal checkout-session links use. Scoped strictly to
    orders that actually originated from a payment link: payment_link_id is
    only ever set inside guest_link_checkout, so an authenticated
    customer's own orders always 404 here.
    """
    order = orders_service.get_order(db, order_id)
    if not order or order.payment_link_id is None:
        raise HTTPException(status_code=404, detail="Not found")
    return order


# ---------------------------------------------------------------------------
# Admin (literal /admin prefix — declared before the {slug} catch-all below,
# since Starlette resolves routes via linear first-match scan and a request
# to /payment-links/admin would otherwise incorrectly match slug="admin").
# ---------------------------------------------------------------------------

@router.get("/admin", response_model=List[schemas.PaymentLink])
async def list_payment_links(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    return payment_links_service.list_payment_links(db, skip, limit)


@router.post("/admin", response_model=schemas.PaymentLink)
async def create_payment_link(
    data: schemas.PaymentLinkCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    return payment_links_service.create_payment_link(db, current_admin.id, data)


@router.get("/admin/{payment_link_id}", response_model=schemas.PaymentLink)
async def get_payment_link(
    payment_link_id: str,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    return payment_links_service.get_payment_link_admin(db, payment_link_id)


@router.patch("/admin/{payment_link_id}", response_model=schemas.PaymentLink)
async def update_payment_link(
    payment_link_id: str,
    data: schemas.PaymentLinkUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    return payment_links_service.update_payment_link(db, payment_link_id, data)


@router.delete("/admin/{payment_link_id}")
async def delete_payment_link(
    payment_link_id: str,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    return payment_links_service.delete_payment_link(db, payment_link_id)


@router.get("/admin/{payment_link_id}/sessions", response_model=List[schemas.OrderWithUser])
async def list_payment_link_sessions(
    payment_link_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    return payment_links_service.list_payment_link_orders(db, payment_link_id, skip, limit)


# ---------------------------------------------------------------------------
# Public sessions (literal /sessions prefix — also declared before {slug}).
# ---------------------------------------------------------------------------

@router.get("/sessions/{order_id}", response_model=schemas.Order)
async def public_get_session(
    order_id: str,
    db: Session = Depends(get_db),
):
    return _get_link_order_or_404(db, order_id)


@router.get("/sessions/{order_id}/status", response_model=schemas.PaymentStatusResponse)
async def public_payment_status(
    order_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limiter.limit(key="payment_links.status", max_requests=30, window_seconds=60)),
):
    order = _get_link_order_or_404(db, order_id)
    return payments_service.get_payment_status(db, order_id, order.user_id, background_tasks)


@router.post("/sessions/{order_id}/charge", response_model=schemas.ChargeInitiateResponse)
async def public_initiate_charge(
    order_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limiter.limit(key="payment_links.charge", max_requests=10, window_seconds=60)),
):
    order = _get_link_order_or_404(db, order_id)
    return await payments_service.initiate_bank_transfer_charge(
        db, order_id, order.user_id, order.user.email, background_tasks,
        order_url=payment_links_service.session_url(order_id),
    )


@router.post("/sessions/{order_id}/verify", response_model=schemas.PaymentStatusResponse)
async def public_verify_payment(
    order_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limiter.limit(key="payment_links.verify", max_requests=5, window_seconds=60)),
):
    order = _get_link_order_or_404(db, order_id)
    return await payments_service.verify_payment_with_paystack(db, order_id, order.user_id, background_tasks)


# ---------------------------------------------------------------------------
# Public checkout (single-segment catch-all — must be declared last).
# ---------------------------------------------------------------------------

@router.get("/{slug}", response_model=schemas.PaymentLinkPublic)
async def get_public_payment_link(
    slug: str,
    db: Session = Depends(get_db),
):
    return payment_links_service.get_payment_link_by_slug(db, slug)


@router.post("/{slug}/checkout", response_model=schemas.PaymentLinkCheckoutResponse)
async def public_checkout(
    slug: str,
    data: schemas.PaymentLinkCheckoutRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limiter.limit(key="payment_links.checkout", max_requests=10, window_seconds=60)),
):
    return await payment_links_service.guest_link_checkout(db, slug, data, background_tasks)
