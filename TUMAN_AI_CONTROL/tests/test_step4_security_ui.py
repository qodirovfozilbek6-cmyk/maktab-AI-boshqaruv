"""4-bosqich testlari: sahifalar, xavfsizlik sarlavhalari va login cheklovi.

SQLite ishlatadi, Neon'ga tegmaydi. 2-bosqichdagi test ma'lumotlari
(`world`) qayta ishlatiladi.

Ishga tushirish:  py -3.11 -m pytest tests/test_step4_security_ui.py -v
"""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import AuditLog
from tests.test_step2_scoping import PASSWORD, world  # noqa: F401  (fixture)


def _login(world, username, password):
    return world["client"].post(
        "/auth/login", data={"username": username, "password": password}
    )


def _reset_limiter():
    from app.main import login_limiter

    for key in list(login_limiter._failures) + list(login_limiter._locked_until):
        login_limiter.reset(key)


def test_pages_and_static_files_are_served(world):
    c = world["client"]

    for path in ("/", "/login", "/panel", "/admin"):
        r = c.get(path)
        assert r.status_code == 200, path
        assert "text/html" in r.headers["content-type"], path

    assert "MAKTAB AI CONTROL" in c.get("/panel").text
    assert "/static/js/panel.js" in c.get("/panel").text
    assert "MAKTAB AI CONTROL" in c.get("/login").text

    assert c.get("/static/css/maktab.css").status_code == 200
    assert c.get("/static/js/panel.js").status_code == 200


def test_security_headers_are_set(world):
    r = world["client"].get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "same-origin"


def test_unknown_user_is_locked_after_five_failures(world):
    _reset_limiter()

    for _ in range(5):
        assert _login(world, "limit_user", "noto'g'ri-parol-123").status_code == 401

    r = _login(world, "limit_user", "noto'g'ri-parol-123")
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    assert "soniyadan keyin" in r.json()["detail"]

    _reset_limiter()


def test_real_user_is_locked_even_with_correct_password_then_recovers(world):
    _reset_limiter()

    for _ in range(5):
        assert _login(world, "adv2", "noto'g'ri-parol-123").status_code == 401

    assert _login(world, "adv2", PASSWORD).status_code == 429   # blok davomida

    db = SessionLocal()
    try:
        row = db.scalar(
            select(AuditLog).where(AuditLog.action == "login_locked")
        )
    finally:
        db.close()
    assert row is not None                                      # blok qayd etildi

    _reset_limiter()                                            # blok muddatini kutmaslik uchun
    assert _login(world, "adv2", PASSWORD).status_code == 200


def test_successful_login_resets_failure_counter(world):
    _reset_limiter()

    for _ in range(3):
        assert _login(world, "adv1", "noto'g'ri-parol-123").status_code == 401

    assert _login(world, "adv1", PASSWORD).status_code == 200   # hisob nolga tushadi

    for _ in range(3):
        assert _login(world, "adv1", "noto'g'ri-parol-123").status_code == 401

    assert _login(world, "adv1", PASSWORD).status_code == 200   # hali bloklanmagan

    _reset_limiter()
