
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Project, Report, School, Task, User


# ============================================================
# UMUMIY YORDAMCHI FUNKSIYALAR
# ============================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _get_or_404(model: type, db: Session, object_id: int):
    obj = db.get(model, object_id)

    if obj is None:
        raise ValueError(
            f"{model.__name__} ID={object_id} topilmadi."
        )

    return obj


def _serialize(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}

    data: dict[str, Any] = {}

    for column in obj.__table__.columns:
        value = getattr(obj, column.name, None)

        if isinstance(value, datetime):
            value = value.isoformat()

        data[column.name] = value

    return data


def _allowed_payload(
    model: type,
    payload: dict[str, Any],
) -> dict[str, Any]:
    allowed = {
        column.name
        for column in model.__table__.columns
    }

    return {
        key: value
        for key, value in payload.items()
        if key in allowed and key != "id"
    }


# ============================================================
# MAKTABLAR
# ============================================================

def get_school(db: Session, school_id: int) -> School:
    return _get_or_404(School, db, school_id)


def list_schools(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
) -> list[School]:
    statement = select(School)

    if active_only:
        statement = statement.where(
            School.is_active.is_(True)
        )

    statement = (
        statement
        .order_by(School.id.asc())
        .offset(max(0, skip))
        .limit(max(1, min(limit, 500)))
    )

    return list(db.scalars(statement).all())


def count_schools(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(School)) or 0
    )


def create_school(
    db: Session,
    *,
    name: str,
    district: str = "",
    address: str = "",
) -> School:
    name = name.strip()

    if not name:
        raise ValueError("Maktab nomi kiritilishi shart.")

    school = School(
        name=name,
        district=district.strip(),
        address=address.strip(),
    )

    db.add(school)
    _commit(db)
    db.refresh(school)

    return school


def update_school(
    db: Session,
    school_id: int,
    **changes: Any,
) -> School:
    school = get_school(db, school_id)

    for key, value in _allowed_payload(
        School, changes
    ).items():
        if key == "name":
            value = str(value).strip()

            if not value:
                raise ValueError(
                    "Maktab nomi bo‘sh bo‘lishi mumkin emas."
                )

        setattr(school, key, value)

    _commit(db)
    db.refresh(school)

    return school


# ============================================================
# FOYDALANUVCHILAR
# ============================================================

def get_user(db: Session, user_id: int) -> User:
    return _get_or_404(User, db, user_id)


def get_user_by_username(
    db: Session,
    username: str,
) -> User | None:
    statement = select(User).where(
        func.lower(User.username) == username.strip().lower()
    )

    return db.scalar(statement)


def list_users(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    school_id: int | None = None,
    role: str | None = None,
    active_only: bool = False,
) -> list[User]:
    statement = select(User)

    if school_id is not None:
        statement = statement.where(
            User.school_id == school_id
        )

    if role:
        statement = statement.where(User.role == role)

    if active_only:
        statement = statement.where(
            User.is_active.is_(True)
        )

    statement = (
        statement
        .order_by(User.id.asc())
        .offset(max(0, skip))
        .limit(max(1, min(limit, 500)))
    )

    return list(db.scalars(statement).all())


def count_users(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(User)) or 0
    )


def count_active_users(db: Session) -> int:
    statement = (
        select(func.count())
        .select_from(User)
        .where(User.is_active.is_(True))
    )

    return int(db.scalar(statement) or 0)


def set_user_active(
    db: Session,
    user_id: int,
    is_active: bool,
) -> User:
    user = get_user(db, user_id)
    user.is_active = bool(is_active)

    _commit(db)
    db.refresh(user)

    return user


# ============================================================
# HISOBOTLAR
# ============================================================

def get_report(db: Session, report_id: int) -> Report:
    return _get_or_404(Report, db, report_id)


def list_reports(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    school_id: int | None = None,
    status: str | None = None,
) -> list[Report]:
    statement = select(Report)

    if school_id is not None:
        statement = statement.where(
            Report.school_id == school_id
        )

    if status:
        statement = statement.where(
            Report.status == status
        )

    statement = (
        statement
        .order_by(Report.id.desc())
        .offset(max(0, skip))
        .limit(max(1, min(limit, 500)))
    )

    return list(db.scalars(statement).all())


def count_reports(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Report)) or 0
    )


def create_report(
    db: Session,
    *,
    title: str,
    school_id: int,
    created_by: int,
    period: str,
    summary: str = "",
    status: str = "submitted",
    evidence_url: str = "",
) -> Report:
    title = title.strip()
    period = period.strip()

    if not title:
        raise ValueError("Hisobot sarlavhasi kiritilishi shart.")

    if not period:
        raise ValueError("Hisobot davri kiritilishi shart.")

    _get_or_404(db=db, model=School, object_id=school_id)
    _get_or_404(db=db, model=User, object_id=created_by)

    report = Report(
        title=title,
        school_id=school_id,
        created_by=created_by,
        period=period,
        summary=summary.strip(),
        status=status,
        evidence_url=evidence_url.strip(),
    )

    db.add(report)
    _commit(db)
    db.refresh(report)

    return report


# ============================================================
# LOYIHALAR
# ============================================================

def get_project(db: Session, project_id: int) -> Project:
    return _get_or_404(db=db, model=Project, object_id=project_id)


def list_projects(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    school_id: int | None = None,
    status: str | None = None,
) -> list[Project]:
    statement = select(Project)

    if school_id is not None:
        statement = statement.where(
            Project.school_id == school_id
        )

    if status:
        statement = statement.where(
            Project.status == status
        )

    statement = (
        statement
        .order_by(Project.id.desc())
        .offset(max(0, skip))
        .limit(max(1, min(limit, 500)))
    )

    return list(db.scalars(statement).all())


def count_projects(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Project)) or 0
    )


def create_project(
    db: Session,
    *,
    title: str,
    school_id: int,
    created_by: int,
    description: str = "",
    category: str = "AI",
    status: str = "planned",
    evidence_url: str = "",
) -> Project:
    title = title.strip()

    if not title:
        raise ValueError("Loyiha nomi kiritilishi shart.")

    _get_or_404(db=db, model=School, object_id=school_id)
    _get_or_404(db=db, model=User, object_id=created_by)

    project = Project(
        title=title,
        school_id=school_id,
        created_by=created_by,
        description=description.strip(),
        category=category.strip() or "AI",
        status=status,
        evidence_url=evidence_url.strip(),
    )

    db.add(project)
    _commit(db)
    db.refresh(project)

    return project


# ============================================================
# VAZIFALAR
# ============================================================

def get_task(db: Session, task_id: int) -> Task:
    return _get_or_404(db=db, model=Task, object_id=task_id)


def list_tasks(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    school_id: int | None = None,
    status: str | None = None,
) -> list[Task]:
    statement = select(Task)

    if school_id is not None:
        statement = statement.where(
            Task.school_id == school_id
        )

    if status:
        statement = statement.where(
            Task.status == status
        )

    statement = (
        statement
        .order_by(Task.id.desc())
        .offset(max(0, skip))
        .limit(max(1, min(limit, 500)))
    )

    return list(db.scalars(statement).all())


def count_tasks(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Task)) or 0
    )


def create_task(
    db: Session,
    *,
    title: str,
    school_id: int,
    created_by: int,
    description: str = "",
    deadline: datetime | None = None,
    status: str = "pending",
) -> Task:
    title = title.strip()

    if not title:
        raise ValueError("Vazifa nomi kiritilishi shart.")

    _get_or_404(db=db, model=School, object_id=school_id)
    _get_or_404(db=db, model=User, object_id=created_by)

    task = Task(
        title=title,
        school_id=school_id,
        created_by=created_by,
        description=description.strip(),
        deadline=deadline,
        status=status,
    )

    db.add(task)
    _commit(db)
    db.refresh(task)

    return task


def update_task(
    db: Session,
    task_id: int,
    **changes: Any,
) -> Task:
    task = get_task(db, task_id)

    for key, value in _allowed_payload(Task, changes).items():
        setattr(task, key, value)

    _commit(db)
    db.refresh(task)

    return task


# ============================================================
# AUDIT LOG
# ============================================================

def create_audit_log(
    db: Session,
    *,
    action: str,
    entity_type: str,
    user_id: int | None = None,
    entity_id: int | None = None,
    details: str = "",
) -> AuditLog:
    if not action.strip():
        raise ValueError("Audit action kiritilishi shart.")

    if not entity_type.strip():
        raise ValueError("Audit entity_type kiritilishi shart.")

    log = AuditLog(
        user_id=user_id,
        action=action.strip(),
        entity_type=entity_type.strip(),
        entity_id=entity_id,
        details=details,
    )

    db.add(log)
    _commit(db)
    db.refresh(log)

    return log


def list_audit_logs(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    user_id: int | None = None,
) -> list[AuditLog]:
    statement = select(AuditLog)

    if user_id is not None:
        statement = statement.where(
            AuditLog.user_id == user_id
        )

    statement = (
        statement
        .order_by(AuditLog.id.desc())
        .offset(max(0, skip))
        .limit(max(1, min(limit, 500)))
    )

    return list(db.scalars(statement).all())


# ============================================================
# DASHBOARD
# ============================================================

def get_dashboard_stats(db: Session) -> dict[str, int]:
    return {
        "schools": count_schools(db),
        "users": count_users(db),
        "active_users": count_active_users(db),
        "reports": count_reports(db),
        "projects": count_projects(db),
        "tasks": count_tasks(db),
    }


# ============================================================
# SERIALIZATSIYA
# ============================================================

def _serialize_model(obj: Any) -> dict[str, Any]:
    data = _serialize(obj)

    if isinstance(obj, User):
        data.pop("password_hash", None)

    return data


def school_to_dict(school: School) -> dict[str, Any]:
    return _serialize_model(school)


def user_to_dict(user: User) -> dict[str, Any]:
    return _serialize_model(user)


def report_to_dict(report: Report) -> dict[str, Any]:
    return _serialize_model(report)


def project_to_dict(project: Project) -> dict[str, Any]:
    return _serialize_model(project)


def task_to_dict(task: Task) -> dict[str, Any]:
    return _serialize_model(task)


def audit_log_to_dict(log: AuditLog) -> dict[str, Any]:
    return _serialize_model(log)
