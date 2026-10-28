"""1-bosqich migratsiyasi: yo'nalishlar va users.direction ustuni.

Ishga tushirish (loyiha papkasidan):
    py -3.11 -m scripts.migrate_step1

Faqat qo'shadi, hech narsani o'chirmaydi va ustidan yozmaydi.
Ishga tushirishdan oldin Neon'da zaxira (branch) oling.
"""

from app.database import SessionLocal, engine
from app.directions import ensure_schema, seed_directions


def main():
    actions = ensure_schema(engine)

    for action in actions:
        print("-", action)

    if not actions:
        print("- Sxema allaqachon yangi. O'zgarish kerak bo'lmadi.")

    db = SessionLocal()
    try:
        added = seed_directions(db)
    finally:
        db.close()

    if added:
        print(f"- {added} ta dastlabki yo'nalish qo'shildi.")
    else:
        print("- Yo'nalishlar allaqachon mavjud, tegilmadi.")

    print("Tayyor.")


if __name__ == "__main__":
    main()
