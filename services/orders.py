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
        db_order.status = "unpaid"
        db.commit()
        db.refresh(db_order)

    notif_data = schemas.NotificationCreate(
        user_id=user_id,
        title="Order Placed",
        message=f"Your order is awaiting payment. Total amount: NGN {db_order.total_amount:,.2f}",
        type="order"
    )
    create_notification(db, notif_data, background_tasks)
    
    return db_order


# Admin-driven status flow. "paid" is reached only via the payment
# webhook/verify path (services/payments.py) and is never admin-settable —
# it has no predecessor in this list, so it's structurally unreachable
# through update_order_status below.
ORDER_STATUS_FLOW = ["paid", "processing", "shipped", "delivered"]
CANCELLABLE_FROM_STATUSES = {"paid", "processing", "shipped"}
TERMINAL_STATUSES = {"delivered", "cancelled"}
PAYMENT_GATED_STATUSES = {"pending", "unpaid", "expired"}


def get_next_status(current: str) -> str | None:
    if current not in ORDER_STATUS_FLOW:
        return None
    idx = ORDER_STATUS_FLOW.index(current)
    return ORDER_STATUS_FLOW[idx + 1] if idx + 1 < len(ORDER_STATUS_FLOW) else None


def update_order_status(db: Session, order_id: str, status: str, background_tasks: BackgroundTasks = None):
    db_order = get_order(db, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")

    current = db_order.status

    if current in PAYMENT_GATED_STATUSES:
        raise HTTPException(status_code=400, detail="This order must be paid before its status can be updated")
    if current in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Order is already {current} and its status can no longer be changed")

    if status == "cancelled":
        if current not in CANCELLABLE_FROM_STATUSES:
            raise HTTPException(status_code=400, detail=f"Order cannot be cancelled from status '{current}'")
    elif status in ORDER_STATUS_FLOW:
        expected = get_next_status(current)
        if status != expected:
            raise HTTPException(status_code=400, detail=f"Invalid transition: order is '{current}', next allowed status is '{expected or 'none'}'")
    else:
        raise HTTPException(status_code=400, detail=f"'{status}' is not a valid order status")

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
