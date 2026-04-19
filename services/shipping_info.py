import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException

import models
import schemas


def upsert_order_shipping_info(db: Session, order_id: str, data: schemas.OrderShippingInfoCreate):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    existing = db.query(models.OrderShippingInfo).filter(models.OrderShippingInfo.order_id == order_id).first()
    if existing:
        for key, value in data.model_dump().items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing

    info = models.OrderShippingInfo(
        id=str(uuid.uuid4()),
        order_id=order_id,
        **data.model_dump(),
    )
    db.add(info)
    db.commit()
    db.refresh(info)
    return info


def get_order_shipping_info(db: Session, order_id: str):
    return db.query(models.OrderShippingInfo).filter(models.OrderShippingInfo.order_id == order_id).first()

