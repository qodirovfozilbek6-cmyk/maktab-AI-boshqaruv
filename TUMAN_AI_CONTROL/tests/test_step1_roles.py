"""1-bosqich testlari: rollar, yo'nalishlar, xavfsiz migratsiya.

SQLite xotirada ishlaydi, Neon'ga tegmaydi.
Ishga tushirish:  py -3.11 -m pytest tests/test_step1_roles.py -v
"""

import os

# config.py import qilinishidan OLDIN sozlanishi shart.
os.environ["DATABASE_URL"] = "sqlite:///./test_maktab.db"
os.environ["JWT_SECRET_KEY"] = "t" * 64
os.environ["TELEGRAM_BOT_TOKEN"] = ""   # bot ishga tushmasin

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import School, User
from app.security import hash_password

PASSWORD = "Sinov-parol-12345"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:   # lifespan: create_all + ensure_schema + seed
        db = SessionLocal()
        db.add(School(name="Sinov maktabi"))
        db.add(
            User(
                username="admin1",
                full_name="Admin Sinov",
                password_hash=hash_password(PASSWORD),
                role="admin",
            )
        )
        db.commit()
        db.close()
        yield c
    Base.metadata.drop_all(bind=engine)


def login(client, username, password=PASSWORD):
    r = client.post(
        "/auth/login", data={"username": username, "password": password}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_user(client, admin, **kw):
    payload = {
        "username": "user1",
        "full_name": "Sinov Foydalanuvchi",
        "password": PASSWORD,
        "role": "coordinator",
        "school_id": 1,
        "direction": "sport",
    }
    payload.update(kw)
    return client.post("/admin/users", json=payload, headers=admin)


def test_seven_default_directions(client):
    admin = login(client, "admin1")
    r = client.get("/directions", headers=admin)
    assert r.status_code == 200
    assert len(r.json()) == 7


def test_coordinator_needs_valid_direction(client):
    admin = login(client, "admin1")
    assert make_user(client, admin, direction=None).status_code == 422
    assert make_user(client, admin, direction="yoq").status_code == 422
    assert make_user(client, admin).status_code == 201


def test_only_one_active_kelajak_leader(client):
    admin = login(client, "admin1")
    r1 = make_user(
        client, admin, username="lider1", role="kelajak_leader",
        school_id=None, direction=None,
    )
    assert r1.status_code == 201
    r2 = make_user(
        client, admin, username="lider2", role="kelajak_leader",
        school_id=None, direction=None,
    )
    assert r2.status_code == 409


def test_cannot_create_or_grant_admin(client):
    admin = login(client, "admin1")
    assert make_user(client, admin, role="admin").status_code == 403
    make_user(client, admin)
    uid = client.get("/users", headers=admin).json()[-1]["id"]
    r = client.patch(
        f"/admin/users/{uid}", json={"role": "admin"}, headers=admin
    )
    assert r.status_code == 403


def test_coordinator_cannot_manage_users(client):
    admin = login(client, "admin1")
    make_user(client, admin)
    coord = login(client, "user1")
    r = client.post(
        "/admin/users",
        json={
            "username": "xuser1", "full_name": "Xx Xx", "password": PASSWORD,
            "role": "coordinator", "school_id": 1, "direction": "media",
        },
        headers=coord,
    )
    assert r.status_code == 403


def test_direction_in_use_cannot_be_deactivated(client):
    admin = login(client, "admin1")
    make_user(client, admin)  # sport
    dirs = client.get("/directions", headers=admin).json()
    sport = next(d for d in dirs if d["code"] == "sport")
    r = client.patch(
        f"/admin/directions/{sport['id']}",
        json={"is_active": False},
        headers=admin,
    )
    assert r.status_code == 409


def test_direction_rename(client):
    admin = login(client, "admin1")
    d = client.get("/directions", headers=admin).json()[0]
    r = client.patch(
        f"/admin/directions/{d['id']}", json={"name": "Yangi nom"},
        headers=admin,
    )
    assert r.status_code == 200 and r.json()["name"] == "Yangi nom"


def test_migration_adds_column_without_losing_data():
    """Eski sxemadagi (direction ustunsiz) bazani simulyatsiya qiladi."""
    from app.directions import ensure_schema

    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(80),"
            " full_name VARCHAR(200), password_hash VARCHAR(500),"
            " role VARCHAR(40), school_id INTEGER, is_active BOOLEAN,"
            " created_at DATETIME)"
        ))
        conn.execute(text(
            "INSERT INTO users (id, username, full_name, password_hash,"
            " role, is_active) VALUES (1, 'eski', 'Eski User', 'h',"
            " 'school_coordinator', 1)"
        ))
    actions = ensure_schema(engine)
    assert actions
    assert ensure_schema(engine) == []          # ikkinchi marta hech narsa qilmaydi
    with engine.connect() as conn:
        row = conn.execute(text("SELECT username, direction FROM users")).one()
    assert row[0] == "eski" and row[1] is None  # ma'lumot saqlandi
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE users"))
