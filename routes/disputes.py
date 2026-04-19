from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from services import disputes as disputes_service
from services.audit import log_admin_action
from database.dependencies import get_db, get_current_active_user, get_admin_user

router = APIRouter(prefix="/disputes", tags=["disputes"])


@router.get("/my", response_model=List[schemas.Dispute])
async def get_my_disputes(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_active_user)):
    return disputes_service.get_my_disputes(db, current_user.id)


@router.post("/", response_model=schemas.Dispute)
async def create_dispute(
    data: schemas.DisputeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    return disputes_service.create_dispute(db, current_user.id, data, background_tasks)


# Admin
@router.get("/", response_model=List[schemas.Dispute])
async def get_all_disputes(db: Session = Depends(get_db), current_admin: models.User = Depends(get_admin_user)):
    return disputes_service.get_all_disputes(db)


@router.patch("/{dispute_id}", response_model=schemas.Dispute)
async def update_dispute(
    dispute_id: str,
    data: schemas.DisputeUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_admin_user),
):
    dispute = disputes_service.update_dispute(db, dispute_id, data)
    log_admin_action(
        db,
        admin_user_id=current_admin.id,
        action="dispute.update",
        entity_type="dispute",
        entity_id=dispute_id,
        meta=data.model_dump(exclude_unset=True),
    )
    return dispute

