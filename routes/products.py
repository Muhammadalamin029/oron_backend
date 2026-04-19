from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from schemas import ProductCreate, ProductUpdate, Product, PaginatedResponse
from services import products as products_service
from services.audit import log_admin_action
from database.dependencies import get_db, get_admin_user

router = APIRouter(prefix="/products", tags=["products"])

@router.get("/", response_model=List[Product])
async def get_products(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
):
    return products_service.get_products(
        db,
        skip=skip,
        limit=limit,
        search=search,
        category=category,
        sort_by=sort_by,
        sort_order=sort_order,
    )

@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: str, db: Session = Depends(get_db)):
    product = products_service.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.post("/", response_model=Product)
async def create_product(product_data: ProductCreate, db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    product = products_service.create_product(db=db, product=product_data)
    log_admin_action(db, admin_user_id=current_admin.id, action="product.create", entity_type="product", entity_id=product.id)
    return product

@router.patch("/{product_id}", response_model=Product)
async def update_product(product_id: str, product_data: ProductUpdate, db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    product = products_service.update_product(db, product_id, product_data)
    log_admin_action(db, admin_user_id=current_admin.id, action="product.update", entity_type="product", entity_id=product_id, meta=product_data.model_dump(exclude_unset=True))
    return product

@router.delete("/{product_id}")
async def delete_product(product_id: str, db: Session = Depends(get_db), current_admin = Depends(get_admin_user)):
    res = products_service.delete_product(db, product_id)
    log_admin_action(db, admin_user_id=current_admin.id, action="product.delete", entity_type="product", entity_id=product_id)
    return res
