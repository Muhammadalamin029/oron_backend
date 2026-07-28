from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

import models
from services.orders import ORDER_STATUS_FLOW

RECENT_ORDERS_LIMIT = 5
TOP_PRODUCTS_LIMIT = 4
REVENUE_TREND_DAYS = 30


def get_dashboard_overview(db: Session) -> dict:
    total_revenue = db.query(func.sum(models.Payment.amount)) \
        .filter(models.Payment.status == "success") \
        .scalar() or 0.0

    total_orders = db.query(models.Order).count()
    total_products = db.query(models.Product).count()
    total_customers = db.query(models.User).filter(models.User.is_admin == False).count()

    orders = (
        db.query(models.Order)
        .options(
            joinedload(models.Order.user),
            joinedload(models.Order.items).joinedload(models.OrderItem.product),
        )
        .order_by(models.Order.created_at.desc())
        .limit(RECENT_ORDERS_LIMIT)
        .all()
    )
    recent_orders = [
        {
            "id": order.id,
            "total_amount": order.total_amount,
            "status": order.status,
            "created_at": order.created_at,
            "customer_name": order.user.full_name if order.user else "Customer",
            "customer_email": order.user.email if order.user else order.user_id,
            "product_name": order.items[0].product.name if order.items and order.items[0].product else "—",
        }
        for order in orders
    ]

    top_product_rows = (
        db.query(
            models.Product.id,
            models.Product.name,
            func.sum(models.OrderItem.quantity).label("units_sold"),
        )
        .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(models.Order.status.in_(ORDER_STATUS_FLOW))
        .group_by(models.Product.id, models.Product.name)
        .order_by(func.sum(models.OrderItem.quantity).desc())
        .limit(TOP_PRODUCTS_LIMIT)
        .all()
    )
    top_products = [
        {"product_id": row.id, "product_name": row.name, "units_sold": int(row.units_sold)}
        for row in top_product_rows
    ]

    open_disputes = db.query(models.Dispute).filter(models.Dispute.status == "open").count()
    open_support_tickets = db.query(models.SupportTicket).filter(models.SupportTicket.status == "open").count()

    now = datetime.now(timezone.utc)

    # "Still-live" pending payments only — status == 'pending' alone isn't meaningful here
    # because expiry is lazy (pending -> expired only flips when a customer loads their order's
    # status page; there's no sweep/cron), so a raw pending count would include stale, abandoned
    # attempts nobody ever triggered the flip for. Only count ones still within their window.
    pending_payments = (
        db.query(models.Payment)
        .filter(
            models.Payment.status == "pending",
            or_(models.Payment.expires_at.is_(None), models.Payment.expires_at > now),
        )
        .count()
    )

    cutoff = (now - timedelta(days=REVENUE_TREND_DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    # func.timezone("UTC", ...) forces bucketing to be deterministic regardless of the DB
    # session's timezone (this DB is accessed through a Prisma pooler, so session-level
    # settings shouldn't be assumed).
    day_bucket = func.date_trunc("day", func.timezone("UTC", models.Payment.created_at)).label("day")
    revenue_rows = (
        db.query(day_bucket, func.sum(models.Payment.amount).label("total"))
        .filter(models.Payment.status == "success", models.Payment.created_at >= cutoff)
        .group_by(day_bucket)
        .order_by(day_bucket)
        .all()
    )
    revenue_by_day = {row.day.date(): float(row.total) for row in revenue_rows}

    today = now.date()
    start_day = today - timedelta(days=REVENUE_TREND_DAYS - 1)
    revenue_trend = []
    d = start_day
    while d <= today:
        revenue_trend.append({"date": d, "revenue": revenue_by_day.get(d, 0.0)})
        d += timedelta(days=1)

    return {
        "stats": {
            "total_revenue": float(total_revenue),
            "total_orders": total_orders,
            "total_products": total_products,
            "total_customers": total_customers,
        },
        "recent_orders": recent_orders,
        "top_products": top_products,
        "needs_attention": {
            "open_disputes": open_disputes,
            "open_support_tickets": open_support_tickets,
            "pending_payments": pending_payments,
        },
        "revenue_trend": revenue_trend,
    }
