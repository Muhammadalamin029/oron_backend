from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from schemas import CategoryCreate, CategoryUpdate, Category
from services import categories as categories_service
from database.dependencies import get_db, get_admin_user

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/", response_model=List[Category])
async def get_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return categories_service.get_categories(db, skip=skip, limit=limit)

@router.post("/", response_model=Category)
async def create_category(category_data: CategoryCreate, db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    return categories_service.create_category(db=db, category=category_data, admin_user_id=current_admin.id)

@router.patch("/{category_id}", response_model=Category)
async def update_category(category_id: str, category_update: CategoryUpdate, db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    return categories_service.update_category(db, category_id, category_update, admin_user_id=current_admin.id)

@router.delete("/{category_id}")
async def delete_category(category_id: str, db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    return categories_service.delete_category(db, category_id, admin_user_id=current_admin.id)
