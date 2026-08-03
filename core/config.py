import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path)

class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "fallback-secret-here-12345")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Frontend (for CORS + links)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # Email settings — sent via Brevo's HTTP API (not raw SMTP), since hosts
    # like Render block/drop outbound SMTP ports but always allow HTTPS.
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    EMAILS_FROM_EMAIL: str = os.getenv("EMAILS_FROM_EMAIL", "noreply@oron.com")
    EMAILS_FROM_NAME: str = "ORON Watch Marketplace"
    
    # Payments
    PAYSTACK_SECRET_KEY: str = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_placeholder")
    PAYSTACK_PUBLIC_KEY: str = os.getenv("PAYSTACK_PUBLIC_KEY", "")
    PAYSTACK_CHARGE_EXPIRY_MINUTES: int = int(os.getenv("PAYSTACK_CHARGE_EXPIRY_MINUTES", "30"))

    # Optional bootstrap admin (dev/prod first admin)
    INITIAL_ADMIN_EMAIL: str = os.getenv("INITIAL_ADMIN_EMAIL", "")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    INITIAL_ADMIN_FULL_NAME: str = os.getenv("INITIAL_ADMIN_FULL_NAME", "Admin")

settings = Settings()
