from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, products, orders, categories, notifications, favourites, payments, settings, reviews, disputes, addresses, shipments, support
from database.database import engine, SessionLocal
from models import Base
from utils.bootstrapping import preseed_settings, preseed_admin
from core.config import settings as app_settings

app = FastAPI(
    title="ORON Watch Marketplace API",
    description="Backend API for ORON luxury watch marketplace",
    version="1.0.0",
)

Base.metadata.create_all(bind=engine)

# Pre-seed site settings
db = SessionLocal()
try:
    preseed_settings(db)
    preseed_admin(db)
finally:
    db.close()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[app_settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(categories.router)
app.include_router(notifications.router)
app.include_router(favourites.router)
app.include_router(payments.router)
app.include_router(settings.router)
app.include_router(reviews.router)
app.include_router(disputes.router)
app.include_router(addresses.router)
app.include_router(shipments.router)
app.include_router(support.router)

@app.get("/")
async def root():
    return {"message": "ORON Watch Marketplace API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ORON API"}

