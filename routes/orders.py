from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from schemas import OrderCreate, OrderUpdate, Order, OrderItemBase
from services import orders as orders_service
from services import shipping_info as shipping_info_service
from services.audit import log_admin_action
from database.dependencies import get_db, get_current_active_user, get_admin_user, get_current_verified_user

router = APIRouter(prefix="/orders", tags=["orders"])

@router.get("/", response_model=List[Order])
async def get_orders(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    if current_user.is_admin:
        return orders_service.get_all_orders(db, skip=skip, limit=limit)
    return orders_service.get_orders(db, current_user.id, skip=skip, limit=limit)

@router.get("/cart", response_model=Order)
async def get_cart(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    return orders_service.get_or_create_cart(db, current_user.id)

@router.post("/cart/{product_id}", response_model=Order)
async def add_to_cart(product_id: str, quantity: int = 1, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    return orders_service.add_to_cart(db, current_user.id, product_id, quantity)

@router.delete("/cart/{product_id}", response_model=Order)
async def remove_from_cart(product_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    return orders_service.remove_from_cart(db, current_user.id, product_id)

@router.get("/{order_id}", response_model=Order)
async def get_order(order_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    order = orders_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to access this order")
    return order

@router.get("/{order_id}/shipping", response_model=schemas.OrderShippingInfo | None)
async def get_order_shipping(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    order = orders_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return shipping_info_service.get_order_shipping_info(db, order_id)

@router.post("/{order_id}/shipping", response_model=schemas.OrderShippingInfo)
async def upsert_order_shipping(
    order_id: str,
    data: schemas.OrderShippingInfoCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    order = orders_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    info = shipping_info_service.upsert_order_shipping_info(db, order_id, data)
    if current_user.is_admin:
        log_admin_action(
            db,
            admin_user_id=current_user.id,
            action="order.shipping.upsert",
            entity_type="order",
            entity_id=order_id,
        )
    return info

@router.post("/", response_model=Order)
async def create_order(order_data: OrderCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_verified_user)):
    return orders_service.create_order(db, order_data, current_user.id, background_tasks)

@router.patch("/{order_id}/status", response_model=Order)
async def update_order_status(order_id: str, status: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    order = orders_service.update_order_status(db, order_id, status, background_tasks)
    log_admin_action(
        db,
        admin_user_id=current_admin.id,
        action="order.status",
        entity_type="order",
        entity_id=order_id,
        meta={"status": status},
    )
    return order

@router.delete("/{order_id}")
async def delete_order(order_id: str, db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    res = orders_service.delete_order(db, order_id)
    log_admin_action(db, admin_user_id=current_admin.id, action="order.delete", entity_type="order", entity_id=order_id)
    return res
