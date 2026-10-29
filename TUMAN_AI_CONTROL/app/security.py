
from datetime import datetime, timedelta, timezone
import hmac

import jwt
from pwdlib import PasswordHash

from app.config import JWT_EXPIRE_MINUTES, JWT_SECRET_KEY


ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()

if len(JWT_SECRET_KEY) < 64:
    raise RuntimeError(
        "JWT_SECRET_KEY kamida 64 belgili tasodifiy maxfiy kalit bo'lishi kerak. "
        ".env faylini sozlang."
    )


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Parol kamida 8 belgidan iborat bo'lishi kerak.")
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hash.verify(password, hashed)
    except Exception:
        return False


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        if not payload.get("sub"):
            return None
        return payload
    except jwt.PyJWTError:
        return None


def constant_time_equal(first: str, second: str) -> bool:
    return hmac.compare_digest(first.encode(), second.encode())
