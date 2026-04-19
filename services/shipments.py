import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

import models
import schemas


def get_order_shipments(db: Session, order_id: str):
    return (
        db.query(models.Shipment)
        .filter(models.Shipment.order_id == order_id)
        .order_by(models.Shipment.created_at.desc())
        .all()
    )


def create_shipment(db: Session, data: schemas.ShipmentCreate):
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
    return shipment


def update_shipment(db: Session, shipment_id: str, data: schemas.ShipmentUpdate):
    shipment = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(shipment, key, value)

    db.commit()
    db.refresh(shipment)
    return shipment

