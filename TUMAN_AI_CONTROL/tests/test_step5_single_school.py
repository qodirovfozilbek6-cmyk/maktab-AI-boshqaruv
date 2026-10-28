"""Maktab ID endi foydalanuvchidan so'ralmaydi: tizim bitta (standart) maktabni
avtomatik biriktiradi. Bazadagi school_id ustuni saqlanadi.

SQLite ishlatadi, Neon'ga tegmaydi.
Ishga tushirish:  py -3.11 -m pytest tests/test_step5_single_school.py -v
"""

from tests.test_step2_scoping import PASSWORD, world  # noqa: F401  (fixture)


def _create_user(world, **overrides):
    payload = {
        "username": "maktabsiz1",
        "full_name": "Maktabsiz Sinov",
        "password": PASSWORD,
        "role": "coordinator",
        "direction": "culture",
    }
    payload.update(overrides)
    return world["client"].post(
        "/admin/users", json=payload, headers=world["H"]["admin1"]
    )


def test_coordinator_without_school_id_gets_default_school(world):
    r = _create_user(world)
    assert r.status_code == 201, r.text
    assert r.json()["school_id"] == 1           # birinchi faol maktab


def test_advisor_without_school_id_gets_default_school(world):
    r = _create_user(world, username="maktabsiz2", role="school_advisor", direction=None)
    assert r.status_code == 201, r.text
    assert r.json()["school_id"] == 1


def test_coordinator_still_needs_direction(world):
    r = _create_user(world, username="maktabsiz3", direction=None)
    assert r.status_code == 422


def test_manager_task_without_school_id_uses_default_school(world):
    r = world["client"].post(
        "/tasks",
        json={"title": "Maktabsiz topshiriq"},
        headers=world["H"]["lider1"],
    )
    assert r.status_code == 201, r.text
    assert r.json()["school_id"] == 1


def test_explicit_school_id_is_still_accepted_for_compatibility(world):
    r = _create_user(world, username="maktabsiz4", school_id=1, direction="ecology")
    assert r.status_code == 201, r.text
    assert r.json()["school_id"] == 1
