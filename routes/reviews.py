from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from services import reviews as reviews_service
from services.audit import log_admin_action
from database.dependencies import get_db, get_current_active_user, get_admin_user, get_current_verified_user

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/product/{product_id}", response_model=List[schemas.Review])
async def get_product_reviews(product_id: str, db: Session = Depends(get_db)):
    return reviews_service.get_product_reviews(db, product_id, approved_only=True)


@router.post("/", response_model=schemas.Review)
async def create_review(
    data: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_verified_user),
):
    return reviews_service.create_review(db, current_user.id, data)


@router.patch("/{review_id}", response_model=schemas.Review)
async def update_review(
    review_id: str,
    data: schemas.ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_verified_user),
):
    return reviews_service.update_review(db, current_user.id, review_id, data)


@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        return {"ok": True}
    if review.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return reviews_service.delete_review(db, review_id)


# Admin
@router.get("/", response_model=List[schemas.Review])
async def get_all_reviews(db: Session = Depends(get_db), current_admin: models.User = Depends(get_admin_user)):
    return reviews_service.get_all_reviews(db)


@router.patch("/{review_id}/approve", response_model=schemas.Review)
async def approve_review(
    review_id: str,
    approved: bool = Query(True),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    review = reviews_service.set_review_approval(db, review_id, approved)
    log_admin_action(
        db,
        admin_user_id=current_admin.id,
        action="review.approve" if approved else "review.unapprove",
        entity_type="review",
        entity_id=review_id,
    )
    return review
