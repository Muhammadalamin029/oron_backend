from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from services import addresses as addresses_service
from database.dependencies import get_db, get_current_active_user

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("/", response_model=List[schemas.Address])
async def list_addresses(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    return addresses_service.get_addresses(db, current_user.id)


@router.post("/", response_model=schemas.Address)
async def create_address(
    data: schemas.AddressCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    return addresses_service.create_address(db, current_user.id, data)


@router.patch("/{address_id}", response_model=schemas.Address)
async def update_address(
    address_id: str,
    data: schemas.AddressUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    return addresses_service.update_address(db, current_user.id, address_id, data)


@router.delete("/{address_id}")
async def delete_address(
    address_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    return addresses_service.delete_address(db, current_user.id, address_id)

