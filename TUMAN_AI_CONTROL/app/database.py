from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL


if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL topilmadi. Loyiha papkasidagi .env "
        "fayliga ulanish manzilini kiriting."
    )

IS_SQLITE = DATABASE_URL.startswith("sqlite")

if not (IS_SQLITE or DATABASE_URL.startswith("postgresql+psycopg://")):
    raise RuntimeError(
        "DATABASE_URL postgresql+psycopg:// yoki sqlite:/// bilan "
        "boshlanishi kerak."
    )


if IS_SQLITE:
    # SQLite: lokal ishlash va testlar uchun.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL / Neon
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
        connect_args={"connect_timeout": 10},
    )

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
