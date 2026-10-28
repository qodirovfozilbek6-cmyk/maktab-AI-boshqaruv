"""3-bosqich testlari: AI markazi endpointlari va ruxsat doirasi.

SQLite ishlatadi, Neon'ga tegmaydi. 2-bosqichdagi test ma'lumotlari
(`world`) qayta ishlatiladi.

Ishga tushirish:  py -3.11 -m pytest tests/test_step3_ai.py -v
"""

from tests.test_step2_scoping import world  # noqa: F401  (fixture)


def _get(world, path, who=None, **params):
    headers = world["H"][who] if who else {}
    return world["client"].get(path, headers=headers, params=params)


def _by_code(overview):
    return {b["code"]: b for b in overview["directions"]}


def test_overview_requires_login(world):
    assert _get(world, "/ai/overview").status_code == 401
    assert _get(world, "/ai/report").status_code == 401


def test_manager_overview_covers_all_directions_and_works_without_api_key(world):
    r = _get(world, "/ai/overview", "lider1")
    assert r.status_code == 200, r.text
    ov = r.json()

    assert ov["ai_mode"] == "local"
    assert "API kalit talab qilinmaydi" in ov["note"]

    by = _by_code(ov)
    for code in ("education", "media", "culture", "ecology", "sport",
                 "it_ai", "social"):
        assert code in by

    # Rahbariyat barcha maktablarni ko'radi: sport = 1-maktab + 2-maktab.
    assert by["sport"]["reports_total"] == 2
    assert by["media"]["reports_total"] == 1
    assert ov["totals"]["reports_total"] == 4
    assert ov["findings"] and ov["recommendations"] and ov["limitations"]


def test_coordinator_overview_is_limited_to_own_direction(world):
    r = _get(world, "/ai/overview", "c_sport")
    assert r.status_code == 200, r.text
    ov = r.json()

    codes = [b["code"] for b in ov["directions"]]
    # O'z yo'nalishi birinchi; rahbariyatning umumiy topshirig'i uchun
    # "yo'nalishsiz" blok qo'shilishi mumkin, boshqa yo'nalishlar esa yo'q.
    assert codes[0] == "sport"
    assert set(codes) <= {"sport", None}
    assert ov["totals"]["reports_total"] == 1      # boshqa maktab/yo'nalish yo'q
    assert ov["totals"]["projects_total"] == 1


def test_other_school_coordinator_sees_only_own_school(world):
    ov = _get(world, "/ai/overview", "c_other").json()
    assert ov["totals"]["reports_total"] == 1
    assert ov["totals"]["projects_total"] == 0
    assert ov["totals"]["tasks_total"] == 0


def test_advisor_overview_contains_only_own_items(world):
    ov = _get(world, "/ai/overview", "adv1").json()
    assert ov["totals"]["reports_total"] == 1
    assert ov["totals"]["tasks_total"] == 1
    # Maslahatchida yo'nalish yo'q: faqat "yo'nalishsiz" blok bo'ladi.
    assert [b["code"] for b in ov["directions"]] == [None]

    other = _get(world, "/ai/overview", "adv2").json()
    assert other["totals"]["reports_total"] == 0
    assert other["directions"] == []


def test_overview_window_is_validated(world):
    assert _get(world, "/ai/overview", "admin1", window_days=0).status_code == 422
    assert _get(world, "/ai/overview", "admin1", window_days=400).status_code == 422
    assert _get(world, "/ai/overview", "admin1", window_days=7).status_code == 200


def test_period_reports(world):
    week = _get(world, "/ai/report", "lider1", period="week")
    assert week.status_code == 200, week.text
    body = week.json()
    assert body["title"] == "Haftalik hisobot"
    assert "so'nggi 7 kun" in body["text"]
    assert "Sport: hisobot" in body["text"]

    month = _get(world, "/ai/report", "lider1", period="month").json()
    assert month["title"] == "Oylik hisobot"
    assert "so'nggi 30 kun" in month["text"]

    assert _get(world, "/ai/report", "lider1", period="year").status_code == 422


def test_period_report_is_scoped_for_coordinator(world):
    text = _get(world, "/ai/report", "c_sport", period="week").json()["text"]
    assert "Sport: hisobot" in text
    assert "Media: hisobot" not in text
    assert "Ta'lim: hisobot" not in text


def test_report_generation_is_audited(world):
    from app.database import SessionLocal
    from app.models import AuditLog
    from sqlalchemy import select

    _get(world, "/ai/report", "admin1", period="week")

    db = SessionLocal()
    try:
        row = db.scalar(
            select(AuditLog).where(AuditLog.entity_type == "ai_report")
        )
    finally:
        db.close()

    assert row is not None and row.action == "generate"
