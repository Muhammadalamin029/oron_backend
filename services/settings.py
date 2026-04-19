from sqlalchemy.orm import Session
from fastapi import HTTPException
import models
import schemas

def get_setting_by_key(db: Session, key: str):
    return db.query(models.SiteSetting).filter(models.SiteSetting.key == key).first()

def get_all_settings(db: Session):
    return db.query(models.SiteSetting).all()

def upsert_setting(db: Session, key: str, value: str, description: str = None):
    db_setting = get_setting_by_key(db, key)
    if db_setting:
        db_setting.value = value
        if description is not None:
            db_setting.description = description
    else:
        db_setting = models.SiteSetting(
            key=key,
            value=value,
            description=description
        )
        db.add(db_setting)
    
    db.commit()
    db.refresh(db_setting)
    return db_setting
