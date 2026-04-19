from sqlalchemy.orm import Session
from services import settings as settings_service
from services import auth as auth_service
from core.config import settings
import schemas
import models

def preseed_settings(db: Session):
    """
    Initializes the database with default site settings if they don't exist.
    """
    default_settings = [
        {
            "key": "site_name",
            "value": "ORON Watch Marketplace",
            "description": "The name of the platform displayed in headers and titles."
        },
        {
            "key": "contact_email",
            "value": "support@oron.com",
            "description": "Public contact email address for customer support."
        },
        {
            "key": "hero_title",
            "value": "Experience Luxury on Your Wrist",
            "description": "Main heading text on the landing page hero section."
        },
        {
            "key": "hero_subtitle",
            "value": "The premier marketplace for authentic luxury timepieces.",
            "description": "Subtitle text below the hero title."
        },
        {
            "key": "currency_symbol",
            "value": "$",
            "description": "Currency symbol used across the platform."
        }
    ]

    for setting in default_settings:
        # We use upsert logic but only if it doesn't exist? 
        # Actually, let's just use the service's upsert but only if the key is missing to avoid overwriting admin changes.
        existing = settings_service.get_setting_by_key(db, setting["key"])
        if not existing:
            settings_service.upsert_setting(
                db=db,
                key=setting["key"],
                value=setting["value"],
                description=setting["description"]
            )
            print(f"Pre-seeded setting: {setting['key']}")

def preseed_admin(db: Session):
    """
    Optionally creates an initial admin user from env vars.
    """
    email = settings.INITIAL_ADMIN_EMAIL.strip()
    password = settings.INITIAL_ADMIN_PASSWORD
    full_name = settings.INITIAL_ADMIN_FULL_NAME.strip() or "Admin"

    if not email or not password:
        return

    existing = auth_service.get_user_by_email(db, email)
    if existing:
        return

    user_create = schemas.UserCreate(email=email, full_name=full_name, password=password)
    auth_service.create_user(
        db=db,
        user=user_create,
        background_tasks=None,
        is_admin=True,
        is_verified=True,
        is_active=True,
        send_verification=False,
    )
    print(f"Pre-seeded admin user: {email}")
