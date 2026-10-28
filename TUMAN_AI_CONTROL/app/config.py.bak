
import os
from pathlib import Path

from dotenv import load_dotenv

# Loyiha ildizi: D:\TUMAN_AI_CONTROL
BASE_DIR = Path(__file__).resolve().parent.parent

# .env faylini aniq manzildan yuklash
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE, override=False)


def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# Ilova
APP_NAME = get_env("APP_NAME", "MAKTAB AI CONTROL")
APP_ENV = get_env("APP_ENV", "development")

# Ma'lumotlar bazasi
DATABASE_URL = get_env("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        f"DATABASE_URL topilmadi. .env manzili: {ENV_FILE}"
    )

if not DATABASE_URL.startswith(("postgresql+psycopg://", "sqlite:///")):
    raise RuntimeError(
        "DATABASE_URL postgresql+psycopg:// (Neon) yoki "
        "sqlite:/// (lokal) bilan boshlanishi kerak."
    )

# JWT xavfsizligi
JWT_SECRET_KEY = get_env("JWT_SECRET_KEY")
JWT_EXPIRE_MINUTES = int(get_env("JWT_EXPIRE_MINUTES", "60"))

if len(JWT_SECRET_KEY) < 64:
    raise RuntimeError(
        "JWT_SECRET_KEY kamida 64 belgidan iborat bo'lishi kerak."
    )

if JWT_EXPIRE_MINUTES < 1:
    raise RuntimeError("JWT_EXPIRE_MINUTES kamida 1 bo'lishi kerak.")

# Birinchi administrator sozlamalari
BOOTSTRAP_ADMIN_USERNAME = get_env(
    "BOOTSTRAP_ADMIN_USERNAME", "admin"
).lower()

BOOTSTRAP_ADMIN_PASSWORD = get_env("BOOTSTRAP_ADMIN_PASSWORD")
BOOTSTRAP_ADMIN_FULL_NAME = get_env(
    "BOOTSTRAP_ADMIN_FULL_NAME",
    "MAKTAB AI CONTROL Administrator",
)

# Telegram
TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAME = get_env(
    "TELEGRAM_BOT_USERNAME"
).lstrip("@")

# Tokenning o'zini hech qachon logga chiqarmaymiz.
if not TELEGRAM_BOT_TOKEN:
    print(
        f"OGOHLANTIRISH: TELEGRAM_BOT_TOKEN topilmadi. "
        f".env manzili: {ENV_FILE}"
    )

if not TELEGRAM_BOT_USERNAME:
    print("OGOHLANTIRISH: TELEGRAM_BOT_USERNAME sozlanmagan.")
