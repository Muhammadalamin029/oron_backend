import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks

import models
import schemas
from services.notifications import create_notification


def get_order_shipments(db: Session, order_id: str):
    return (
        db.query(models.Shipment)
        .filter(models.Shipment.order_id == order_id)
        .order_by(models.Shipment.created_at.desc())
        .all()
    )


def create_shipment(db: Session, data: schemas.ShipmentCreate, background_tasks: BackgroundTasks = None):
    order = db.query(models.Order).filter(models.Order.id == data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    shipment = models.Shipment(
        id=str(uuid.uuid4()),
        order_id=data.order_id,
        carrier=data.carrier or "",
        tracking_number=data.tracking_number or "",
        status=data.status or "label_created",
        shipped_at=datetime.now(timezone.utc) if data.status == "in_transit" else None,
        delivered_at=datetime.now(timezone.utc) if data.status == "delivered" else None,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    notif_data = schemas.NotificationCreate(
        user_id=order.user_id,
        title=f"Shipment Created: Order #{order.id[-6:]}",
        message=f"Your order has shipped via {shipment.carrier or 'our carrier'}. Tracking: {shipment.tracking_number or 'N/A'}.",
        type="order",
    )
    create_notification(db, notif_data, background_tasks)

    return shipment


def update_shipment(db: Session, shipment_id: str, data: schemas.ShipmentUpdate, background_tasks: BackgroundTasks = None):
    shipment = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(shipment, key, value)

    db.commit()
    db.refresh(shipment)

    if "status" in update_data:
        order = db.query(models.Order).filter(models.Order.id == shipment.order_id).first()
        if order:
            notif_data = schemas.NotificationCreate(
                user_id=order.user_id,
                title=f"Shipment Update: Order #{order.id[-6:]}",
                message=f"Your shipment status is now: {shipment.status}.",
                type="order",
            )
            create_notification(db, notif_data, background_tasks)

    return shipment

