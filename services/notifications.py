import uuid
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
import models
import schemas
from core.email import send_notification_email

def create_notification(db: Session, notification: schemas.NotificationCreate, background_tasks: BackgroundTasks = None):
    db_notif = models.Notification(
        id=str(uuid.uuid4()),
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        type=notification.type
    )
    db.add(db_notif)
    db.commit()
    db.refresh(db_notif)
    
    # Fire off email
    user = db.query(models.User).filter(models.User.id == notification.user_id).first()
    if user and background_tasks:
        background_tasks.add_task(send_notification_email, user.email, notification.title, notification.message)
    elif user and not background_tasks:
        # fallback to sync
        send_notification_email(user.email, notification.title, notification.message)
        
    return db_notif

def get_user_notifications(db: Session, user_id: str, skip: int = 0, limit: int = 100):
    return db.query(models.Notification).filter(models.Notification.user_id == user_id).order_by(models.Notification.created_at.desc()).offset(skip).limit(limit).all()

def mark_notification_read(db: Session, notification_id: str, user_id: str):
    notif = db.query(models.Notification).filter(models.Notification.id == notification_id, models.Notification.user_id == user_id).first()
    if notif:
        notif.is_read = True
        db.commit()
        db.refresh(notif)
    return notif

def create_admin_notification(db: Session, title: str, message: str, notification_type: str = "system", background_tasks: BackgroundTasks = None):
    """Create notifications for all admin users"""
    admin_users = db.query(models.User).filter(models.User.is_admin == True, models.User.is_active == True).all()
    
    notifications = []
    for admin in admin_users:
        notification = models.Notification(
            id=str(uuid.uuid4()),
            user_id=admin.id,
            title=title,
            message=message,
            type=notification_type
        )
        db.add(notification)
        notifications.append(notification)
    
    db.commit()
    
    # Send emails to all admins
    if background_tasks:
        for admin in admin_users:
            background_tasks.add_task(send_notification_email, admin.email, title, message)
    
    return notifications

def trigger_order_notifications(db: Session, order: models.Order, background_tasks: BackgroundTasks = None):
    """Trigger notifications for new orders"""
    # Notify admins about new order
    admin_title = f"New Order Received: #{order.id[-6:]}"
    admin_message = f"A new order of {order.total_amount:,.2f} NGN has been placed by {order.user.full_name if order.user else 'Customer'}."
    create_admin_notification(db, admin_title, admin_message, "order", background_tasks)
    
    # Notify customer about order confirmation
    if order.user:
        customer_title = f"Order Confirmed: #{order.id[-6:]}"
        customer_message = f"Your order of {order.total_amount:,.2f} NGN has been confirmed and is being processed."
        create_notification(
            db,
            schemas.NotificationCreate(
                user_id=order.user.id,
                title=customer_title,
                message=customer_message,
                type="order"
            ),
            background_tasks
        )

def trigger_payment_notifications(db: Session, payment: models.Payment, background_tasks: BackgroundTasks = None):
    """Trigger notifications for successful payments"""
    if payment.status == "success" and payment.order:
        # Notify admins about successful payment
        admin_title = f"Payment Received: #{payment.order.id[-6:]}"
        admin_message = f"Payment of {payment.amount:,.2f} NGN received for order #{payment.order.id[-6:]}."
        create_admin_notification(db, admin_title, admin_message, "payment", background_tasks)
        
        # Notify customer about payment confirmation
        if payment.order.user:
            customer_title = f"Payment Successful: #{payment.order.id[-6:]}"
            customer_message = f"Your payment of {payment.amount:,.2f} NGN has been successfully processed. Your order is now being prepared."
            create_notification(
                db,
                schemas.NotificationCreate(
                    user_id=payment.order.user.id,
                    title=customer_title,
                    message=customer_message,
                    type="payment"
                ),
                background_tasks
            )

def trigger_dispute_notifications(db: Session, dispute: models.Dispute, background_tasks: BackgroundTasks = None):
    """Trigger notifications for new disputes"""
    # Notify admins about new dispute
    admin_title = f"New Dispute Filed: #{dispute.order_id[-6:]}"
    admin_message = f"A new dispute has been filed for order #{dispute.order_id[-6:]} by {dispute.user.full_name if dispute.user else 'Customer'}. Reason: {dispute.reason}"
    create_admin_notification(db, admin_title, admin_message, "dispute", background_tasks)
