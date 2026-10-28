"""Yo'nalishlar va xavfsiz (faqat qo'shuvchi) sxema yangilash.

Bu modul mavjud jadvallarni o'chirmaydi va ma'lumotlarni o'zgartirmaydi:
  * yetishmayotgan `direction` ustunini (users, reports, projects, tasks) qo'shadi;
  * `directions` jadvalini yaratadi (agar yo'q bo'lsa);
  * jadval bo'sh bo'lsagina 7 ta dastlabki yo'nalishni qo'shadi.
"""

from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Direction

# Dastlabki taklif. Rasmiy nomlar farq qilsa, admin panelidan
# (PATCH /admin/directions/{id}) o'zgartiriladi.
DEFAULT_DIRECTIONS = [
    ("education", "Ta'lim"),
    ("media", "Media"),
    ("culture", "Madaniyat"),
    ("ecology", "Ekologiya"),
    ("sport", "Sport"),
    ("it_ai", "IT va sun'iy intellekt"),
    ("social", "Ijtimoiy tashabbuslar"),
]


# `direction` ustuni qo'shiladigan jadvallar.
DIRECTION_TABLES = ("users", "reports", "projects", "tasks")


def ensure_schema(engine: Engine) -> list[str]:
    """Faqat qo'shuvchi migratsiya. Bajarilgan amallar ro'yxatini qaytaradi."""
    done: list[str] = []

    Direction.__table__.create(bind=engine, checkfirst=True)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in DIRECTION_TABLES:
        if table not in existing_tables:
            continue

        columns = {col["name"] for col in inspector.get_columns(table)}

        if "direction" in columns:
            continue

        with engine.begin() as conn:
            conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN direction VARCHAR(50)")
            )
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS ix_{table}_direction "
                    f"ON {table} (direction)"
                )
            )

        done.append(f"{table}.direction ustuni qo'shildi")

    return done


def seed_directions(db: Session) -> int:
    """Jadval bo'sh bo'lsagina dastlabki yo'nalishlarni qo'shadi."""
    if db.scalar(select(Direction.id).limit(1)) is not None:
        return 0

    for order, (code, name) in enumerate(DEFAULT_DIRECTIONS, start=1):
        db.add(Direction(code=code, name=name, sort_order=order))

    db.commit()
    return len(DEFAULT_DIRECTIONS)
