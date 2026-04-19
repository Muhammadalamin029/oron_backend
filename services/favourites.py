import uuid
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
import models

def add_favorite(db: Session, user_id: str, product_id: str):
    existing = db.query(models.Favorite).filter(models.Favorite.user_id == user_id, models.Favorite.product_id == product_id).first()
    if existing:
        return existing
        
    db_fav = models.Favorite(
        id=str(uuid.uuid4()),
        user_id=user_id,
        product_id=product_id
    )
    db.add(db_fav)
    db.commit()
    db.refresh(db_fav)
    return db_fav

def remove_favorite(db: Session, user_id: str, product_id: str):
    existing = db.query(models.Favorite).filter(models.Favorite.user_id == user_id, models.Favorite.product_id == product_id).first()
    if existing:
        db.delete(existing)
        db.commit()
    return {"ok": True}

def get_user_favorites(db: Session, user_id: str):
    return db.query(models.Favorite).options(
        joinedload(models.Favorite.product).joinedload(models.Product.category)
    ).filter(models.Favorite.user_id == user_id).all()
