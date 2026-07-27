from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    # Fail fast on a stuck connection attempt instead of hanging indefinitely —
    # this DB sits behind a pooling proxy (Prisma) that can drop idle
    # connections; without a timeout, a dead TCP handshake can block the
    # whole request (and, in a single-worker dev server, every other request).
    connect_args={"connect_timeout": 10},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
