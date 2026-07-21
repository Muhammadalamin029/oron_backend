from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

import schemas
from services import checkout as checkout_service
from database.dependencies import get_db
from utils.rate_limit import rate_limiter

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.post("/guest", response_model=schemas.GuestCheckoutResponse)
async def guest_checkout(
    data: schemas.GuestCheckoutRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limiter.limit(key="checkout.guest", max_requests=10, window_seconds=60)),
):
    return checkout_service.guest_checkout(db, data, background_tasks)
