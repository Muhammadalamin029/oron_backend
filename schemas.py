from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# Base schemas
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True


# User schemas
class UserBase(BaseSchema):
    email: EmailStr
    full_name: str
    is_active: bool = True
    is_admin: bool = False
    is_verified: bool = False


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseSchema):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserInDB(UserBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class User(UserInDB):
    pass


# Authentication schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: User

class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# Notification schemas
class NotificationBase(BaseSchema):
    title: str
    message: str
    type: str = "system"


class NotificationCreate(NotificationBase):
    user_id: str


class Notification(NotificationBase):
    id: str
    user_id: str
    is_read: bool = False
    created_at: datetime


# Category schemas
class CategoryBase(BaseSchema):
    name: str
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None


class Category(CategoryBase):
    id: str
    created_at: datetime


# Product schemas
class ProductBase(BaseSchema):
    name: str
    description: str = ""
    price: float
    image_url: str = ""
    stock: int = 0
    is_active: bool = True


class ProductCreate(ProductBase):
    category_id: str


class ProductUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    category_id: Optional[str] = None
    stock: Optional[int] = None
    is_active: Optional[bool] = None


class Product(ProductBase):
    id: str
    category_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    category: Category


# Order schemas
class OrderItemBase(BaseSchema):
    quantity: int
    # Price is computed server-side during order creation; accepted for compatibility.
    price: float = 0.0


class OrderItemCreate(OrderItemBase):
    product_id: str


class OrderItem(OrderItemBase):
    id: str
    order_id: str
    product_id: str
    product: Product


class OrderBase(BaseSchema):
    total_amount: float
    status: str = "pending"


class OrderCreate(BaseSchema):
    items: List[OrderItemCreate]


class OrderUpdate(BaseSchema):
    status: Optional[str] = None


class Order(OrderBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[OrderItem]
    shipping_info: Optional["OrderShippingInfo"] = None
    shipments: List["Shipment"] = []


# Query parameters
class QueryParams(BaseModel):
    page: int = 1
    size: int = 10
    search: Optional[str] = None
    category: Optional[str] = None
    sort_by: Optional[str] = None
    sort_order: str = "desc"


# Paginated response
class PaginatedResponse(BaseModel):
    items: List[BaseModel]
    total: int
    page: int
    size: int
    pages: int


# Favorite schemas
class FavoriteBase(BaseSchema):
    product_id: str

class Favorite(FavoriteBase):
    id: str
    user_id: str
    created_at: datetime
    product: Product


# Payment schemas
class PaymentInitialize(BaseModel):
    order_id: str

class PaymentBase(BaseSchema):
    amount: float
    provider: str
    reference: str
    status: str

class Payment(PaymentBase):
    id: str
    order_id: str
    created_at: datetime

# Site Settings schemas
class SiteSettingBase(BaseSchema):
    value: str
    description: Optional[str] = None

class SiteSettingUpdate(SiteSettingBase):
    pass

class SiteSetting(SiteSettingBase):
    key: str
    updated_at: Optional[datetime] = None


# Reviews
class ReviewBase(BaseSchema):
    rating: int
    title: str = ""
    comment: str = ""


class ReviewCreate(ReviewBase):
    product_id: str


class ReviewUpdate(BaseSchema):
    rating: Optional[int] = None
    title: Optional[str] = None
    comment: Optional[str] = None


class Review(ReviewBase):
    id: str
    user_id: str
    product_id: str
    is_approved: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    user: Optional[User] = None


# Disputes
class DisputeBase(BaseSchema):
    order_id: str
    reason: str
    description: str = ""


class DisputeCreate(DisputeBase):
    pass


class DisputeUpdate(BaseSchema):
    status: Optional[str] = None
    resolution_note: Optional[str] = None


class Dispute(DisputeBase):
    id: str
    user_id: str
    status: str
    resolution_note: str = ""
    created_at: datetime
    updated_at: Optional[datetime] = None


# Addresses
class AddressBase(BaseSchema):
    label: str = ""
    phone: str = ""
    line1: str
    line2: str = ""
    city: str = ""
    state: str = ""
    country: str = "Nigeria"
    postal_code: str = ""
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseSchema):
    label: Optional[str] = None
    phone: Optional[str] = None
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    is_default: Optional[bool] = None


class Address(AddressBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None


# Order shipping info
class OrderShippingInfoBase(BaseSchema):
    email: str = ""
    phone: str = ""
    first_name: str = ""
    last_name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = "Nigeria"


class OrderShippingInfoCreate(OrderShippingInfoBase):
    pass


class OrderShippingInfo(OrderShippingInfoBase):
    id: str
    order_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None


# Shipments
class ShipmentBase(BaseSchema):
    carrier: str = ""
    tracking_number: str = ""
    status: str = "label_created"


class ShipmentCreate(ShipmentBase):
    order_id: str


class ShipmentUpdate(BaseSchema):
    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    status: Optional[str] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class Shipment(ShipmentBase):
    id: str
    order_id: str
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Support
class SupportTicketCreate(BaseSchema):
    subject: str
    message: str


class SupportMessageCreate(BaseSchema):
    message: str


class SupportMessage(BaseSchema):
    id: str
    ticket_id: str
    sender: str
    message: str
    created_at: datetime


class SupportTicket(BaseSchema):
    id: str
    user_id: Optional[str] = None
    email: str = ""
    subject: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: List[SupportMessage] = []


class SupportTicketUpdate(BaseSchema):
    status: Optional[str] = None


# Admin audit logs
class AdminAuditLog(BaseSchema):
    id: str
    admin_user_id: str
    action: str
    entity_type: str
    entity_id: str = ""
    meta: Optional[dict] = None
    created_at: datetime


# Resolve forward references
Order.model_rebuild()
