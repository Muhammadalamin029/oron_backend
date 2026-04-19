import uuid
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

import models
import schemas


PAID_STATUSES = {"paid", "completed", "delivered", "shipped", "success"}


def _user_has_purchased_product(db: Session, user_id: str, product_id: str) -> bool:
    q = (
        db.query(models.OrderItem)
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .filter(models.Order.user_id == user_id)
        .filter(models.OrderItem.product_id == product_id)
    )
    q = q.filter(models.Order.status.in_(list(PAID_STATUSES)))
    return db.query(q.exists()).scalar() is True


def get_product_reviews(db: Session, product_id: str, *, approved_only: bool = True):
    query = (
        db.query(models.Review)
        .options(joinedload(models.Review.user))
        .filter(models.Review.product_id == product_id)
        .order_by(models.Review.created_at.desc())
    )
    if approved_only:
        query = query.filter(models.Review.is_approved == True)  # noqa: E712
    return query.all()


def get_all_reviews(db: Session):
    return (
        db.query(models.Review)
        .options(joinedload(models.Review.user))
        .order_by(models.Review.created_at.desc())
        .all()
    )


def create_review(db: Session, user_id: str, data: schemas.ReviewCreate):
    if data.rating < 1 or data.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    product = db.query(models.Product).filter(models.Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if not _user_has_purchased_product(db, user_id, data.product_id):
        raise HTTPException(status_code=403, detail="Only verified buyers can leave reviews")

    existing = (
        db.query(models.Review)
        .filter(models.Review.user_id == user_id, models.Review.product_id == data.product_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this product")

    review = models.Review(
        id=str(uuid.uuid4()),
        user_id=user_id,
        product_id=data.product_id,
        rating=data.rating,
        title=data.title or "",
        comment=data.comment or "",
        is_approved=False,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def update_review(db: Session, user_id: str, review_id: str, data: schemas.ReviewUpdate):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = data.model_dump(exclude_unset=True)
    if "rating" in update_data:
        rating = update_data["rating"]
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    for key, value in update_data.items():
        setattr(review, key, value)
    # re-approval required after edit
    review.is_approved = False
    db.commit()
    db.refresh(review)
    return review


def delete_review(db: Session, review_id: str):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    db.commit()
    return {"ok": True}


def set_review_approval(db: Session, review_id: str, approved: bool):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.is_approved = approved
    db.commit()
    db.refresh(review)
    return review
