import uuid
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, BackgroundTasks
import models
import schemas
from services.notifications import create_notification

def get_order(db: Session, order_id: str):
    return db.query(models.Order).options(
        joinedload(models.Order.items).joinedload(models.OrderItem.product).joinedload(models.Product.category),
        joinedload(models.Order.shipping_info),
        joinedload(models.Order.shipments),
    ).filter(models.Order.id == order_id).first()

def get_orders(db: Session, user_id: str, skip: int = 0, limit: int = 100):
    return db.query(models.Order).options(
        joinedload(models.Order.items).joinedload(models.OrderItem.product).joinedload(models.Product.category),
        joinedload(models.Order.shipping_info),
        joinedload(models.Order.shipments),
    ).filter(models.Order.user_id == user_id).offset(skip).limit(limit).all()

def get_all_orders(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Order).options(
        joinedload(models.Order.items).joinedload(models.OrderItem.product).joinedload(models.Product.category),
        joinedload(models.Order.shipping_info),
        joinedload(models.Order.shipments),
    ).offset(skip).limit(limit).all()

def get_or_create_cart(db: Session, user_id: str):
    cart = db.query(models.Order).options(
        joinedload(models.Order.items).joinedload(models.OrderItem.product).joinedload(models.Product.category),
        joinedload(models.Order.shipping_info),
        joinedload(models.Order.shipments),
    ).filter(models.Order.user_id == user_id, models.Order.status == "pending").first()
    if not cart:
        cart = models.Order(
            id=str(uuid.uuid4()),
            user_id=user_id,
            total_amount=0.0,
            status="pending"
        )
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart

def update_order_total(db: Session, order_id: str):
    order = db.query(models.Order).options(
        joinedload(models.Order.items).joinedload(models.OrderItem.product).joinedload(models.Product.category),
        joinedload(models.Order.shipping_info),
        joinedload(models.Order.shipments),
    ).filter(models.Order.id == order_id).first()
    total = sum([item.price * item.quantity for item in order.items])
    order.total_amount = total
    db.commit()
    db.refresh(order)
    return order

def add_to_cart(db: Session, user_id: str, product_id: str, quantity: int = 1):
    cart = get_or_create_cart(db, user_id)
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    existing_item = db.query(models.OrderItem).filter(models.OrderItem.order_id == cart.id, models.OrderItem.product_id == product_id).first()
    if existing_item:
        existing_item.quantity += quantity
    else:
        new_item = models.OrderItem(
            id=str(uuid.uuid4()),
            order_id=cart.id,
            product_id=product_id,
            quantity=quantity,
            price=product.price
        )
        db.add(new_item)
    db.commit()
    return update_order_total(db, cart.id)

def remove_from_cart(db: Session, user_id: str, product_id: str):
    cart = get_or_create_cart(db, user_id)
    item = db.query(models.OrderItem).filter(models.OrderItem.order_id == cart.id, models.OrderItem.product_id == product_id).first()
    if item:
        db.delete(item)
        db.commit()
    return update_order_total(db, cart.id)

def create_order(db: Session, order: schemas.OrderCreate, user_id: str, background_tasks: BackgroundTasks = None):
    total_amount = 0.0
    db_order = get_or_create_cart(db, user_id)
    
    # If they are passing items directly instead of using cart endpoint
    if order.items:
        # Clear existing items to rebuild cart
        db.query(models.OrderItem).filter(models.OrderItem.order_id == db_order.id).delete()
        db.commit()
        
        for item in order.items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

            if item.quantity <= 0:
                raise HTTPException(status_code=400, detail="Quantity must be at least 1")

            if product.stock < item.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")
                
            actual_price = product.price
            total_amount += actual_price * item.quantity
            
            db_item = models.OrderItem(
                id=str(uuid.uuid4()),
                order_id=db_order.id,
                product_id=product.id,
                quantity=item.quantity,
                price=actual_price 
            )
            db.add(db_item)
        db_order.total_amount = total_amount
        db.commit()
        db.refresh(db_order)
    
    notif_data = schemas.NotificationCreate(
        user_id=user_id,
        title="Cart Updated",
        message=f"Cart updated. Total amount: ${db_order.total_amount:,.2f}",
        type="order"
    )
    create_notification(db, notif_data, background_tasks)
    
    return db_order

def update_order_status(db: Session, order_id: str, status: str, background_tasks: BackgroundTasks = None):
    db_order = get_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    db_order.status = status
    db.commit()
    db.refresh(db_order)
    
    notif_data = schemas.NotificationCreate(
        user_id=db_order.user_id,
        title="Order Status Updated",
        message=f"Your order is now: {status}.",
        type="order"
    )
    create_notification(db, notif_data, background_tasks)
    
    return db_order

def delete_order(db: Session, order_id: str):
    db_order = get_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    db.delete(db_order)
    db.commit()
    return {"ok": True}
