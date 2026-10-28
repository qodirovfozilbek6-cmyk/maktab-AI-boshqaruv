
from pathlib import Path
import re

path = Path("app/static/js/panel.js")
source = path.read_text(encoding="utf-8")

# Zaxira nusxa mavjud bo'lmasa, asl faylni saqlab qo'yamiz.
backup = path.with_suffix(".js.telegram-backup")
if not backup.exists():
    backup.write_text(source, encoding="utf-8")

# Bo'lim sarlavhasi
if "telegram: [\"Telegram bog'lash\"" not in source:
    source, count = re.subn(
        r'(\s+audit:\s*\["Audit jurnali",\s*"Muhim amallar tarixi"\])',
        r'\1,\n    telegram: ["Telegram bog\'lash", '
        r'"Telegram akkauntingizni tizimga ulash"]',
        source,
        count=1,
    )
    if count != 1:
        raise SystemExit("SECTION_TITLES topilmadi. Fayl o'zgartirilmadi.")

# Navigatsiya belgisi
if "telegram:" not in source[source.find("var NAV_ICONS"):source.find("var STATUS")]:
    source, count = re.subn(
        r'(var NAV_ICONS\s*=\s*\{.*?)(\n\s*\};)',
        r'\1,\n    telegram: "✉"\2',
        source,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise SystemExit("NAV_ICONS topilmadi. Fayl o'zgartirilmadi.")

# Har bir rolning menyusiga Telegram qo'shish
for role in (
    "admin", "director", "kelajak_leader", "coordinator",
    "school_advisor", "district_coordinator", "school_coordinator"
):
    pattern = rf'({role}:\s*\{{.*?sections:\s*\[)([^\]]*)(\])'
    match = re.search(pattern, source, re.S)
    if not match:
        raise SystemExit(f"{role} roli topilmadi. Fayl o'zgartirilmadi.")
    sections = match.group(2)
    if '"telegram"' not in sections and "'telegram'" not in sections:
        source = (
            source[:match.start(2)]
            + sections.rstrip() + ', "telegram"'
            + source[match.end(2):]
        )

# Telegram sahifasini marshrutlashga ulash
if "telegram: viewTelegramLink" not in source:
    pattern = r'(ai:\s*viewAI,\s*users:\s*viewUsers,\s*directions:\s*viewDirections,\s*audit:\s*viewAudit)(\s*\})'
    source, count = re.subn(
        pattern, r'\1,\n    telegram: viewTelegramLink\2',
        source, count=1
    )
    if count != 1:
        raise SystemExit("VIEWS joyi topilmadi. Fayl o'zgartirilmadi.")

path.write_text(source, encoding="utf-8")
print("Tayyor: Telegram menyusi barcha rollarga ulandi.")
print("Zaxira nusxa:", backup)
