"""panel_smoke.js uchun namunaviy ma'lumot tayyorlaydi (haqiqiy AI hisob-kitobi bilan).

Ishga tushirish (loyiha papkasidan):  py -3.11 tests/ui/make_data.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.ai_center import build_overview, build_period_report  # noqa: E402

now = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
dirs = [
    {"code": c, "name": n}
    for c, n in [
        ("education", "Ta'lim"), ("media", "Media"), ("culture", "Madaniyat"),
        ("ecology", "Ekologiya"), ("sport", "Sport"),
        ("it_ai", "IT va sun'iy intellekt"), ("social", "Ijtimoiy tashabbuslar"),
    ]
]
reports = [
    {"direction": "sport", "status": "submitted", "created_at": now - timedelta(days=9)},
    {"direction": "media", "status": "needs_revision", "created_at": now - timedelta(days=2)},
]
tasks = [
    {"id": 1, "title": "<b>Eski</b> topshiriq", "direction": "sport", "status": "pending", "deadline": now - timedelta(days=4)},
    {"id": 2, "title": "B", "direction": "media", "status": "completed", "deadline": None},
    {"id": 3, "title": "C", "direction": "media", "status": "completed", "deadline": None},
    {"id": 4, "title": "D", "direction": "media", "status": "completed", "deadline": None},
]

ov = build_overview(dirs, reports, [], tasks, now=now)
out = {
    "overview": ov,
    "week": build_period_report(ov, "week"),
    "dirs": [dict(d, id=i + 1, sort_order=i + 1, is_active=True) for i, d in enumerate(dirs)],
}
(Path(__file__).parent / "data.json").write_text(json.dumps(out), encoding="utf-8")
print("data.json tayyor")
