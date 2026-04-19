from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import schemas
from services import settings as settings_service
from services.audit import log_admin_action
from database.dependencies import get_db, get_admin_user

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/", response_model=List[schemas.SiteSetting])
async def get_all_settings(db: Session = Depends(get_db)):
    return settings_service.get_all_settings(db)

@router.get("/{key}", response_model=schemas.SiteSetting)
async def get_setting(key: str, db: Session = Depends(get_db)):
    setting = settings_service.get_setting_by_key(db, key)
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting

@router.post("/{key}", response_model=schemas.SiteSetting)
async def update_setting(
    key: str, 
    setting_data: schemas.SiteSettingUpdate, 
    db: Session = Depends(get_db), 
    current_admin = Depends(get_admin_user)
):
    setting = settings_service.upsert_setting(
        db=db, 
        key=key, 
        value=setting_data.value, 
        description=setting_data.description
    )
    log_admin_action(
        db,
        admin_user_id=current_admin.id,
        action="setting.upsert",
        entity_type="site_setting",
        entity_id=key,
        meta={"value": setting_data.value},
    )
    return setting
