import uuid
from sqlalchemy.orm import Session, joinedload, selectinload
from fastapi import HTTPException
from sqlalchemy import or_
import models
import schemas

def get_product(db: Session, product_id: str):
    return db.query(models.Product).options(joinedload(models.Product.category), selectinload(models.Product.images)).filter(models.Product.id == product_id).first()

def get_products(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    category: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
):
    query = db.query(models.Product).options(joinedload(models.Product.category), selectinload(models.Product.images))

    if category:
        query = query.join(models.Product.category).filter(models.Category.name == category)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Product.name.ilike(pattern),
                models.Product.description.ilike(pattern),
            )
        )

    sort_by = (sort_by or "created_at").lower()
    sort_order = (sort_order or "desc").lower()

    sort_map = {
        "price": models.Product.price,
        "name": models.Product.name,
        "created_at": models.Product.created_at,
    }
    sort_col = sort_map.get(sort_by)
    if sort_col is None:
        raise HTTPException(status_code=400, detail="Invalid sort_by value")

    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    elif sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        raise HTTPException(status_code=400, detail="Invalid sort_order value")

    return query.offset(skip).limit(limit).all()

def create_product(db: Session, product: schemas.ProductCreate):
    images = list(product.images) if product.images else ([product.image_url] if product.image_url else [])
    primary_image = images[0] if images else ""

    db_product = models.Product(
        id=str(uuid.uuid4()),
        name=product.name,
        description=product.description,
        price=product.price,
        image_url=primary_image,
        category_id=product.category_id,
        stock=product.stock,
        is_active=product.is_active
    )
    db.add(db_product)
    db.flush()

    for position, image_url in enumerate(images):
        db.add(models.ProductImage(
            id=str(uuid.uuid4()),
            product_id=db_product.id,
            image_url=image_url,
            position=position,
        ))

    db.commit()
    db.refresh(db_product)
    return db_product

def update_product(db: Session, product_id: str, product_update: schemas.ProductUpdate):
    db_product = get_product(db, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product_update.model_dump(exclude_unset=True)
    images = update_data.pop("images", None)
    for key, value in update_data.items():
        setattr(db_product, key, value)

    if images is not None:
        db_product.images.clear()
        for position, image_url in enumerate(images):
            db_product.images.append(models.ProductImage(
                id=str(uuid.uuid4()),
                image_url=image_url,
                position=position,
            ))
        db_product.image_url = images[0] if images else ""

    db.commit()
    db.refresh(db_product)
    return db_product

def delete_product(db: Session, product_id: str):
    db_product = get_product(db, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    db.delete(db_product)
    db.commit()
    return {"ok": True}
