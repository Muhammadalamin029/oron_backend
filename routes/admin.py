from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

import models
import schemas
from database.dependencies import get_db, get_admin_user
from typing import List

router = APIRouter(prefix="/admin", tags=["admin"])

class DashboardStats(BaseModel):
    total_revenue: float
    total_orders: int
    total_products: int
    total_customers: int

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    revenue = db.query(func.sum(models.Order.total_amount))\
        .filter(models.Order.status.in_(['paid', 'completed', 'success', 'shipped', 'delivered']))\
        .scalar() or 0.0

    total_orders = db.query(models.Order).count()
    total_products = db.query(models.Product).count()
    total_customers = db.query(models.User).filter(models.User.is_admin == False).count()

    return DashboardStats(
        total_revenue=float(revenue),
        total_orders=total_orders,
        total_products=total_products,
        total_customers=total_customers
    )

@router.get("/orders", response_model=List[schemas.OrderWithUser])
async def get_all_orders_with_users(db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    orders = db.query(models.Order).order_by(models.Order.created_at.desc()).all()
    # Eager loading isn't strictly necessary if relationship is configured, but let's manual join or just return if relationship exists
    # If relationship doesn't exist, we manually attach. Let's see if models.Order has user relationship.
    # Usually it's better to just return the objects if the relationship is configured correctly.
    # Let's attach user manually just in case:
    for order in orders:
        if not hasattr(order, 'user') or not order.user:
            order.user = db.query(models.User).filter(models.User.id == order.user_id).first()
    return orders

@router.get("/users/stats", response_model=List[schemas.UserWithStats])
async def get_users_with_stats(db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    users = db.query(models.User).filter(models.User.is_admin == False).all()
    # Compute stats
    user_stats = db.query(
        models.Order.user_id,
        func.count(models.Order.id).label("total_orders"),
        func.sum(models.Order.total_amount).label("total_spent")
    ).filter(models.Order.status.in_(['paid', 'completed', 'success', 'shipped', 'delivered']))\
    .group_by(models.Order.user_id).all()
    
    stats_map = {us.user_id: {"total_orders": us.total_orders, "total_spent": us.total_spent or 0.0} for us in user_stats}
    
    for u in users:
        u.total_orders = stats_map.get(u.id, {}).get("total_orders", 0)
        u.total_spent = stats_map.get(u.id, {}).get("total_spent", 0.0)
    
    return users

@router.get("/disputes", response_model=List[schemas.DisputeWithDetails])
async def get_disputes_with_details(db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    disputes = db.query(models.Dispute).order_by(models.Dispute.created_at.desc()).all()
    for dispute in disputes:
        dispute.user = db.query(models.User).filter(models.User.id == dispute.user_id).first()
        dispute.order = db.query(models.Order).filter(models.Order.id == dispute.order_id).first()
    return disputes
