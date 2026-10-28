
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import APP_NAME, JWT_EXPIRE_MINUTES
from app.database import Base, engine, get_db
from app import models
from app.models import (
    AuditLog,
    Project,
    Report,
    School,
    Task,
    User,
)
from app.schemas import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    DashboardSummary,
    LoginRequest,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    ReportCreate,
    ReportOut,
    ReportReview,
    SchoolCreate,
    SchoolOut,
    SchoolUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    TokenResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.permissions import get_current_user
from app.ai_analysis import analyze_report
from fastapi.responses import FileResponse


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"

ADMIN = "admin"
DISTRICT = "district_coordinator"
SCHOOL_COORDINATOR = "school_coordinator"

VALID_ROLES = {ADMIN, DISTRICT, SCHOOL_COORDINATOR}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Prototipni dastlabki ishga tushirish uchun jadvallar yaratiladi.
    # Ishlab chiqarish muhitida migratsiyalar bilan almashtirish kerak.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=APP_NAME,
    version="1.0.0",
    description=(
        "Tuman maktablarida IT va sun'iy intellekt faoliyatini "
        "boshqarish platformasi."
    ),
    lifespan=lifespan,
)

if STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )


def role_guard(*allowed_roles):
    def dependency(user=Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu amal uchun ruxsatingiz yo'q.",
            )
        return user

    return dependency


def commit_or_rollback(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Ma'lumotlar to'qnashuvi. Nom yoki username "
                "takrorlanmaganini tekshiring."
            ),
        )


def school_access(db: Session, user: User, school_id: int) -> School:
    school = db.get(School, school_id)

    if not school or not school.is_active:
        raise HTTPException(status_code=404, detail="Maktab topilmadi.")

    if (
        user.role == SCHOOL_COORDINATOR
        and user.school_id != school_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Siz faqat o'z maktabingiz ma'lumotlarini ko'ra olasiz.",
        )

    return school


def ensure_record_school_access(user: User, school_id: int):
    if (
        user.role == SCHOOL_COORDINATOR
        and user.school_id != school_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Boshqa maktab ma'lumotlariga ruxsat yo'q.",
        )


def audit(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: str = "",
):
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details[:2000],
        )
    )


def visible_school_ids(db: Session, user: User) -> list[int]:
    if user.role in {ADMIN, DISTRICT}:
        return list(
            db.scalars(select(School.id)).all()
        )

    if user.school_id is None:
        return []

    return [user.school_id]


@app.get("/", include_in_schema=False)
def home():
    index_file = STATIC_DIR / "index.html"

    if index_file.is_file():
        return FileResponse(index_file)

    return {
        "app": APP_NAME,
        "status": "backend_ready",
        "message": "Frontend index.html fayli hali tayyor emas.",
        "docs": "/docs",
    }
@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(STATIC_DIR / "login.html")
@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")

    return FileResponse(index_file)


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}


# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------


@app.post("/auth/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    username = form.username.strip().lower()

    user = db.scalar(
        select(User).where(User.username == username)
    )

    if (
        not user
        or not user.is_active
        or not verify_password(form.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username yoki parol noto'g'ri.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id, user.role)

    audit(
        db,
        user,
        "login",
        "user",
        user.id,
        "Muvaffaqiyatli tizimga kirish",
    )
    db.commit()

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=JWT_EXPIRE_MINUTES,
    )


@app.get("/auth/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user


# ---------------------------------------------------------
# SCHOOLS
# ---------------------------------------------------------

@app.get("/schools", response_model=list[SchoolOut])
def list_schools(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(School).order_by(School.name)

    if user.role == SCHOOL_COORDINATOR:
        if user.school_id is None:
            return []
        query = query.where(School.id == user.school_id)

    return list(db.scalars(query).all())


@app.post(
    "/admin/schools",
    response_model=SchoolOut,
    status_code=status.HTTP_201_CREATED,
)
def create_school(
    payload: SchoolCreate,
    db: Session = Depends(get_db),
    user=Depends(role_guard(ADMIN)),
):
    school = School(**payload.model_dump())
    db.add(school)
    db.flush()

    audit(db, user, "create", "school", school.id, school.name)
    commit_or_rollback(db)
    db.refresh(school)

    return school


@app.patch("/admin/schools/{school_id}", response_model=SchoolOut)
def update_school(
    school_id: int,
    payload: SchoolUpdate,
    db: Session = Depends(get_db),
    user=Depends(role_guard(ADMIN)),
):
    school = db.get(School, school_id)

    if not school:
        raise HTTPException(status_code=404, detail="Maktab topilmadi.")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(school, key, value)

    audit(db, user, "update", "school", school.id, school.name)
    commit_or_rollback(db)
    db.refresh(school)

    return school


# ---------------------------------------------------------
# USERS
# ---------------------------------------------------------

@app.get("/users", response_model=list[UserOut])
def list_users(
    school_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(User).order_by(User.id)

    if user.role == SCHOOL_COORDINATOR:
        if user.school_id is None:
            return []
        query = query.where(User.school_id == user.school_id)

    elif user.role == DISTRICT:
        query = query.where(User.role != ADMIN)

        if school_id is not None:
            query = query.where(User.school_id == school_id)

    elif school_id is not None:
        query = query.where(User.school_id == school_id)

    return list(db.scalars(query).all())


@app.post(
    "/admin/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    user=Depends(role_guard(ADMIN)),
):
    data = payload.model_dump()

    if data["role"] not in VALID_ROLES:
        raise HTTPException(status_code=422, detail="Rol noto'g'ri.")

    # Yangi admin hisobini ushbu endpoint orqali yaratishga ruxsat yo'q.
    if data["role"] == ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Yangi admin yaratish bu endpointda taqiqlangan.",
        )

    school_id = data.get("school_id")

    if data["role"] == SCHOOL_COORDINATOR:
        if not school_id:
            raise HTTPException(
                status_code=422,
                detail="Maktab koordinatori uchun school_id kerak.",
            )
        school_access(db, user, school_id)
    else:
        data["school_id"] = None

    raw_password = data.pop("password")
    new_user = User(
        **data,
        password_hash=hash_password(raw_password),
    )

    db.add(new_user)
    db.flush()

    audit(db, user, "create", "user", new_user.id, new_user.username)
    commit_or_rollback(db)
    db.refresh(new_user)

    return new_user


@app.patch("/admin/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user=Depends(role_guard(ADMIN)),
):
    target = db.get(User, user_id)

    if not target:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi.")

    changes = payload.model_dump(exclude_unset=True)

    if changes.get("role") == ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Bu endpoint orqali admin roli berilmaydi.",
        )

    if target.id == user.id and changes.get("is_active") is False:
        raise HTTPException(
            status_code=400,
            detail="O'z hisobingizni o'chira olmaysiz.",
        )

    new_role = changes.get("role", target.role)
    new_school_id = changes.get("school_id", target.school_id)

    if new_role == SCHOOL_COORDINATOR:
        if not new_school_id:
            raise HTTPException(
                status_code=422,
                detail="Maktab koordinatori uchun school_id kerak.",
            )
        school_access(db, user, new_school_id)
    else:
        changes["school_id"] = None

    for key, value in changes.items():
        setattr(target, key, value)

    audit(db, user, "update", "user", target.id, target.username)
    commit_or_rollback(db)
    db.refresh(target)

    return target


# ---------------------------------------------------------
# REPORTS
# ---------------------------------------------------------

@app.post(
    "/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    user=Depends(role_guard(SCHOOL_COORDINATOR)),
):
    if not user.school_id:
        raise HTTPException(
            status_code=400,
            detail="Hisobot uchun hisobingizga maktab biriktirilmagan.",
        )

    report = Report(
        **payload.model_dump(),
        school_id=user.school_id,
        created_by=user.id,
        status="submitted",
    )

    db.add(report)
    db.flush()

    audit(db, user, "create", "report", report.id, report.title)
    commit_or_rollback(db)
    db.refresh(report)

    return report


@app.get("/reports", response_model=list[ReportOut])
def list_reports(
    school_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(Report).order_by(Report.created_at.desc())

    if user.role == SCHOOL_COORDINATOR:
        if not user.school_id:
            return []
        query = query.where(Report.school_id == user.school_id)
    elif school_id is not None:
        query = query.where(Report.school_id == school_id)

    return list(db.scalars(query).all())


@app.patch("/reports/{report_id}/review", response_model=ReportOut)
def review_report(
    report_id: int,
    payload: ReportReview,
    db: Session = Depends(get_db),
    user=Depends(role_guard(ADMIN, DISTRICT)),
):
    report = db.get(Report, report_id)

    if not report:
        raise HTTPException(status_code=404, detail="Hisobot topilmadi.")

    report.status = payload.status
    review_note = payload.review_note.strip()
    audit(
        db,
        user,
        "review",
        "report",
        report.id,
                f"Yangi holat: {payload.status}; "
                f"Izoh: {review_note}",
    )

    commit_or_rollback(db)
    db.refresh(report)

    return report


# ---------------------------------------------------------
# PROJECTS
# ---------------------------------------------------------

@app.post(
    "/projects",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(role_guard(SCHOOL_COORDINATOR)),
):
    if not user.school_id:
        raise HTTPException(
            status_code=400,
            detail="Loyiha uchun hisobingizga maktab biriktirilmagan.",
        )

    project = Project(
        **payload.model_dump(),
        school_id=user.school_id,
        created_by=user.id,
    )

    db.add(project)
    db.flush()

    audit(db, user, "create", "project", project.id, project.title)
    commit_or_rollback(db)
    db.refresh(project)

    return project


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(
    school_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(Project).order_by(Project.created_at.desc())

    if user.role == SCHOOL_COORDINATOR:
        if not user.school_id:
            return []
        query = query.where(Project.school_id == user.school_id)
    elif school_id is not None:
        query = query.where(Project.school_id == school_id)

    return list(db.scalars(query).all())


# ---------------------------------------------------------
# TASKS
# ---------------------------------------------------------

@app.post(
    "/tasks",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    user=Depends(role_guard(ADMIN, DISTRICT, SCHOOL_COORDINATOR)),
):
    data = payload.model_dump()
    school_id = data.get("school_id")

    if user.role == SCHOOL_COORDINATOR:
        if not user.school_id:
            raise HTTPException(
                status_code=400,
                detail="Hisobingizga maktab biriktirilmagan.",
            )
        school_id = user.school_id
    elif school_id is None:
        raise HTTPException(
            status_code=422,
            detail="Topshiriq uchun school_id ko'rsatilishi kerak.",
        )

    school_access(db, user, school_id)

    data["school_id"] = school_id
    task = Task(**data, created_by=user.id)

    db.add(task)
    db.flush()

    audit(db, user, "create", "task", task.id, task.title)
    commit_or_rollback(db)
    db.refresh(task)

    return task


@app.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    school_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(Task).order_by(Task.created_at.desc())

    if user.role == SCHOOL_COORDINATOR:
        if not user.school_id:
            return []
        query = query.where(Task.school_id == user.school_id)
    elif school_id is not None:
        query = query.where(Task.school_id == school_id)

    return list(db.scalars(query).all())


@app.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    task = db.get(Task, task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi.")

    ensure_record_school_access(user, task.school_id)

    changes = payload.model_dump(exclude_unset=True)

    if user.role == SCHOOL_COORDINATOR:
        # Maktab koordinatori topshiriqning faqat holatini o'zgartiradi.
        if set(changes.keys()) - {"status"}:
            raise HTTPException(
                status_code=403,
                detail="Siz faqat topshiriq holatini o'zgartira olasiz.",
            )
    elif user.role not in {ADMIN, DISTRICT}:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q.")

    if "school_id" in changes:
        school_access(db, user, changes["school_id"])

    for key, value in changes.items():
        setattr(task, key, value)

    audit(db, user, "update", "task", task.id, task.title)
    commit_or_rollback(db)
    db.refresh(task)

    return task


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    school_ids = visible_school_ids(db, user)

    school_query = select(func.count(School.id))
    active_school_query = select(func.count(School.id))

    if user.role == SCHOOL_COORDINATOR:
        school_query = school_query.where(School.id.in_(school_ids))
        active_school_query = active_school_query.where(
            School.id.in_(school_ids),
            School.is_active.is_(True),
        )

    schools_count = db.scalar(school_query) or 0
    active_schools_count = db.scalar(active_school_query) or 0

    user_query = select(func.count(User.id))
    report_query = select(func.count(Report.id))
    project_query = select(func.count(Project.id))
    pending_query = select(func.count(Task.id)).where(
        Task.status != "completed"
    )
    completed_query = select(func.count(Task.id)).where(
        Task.status == "completed"
    )

    if user.role == SCHOOL_COORDINATOR:
        school_id = user.school_id
        user_query = user_query.where(User.school_id == school_id)
        report_query = report_query.where(Report.school_id == school_id)
        project_query = project_query.where(Project.school_id == school_id)
        pending_query = pending_query.where(Task.school_id == school_id)
        completed_query = completed_query.where(Task.school_id == school_id)

    return DashboardSummary(
        schools_count=schools_count,
        active_schools_count=active_schools_count,
        users_count=db.scalar(user_query) or 0,
        reports_count=db.scalar(report_query) or 0,
        projects_count=db.scalar(project_query) or 0,
        tasks_pending_count=db.scalar(pending_query) or 0,
        tasks_completed_count=db.scalar(completed_query) or 0,
    )


# ---------------------------------------------------------
# AUDIT LOGS
# ---------------------------------------------------------

@app.get("/admin/audit-logs")
def get_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(role_guard(ADMIN)),
):
    logs = db.scalars(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": log.created_at,
        }
        for log in logs
    ]


# ---------------------------------------------------------
# AI ANALYSIS
# ---------------------------------------------------------

@app.post("/ai/analyze", response_model=AIAnalysisResponse)
def ai_analyze(
    payload: AIAnalysisRequest,
    user=Depends(get_current_user),
):
    # Hozircha lokal, qoidaga asoslangan tahlil.
    # Tashqi AI API kaliti ulanmaguncha internetga ma'lumot yuborilmaydi.
    return analyze_report(
        text=payload.text,
        context=payload.context,
    )
