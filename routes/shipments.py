from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from services import shipments as shipments_service
from services import orders as orders_service
from services.audit import log_admin_action
from database.dependencies import get_db, get_current_active_user, get_admin_user

router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.get("/order/{order_id}", response_model=List[schemas.Shipment])
async def get_order_shipments(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    order = orders_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return shipments_service.get_order_shipments(db, order_id)


# Admin
@router.post("/", response_model=schemas.Shipment)
async def create_shipment(
    data: schemas.ShipmentCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    shipment = shipments_service.create_shipment(db, data)
    log_admin_action(
        db,
        admin_user_id=current_admin.id,
        action="shipment.create",
        entity_type="shipment",
        entity_id=shipment.id,
        meta={"order_id": shipment.order_id},
    )
    return shipment


@router.patch("/{shipment_id}", response_model=schemas.Shipment)
async def update_shipment(
    shipment_id: str,
    data: schemas.ShipmentUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    shipment = shipments_service.update_shipment(db, shipment_id, data)
    log_admin_action(
        db,
        admin_user_id=current_admin.id,
        action="shipment.update",
        entity_type="shipment",
        entity_id=shipment_id,
        meta=data.model_dump(exclude_unset=True),
    )
    return shipment
