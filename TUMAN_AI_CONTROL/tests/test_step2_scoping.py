"""2-bosqich testlari: yo'nalish va maktab bo'yicha ma'lumot cheklovlari.

SQLite ishlatadi, Neon'ga tegmaydi. Foydalanuvchilar bazaga to'g'ridan-to'g'ri
qo'shiladi (parol xeshi bir marta hisoblanadi), shuning uchun testlar tez.

Ishga tushirish:  py -3.11 -m pytest tests/test_step2_scoping.py -v

Eslatma: tartib muhim. Ma'lumot yaratadigan testlar eng oxirida turadi.
"""

import os

# config.py import qilinishidan OLDIN sozlanishi shart.
os.environ["DATABASE_URL"] = "sqlite:///./test_maktab.db"
os.environ["JWT_SECRET_KEY"] = "t" * 64
os.environ["TELEGRAM_BOT_TOKEN"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import School, User
from app.security import hash_password

PASSWORD = "Sinov-parol-12345"

USERS = [
    # (username, role, school_id, direction)
    ("admin1", "admin", None, None),
    ("lider1", "kelajak_leader", None, None),
    ("c_sport", "coordinator", 1, "sport"),
    ("c_media", "coordinator", 1, "media"),
    ("adv1", "school_advisor", 1, None),
    ("adv2", "school_advisor", 1, None),
    ("c_other", "coordinator", 2, "sport"),  # boshqa maktab
]


def _login(client, username):
    r = client.post(
        "/auth/login", data={"username": username, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def world():
    Base.metadata.drop_all(bind=engine)

    with TestClient(app) as client:  # lifespan: jadvallar + 7 yo'nalish
        db = SessionLocal()
        db.add_all([School(name="Sinov maktabi"), School(name="Boshqa maktab")])
        db.flush()

        pw_hash = hash_password(PASSWORD)
        for username, role, school_id, direction in USERS:
            db.add(
                User(
                    username=username,
                    full_name=f"Sinov {username}",
                    password_hash=pw_hash,
                    role=role,
                    school_id=school_id,
                    direction=direction,
                )
            )
        db.commit()
        db.close()

        H = {username: _login(client, username) for username, *_ in USERS}

        def post(path, who, **payload):
            r = client.post(path, json=payload, headers=H[who])
            assert r.status_code == 201, r.text
            return r.json()["id"]

        text_ = "Bu sinov uchun yozilgan hisobot matni."
        ids = {
            "r_sport": post("/reports", "c_sport", title="Sport hisoboti",
                            period="Oktyabr", summary=text_),
            "r_media": post("/reports", "c_media", title="Media hisoboti",
                            period="Oktyabr", summary=text_),
            "r_adv1": post("/reports", "adv1", title="Maslahatchi hisoboti",
                           period="Oktyabr", summary=text_),
            "r_other": post("/reports", "c_other", title="Boshqa maktab",
                            period="Oktyabr", summary=text_),
            "p_sport": post("/projects", "c_sport", title="Sport loyihasi"),
            "p_media": post("/projects", "c_media", title="Media loyihasi"),
            "t_sport": post("/tasks", "c_sport", title="Sport topshirig'i"),
            "t_media": post("/tasks", "c_media", title="Media topshirig'i"),
            "t_adv": post("/tasks", "adv1", title="Maslahatchi topshirig'i"),
            "t_all": post("/tasks", "lider1", title="Umumiy topshiriq",
                          school_id=1),
            "t_media_lead": post("/tasks", "lider1", title="Media uchun",
                                 school_id=1, direction="media"),
        }

        yield {"client": client, "H": H, "ids": ids}

    Base.metadata.drop_all(bind=engine)


def _ids(world, path, who, **params):
    r = world["client"].get(path, headers=world["H"][who], params=params)
    assert r.status_code == 200, r.text
    return {item["id"] for item in r.json()}


def _pick(world, *names):
    return {world["ids"][n] for n in names}


# ------------------------------------------------------------ hisobotlar

def test_report_direction_is_set_automatically(world):
    r = world["client"].get("/reports", headers=world["H"]["admin1"])
    by_id = {x["id"]: x for x in r.json()}
    assert by_id[world["ids"]["r_sport"]]["direction"] == "sport"
    assert by_id[world["ids"]["r_media"]]["direction"] == "media"
    assert by_id[world["ids"]["r_adv1"]]["direction"] is None


def test_coordinator_sees_only_own_direction_reports(world):
    assert _ids(world, "/reports", "c_sport") == _pick(world, "r_sport")
    assert _ids(world, "/reports", "c_media") == _pick(world, "r_media")


def test_leader_and_admin_see_all_reports(world):
    everything = _pick(world, "r_sport", "r_media", "r_adv1", "r_other")
    assert _ids(world, "/reports", "lider1") == everything
    assert _ids(world, "/reports", "admin1") == everything


def test_advisor_sees_only_own_reports(world):
    assert _ids(world, "/reports", "adv1") == _pick(world, "r_adv1")
    assert _ids(world, "/reports", "adv2") == set()


def test_other_school_is_isolated(world):
    assert _ids(world, "/reports", "c_other") == _pick(world, "r_other")
    assert _ids(world, "/reports", "lider1", school_id=2) == _pick(
        world, "r_other"
    )


def test_coordinator_cannot_review_reports(world):
    rid = world["ids"]["r_sport"]
    r = world["client"].patch(
        f"/reports/{rid}/review",
        json={"status": "reviewed", "review_note": "ok"},
        headers=world["H"]["c_sport"],
    )
    assert r.status_code == 403


# --------------------------------------------------------------- loyihalar

def test_projects_are_scoped_like_reports(world):
    assert _ids(world, "/projects", "c_sport") == _pick(world, "p_sport")
    assert _ids(world, "/projects", "c_media") == _pick(world, "p_media")
    assert _ids(world, "/projects", "adv1") == set()
    assert _ids(world, "/projects", "c_other") == set()
    assert _ids(world, "/projects", "lider1") == _pick(
        world, "p_sport", "p_media"
    )


# ------------------------------------------------------------ topshiriqlar

def test_task_visibility_per_role(world):
    assert _ids(world, "/tasks", "c_sport") == _pick(
        world, "t_sport", "t_all"
    )
    assert _ids(world, "/tasks", "c_media") == _pick(
        world, "t_media", "t_all", "t_media_lead"
    )
    assert _ids(world, "/tasks", "adv1") == _pick(world, "t_adv")
    assert _ids(world, "/tasks", "adv2") == set()
    assert _ids(world, "/tasks", "c_other") == set()
    assert _ids(world, "/tasks", "lider1") == _pick(
        world, "t_sport", "t_media", "t_adv", "t_all", "t_media_lead"
    )


def test_cannot_touch_other_direction_task(world):
    tid = world["ids"]["t_media"]
    r = world["client"].patch(
        f"/tasks/{tid}", json={"status": "completed"},
        headers=world["H"]["c_sport"],
    )
    assert r.status_code == 404


def test_coordinator_can_update_own_task_status(world):
    tid = world["ids"]["t_sport"]
    r = world["client"].patch(
        f"/tasks/{tid}", json={"status": "in_progress"},
        headers=world["H"]["c_sport"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"


def test_coordinator_cannot_edit_other_task_fields(world):
    tid = world["ids"]["t_sport"]
    r = world["client"].patch(
        f"/tasks/{tid}", json={"title": "Boshqa nom"},
        headers=world["H"]["c_sport"],
    )
    assert r.status_code == 403


def test_umbrella_task_status_is_managers_only(world):
    tid = world["ids"]["t_all"]
    r = world["client"].patch(
        f"/tasks/{tid}", json={"status": "completed"},
        headers=world["H"]["c_sport"],
    )
    assert r.status_code == 403
    r = world["client"].patch(
        f"/tasks/{tid}", json={"status": "in_progress"},
        headers=world["H"]["lider1"],
    )
    assert r.status_code == 200


def test_dashboard_counts_match_visible_data(world):
    for username, *_ in USERS:
        r = world["client"].get(
            "/dashboard/summary", headers=world["H"][username]
        )
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["reports_count"] == len(_ids(world, "/reports", username))
        assert s["projects_count"] == len(_ids(world, "/projects", username))
        assert (
            s["tasks_pending_count"] + s["tasks_completed_count"]
            == len(_ids(world, "/tasks", username))
        ), username


# ------------------------------------------- ma'lumot yaratadigan testlar
# (ular ro'yxatlar tarkibini o'zgartiradi, shuning uchun eng oxirida)

def test_coordinator_cannot_create_task_for_other_direction(world):
    c = world["client"]
    r = c.post(
        "/tasks", json={"title": "Begona topshiriq", "direction": "media"},
        headers=world["H"]["c_sport"],
    )
    assert r.status_code == 403

    r = c.post(
        "/tasks", json={"title": "O'z topshirig'im"},
        headers=world["H"]["c_sport"],
    )
    assert r.status_code == 201
    assert r.json()["direction"] == "sport"


def test_manager_task_direction_is_validated(world):
    c = world["client"]
    lead = world["H"]["lider1"]

    r = c.post(
        "/tasks",
        json={"title": "Xato yo'nalish", "school_id": 1, "direction": "yoq"},
        headers=lead,
    )
    assert r.status_code == 422

    r = c.post(
        "/tasks",
        json={"title": "Ekologiya", "school_id": 1, "direction": "ecology"},
        headers=lead,
    )
    assert r.status_code == 201
    assert r.json()["direction"] == "ecology"


# --------------------------------------------------------------- migratsiya

def test_migration_adds_direction_to_all_tables_without_data_loss():
    """Eski sxemadagi bazani alohida xotira bazasida simulyatsiya qiladi."""
    from app.directions import ensure_schema

    mem = create_engine("sqlite://")
    with mem.begin() as conn:
        for table in ("users", "reports", "projects", "tasks"):
            conn.execute(text(
                f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, title VARCHAR(50))"
            ))
            conn.execute(text(
                f"INSERT INTO {table} (id, title) VALUES (1, 'eski yozuv')"
            ))

    actions = ensure_schema(mem)
    assert len(actions) == 4

    insp = inspect(mem)
    for table in ("users", "reports", "projects", "tasks"):
        cols = {c["name"] for c in insp.get_columns(table)}
        assert "direction" in cols, table
        with mem.connect() as conn:
            row = conn.execute(
                text(f"SELECT title, direction FROM {table}")
            ).one()
        assert row[0] == "eski yozuv" and row[1] is None

    assert ensure_schema(mem) == []  # ikkinchi marta hech narsa qilmaydi
