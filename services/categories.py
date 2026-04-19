import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models
import schemas
from services.audit import log_admin_action

def get_category(db: Session, category_id: str):
    return db.query(models.Category).filter(models.Category.id == category_id).first()

def get_categories(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Category).offset(skip).limit(limit).all()

def create_category(db: Session, category: schemas.CategoryCreate, admin_user_id: str = None):
    db_category = models.Category(
        id=str(uuid.uuid4()),
        name=category.name,
        description=category.description
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    
    # Log category creation
    if admin_user_id:
        log_admin_action(
            db,
            admin_user_id=admin_user_id,
            action="category.created",
            entity_type="category",
            entity_id=db_category.id,
            meta={"name": category.name, "description": category.description}
        )
    
    return db_category

def update_category(db: Session, category_id: str, category_update: schemas.CategoryUpdate, admin_user_id: str = None):
    db_category = get_category(db, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
        
    old_values = {"name": db_category.name, "description": db_category.description}
    
    update_data = category_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)
        
    db.commit()
    db.refresh(db_category)
    
    # Log category update
    if admin_user_id:
        log_admin_action(
            db,
            admin_user_id=admin_user_id,
            action="category.updated",
            entity_type="category",
            entity_id=category_id,
            meta={"old_values": old_values, "new_values": update_data}
        )
    
    return db_category

def delete_category(db: Session, category_id: str, admin_user_id: str = None):
    db_category = get_category(db, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    category_data = {"name": db_category.name, "description": db_category.description}
        
    db.delete(db_category)
    db.commit()
    
    # Log category deletion
    if admin_user_id:
        log_admin_action(
            db,
            admin_user_id=admin_user_id,
            action="category.deleted",
            entity_type="category",
            entity_id=category_id,
            meta=category_data
        )
    
    return {"ok": True}
