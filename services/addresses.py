import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException

import models
import schemas


def get_addresses(db: Session, user_id: str):
    return (
        db.query(models.Address)
        .filter(models.Address.user_id == user_id)
        .order_by(models.Address.is_default.desc(), models.Address.created_at.desc())
        .all()
    )


def create_address(db: Session, user_id: str, data: schemas.AddressCreate):
    if data.is_default:
        db.query(models.Address).filter(models.Address.user_id == user_id).update({"is_default": False})

    addr = models.Address(
        id=str(uuid.uuid4()),
        user_id=user_id,
        label=data.label or "",
        phone=data.phone or "",
        line1=data.line1,
        line2=data.line2 or "",
        city=data.city or "",
        state=data.state or "",
        country=data.country or "Nigeria",
        postal_code=data.postal_code or "",
        is_default=bool(data.is_default),
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr


def update_address(db: Session, user_id: str, address_id: str, data: schemas.AddressUpdate):
    addr = db.query(models.Address).filter(models.Address.id == address_id).first()
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")
    if addr.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("is_default") is True:
        db.query(models.Address).filter(models.Address.user_id == user_id).update({"is_default": False})
    for key, value in update_data.items():
        setattr(addr, key, value)
    db.commit()
    db.refresh(addr)
    return addr


def delete_address(db: Session, user_id: str, address_id: str):
    addr = db.query(models.Address).filter(models.Address.id == address_id).first()
    if not addr:
        return {"ok": True}
    if addr.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(addr)
    db.commit()
    return {"ok": True}

