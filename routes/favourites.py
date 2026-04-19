from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
from schemas import Favorite
from services import favourites as fav_service
from database.dependencies import get_db, get_current_active_user

router = APIRouter(prefix="/favourites", tags=["favourites"])

@router.get("/", response_model=List[Favorite])
async def get_favorites(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    return fav_service.get_user_favorites(db, current_user.id)

@router.post("/{product_id}", response_model=Favorite)
async def add_favorite(product_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    return fav_service.add_favorite(db, current_user.id, product_id)

@router.delete("/{product_id}")
async def remove_favorite(product_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    return fav_service.remove_favorite(db, current_user.id, product_id)
