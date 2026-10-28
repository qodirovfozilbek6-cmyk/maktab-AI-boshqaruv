
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from sqlalchemy import Column, DateTime, ForeignKey, Integer, BigInteger, String, select
from sqlalchemy.orm import Session

from app.database import Base


class TelegramLink(Base):
    __tablename__ = "telegram_links"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    link_code_hash = Column(String(64), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    linked_at = Column(DateTime(timezone=True), nullable=True)


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def create_link_code(db: Session, user_id: int) -> tuple[str, datetime]:
    """Foydalanuvchi uchun 10 daqiqalik bir martalik kod yaratadi."""
    link = db.scalar(
        select(TelegramLink).where(TelegramLink.user_id == user_id)
    )

    if link is None:
        link = TelegramLink(user_id=user_id)
        db.add(link)

    if link.telegram_id is not None:
        raise ValueError("Telegram akkauntingiz allaqachon bog‘langan.")

    code = secrets.token_hex(4).upper()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    link.link_code_hash = _hash_code(code)
    link.expires_at = expires_at
    db.commit()

    return code, expires_at


def connect_telegram(
    db: Session,
    telegram_id: int,
    code: str,
) -> int:
    """Kod yaroqli bo‘lsa, Telegram akkauntini bog‘laydi."""
    now = datetime.now(timezone.utc)

    link = db.scalar(
        select(TelegramLink)
        .where(TelegramLink.link_code_hash == _hash_code(code))
        .with_for_update()
    )

    if link is None or not link.expires_at:
        raise ValueError("Kod noto‘g‘ri yoki muddati tugagan.")

    expiry = link.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if expiry <= now:
        link.link_code_hash = None
        link.expires_at = None
        db.commit()
        raise ValueError("Kod muddati tugagan. Yangi kod oling.")

    existing = db.scalar(
        select(TelegramLink).where(
            TelegramLink.telegram_id == telegram_id
        )
    )
    if existing is not None and existing.id != link.id:
        raise ValueError("Bu Telegram akkaunti boshqa foydalanuvchiga bog‘langan.")

    link.telegram_id = telegram_id
    link.linked_at = now
    link.link_code_hash = None
    link.expires_at = None
    db.commit()

    return link.user_id
