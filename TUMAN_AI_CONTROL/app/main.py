import asyncio
from contextlib import asynccontextmanager, suppress

from app.telegram_link import TelegramLink, create_link_code
from app.telegram_bot import start_telegram_bot
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import APP_NAME, JWT_EXPIRE_MINUTES
from app.database import Base, engine, get_db
from app import models
from app.models import (
    AuditLog,
    Direction,
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
    DirectionOut,
    DirectionUpdate,
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
from app.permissions import (
    ADMIN,
    ASSIGNABLE_ROLES,
    COORDINATOR,
    DISTRICT_COORDINATOR as DISTRICT,
    KELAJAK_LEADER,
    MANAGER_ROLES,
    SCHOOL_ADVISOR,
    SCHOOL_BOUND_ROLES,
    VALID_ROLES,
    get_current_user,
)
from app.directions import ensure_schema, seed_directions
from app.database import SessionLocal
from app.ai_analysis import analyze_report
from app.ai_center import build_overview, build_period_report
from app.ratelimit import LoginLimiter
from fastapi.responses import FileResponse


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"




@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    # Faqat qo'shuvchi, xavfsiz yangilash: users.direction ustuni va
    # yo'nalishlar. Mavjud ma'lumotlarga tegilmaydi.
    ensure_schema(engine)
    seed_db = SessionLocal()
    try:
        seed_directions(seed_db)
    finally:
        seed_db.close()

    bot_task = asyncio.create_task(start_telegram_bot())

    try:
        yield
    finally:
        bot_task.cancel()

        with suppress(asyncio.CancelledError):
            await bot_task



app = FastAPI(
    title=APP_NAME,
    version="2.0.0-dev",
    description=(
        "Maktab Kelajak o'quvchilar kengashi faoliyatini "
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


# Login urinishlarini cheklash: 5 ta xato urinishdan keyin 5 daqiqa blok.
login_limiter = LoginLimiter(
    max_failures=5, window_seconds=300, lockout_seconds=300
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    return response


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
        user.role in SCHOOL_BOUND_ROLES
        and user.school_id != school_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Siz faqat o'z maktabingiz ma'lumotlarini ko'ra olasiz.",
        )

    return school


def ensure_record_school_access(user: User, school_id: int):
    if (
        user.role in SCHOOL_BOUND_ROLES
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
    if user.role in MANAGER_ROLES:
        return list(
            db.scalars(select(School.id)).all()
        )

    if user.school_id is None:
        return []

    return [user.school_id]


DEFAULT_SCHOOL_NAME = "Maktab"


def default_school_id(db: Session) -> int:
    """Tizim bitta maktab bilan ishlaydi: maktab ID foydalanuvchidan so'ralmaydi.

    Birinchi faol maktab ishlatiladi. Maktab yozuvi umuman bo'lmasa,
    bitta standart maktab yaratiladi (chaqiruvchi commit qiladi).
    """
    school = db.scalar(
        select(School)
        .where(School.is_active.is_(True))
        .order_by(School.id)
        .limit(1)
    )

    if school:
        return school.id

    school = db.scalar(
        select(School).where(School.name == DEFAULT_SCHOOL_NAME)
    )

    if not school:
        school = School(name=DEFAULT_SCHOOL_NAME)
        db.add(school)
        db.flush()

    return school.id


def resolve_assignment(
    db: Session,
    actor: User,
    role: str,
    school_id: int | None,
    direction: str | None,
    *,
    is_active: bool = True,
    exclude_user_id: int | None = None,
    current_direction: str | None = None,
) -> tuple[int | None, str | None]:
    """Rolga qarab school_id va direction qiymatlarini tekshiradi."""
    if role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail="Rol noto'g'ri.")

    # Maktabga bog'langan rollar uchun maktab majburiy.
    if role in SCHOOL_BOUND_ROLES:
        if school_id:
            school_access(db, actor, school_id)
        else:
            school_id = default_school_id(db)
    else:
        school_id = None

    # Yo'nalish faqat koordinator uchun.
    if role == COORDINATOR:
        direction = (direction or "").strip() or None

        if not direction:
            raise HTTPException(
                status_code=422,
                detail="Koordinator uchun yo'nalish (direction) kerak.",
            )

        found = db.scalar(
            select(Direction).where(Direction.code == direction)
        )

        if not found:
            raise HTTPException(
                status_code=422, detail="Bunday yo'nalish mavjud emas."
            )

        if not found.is_active and direction != current_direction:
            raise HTTPException(
                status_code=422, detail="Bu yo'nalish faol emas."
            )
    else:
        direction = None

    # Kelajak lideri bitta bo'ladi.
    if role == KELAJAK_LEADER and is_active:
        other = db.scalar(
            select(User.id).where(
                User.role == KELAJAK_LEADER,
                User.is_active.is_(True),
                User.id != (exclude_user_id or 0),
            )
        )

        if other is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Faol Kelajak lideri allaqachon mavjud. "
                    "Avval uni faolsizlantiring."
                ),
            )

    return school_id, direction


def scope_query(query, model, user: User):
    """Foydalanuvchi ko'ra oladigan yozuvlarga cheklaydi (Report, Project, Task).

    * Rahbariyat (admin, direktor, Kelajak lideri, eski tuman koordinatori):
      hammasini ko'radi.
    * Koordinator: o'z maktabi va O'Z YO'NALISHI. Topshiriqlarda qo'shimcha
      ravishda rahbariyat bergan umumiy (yo'nalishsiz) topshiriqlarni ham ko'radi.
    * Maslahatchi: faqat o'zi yaratganlarni.
    * Eski maktab koordinatori: butun maktab (avvalgidek).
    """
    if user.role in MANAGER_ROLES:
        return query

    if not user.school_id:
        return query.where(false())

    query = query.where(model.school_id == user.school_id)

    if user.role == COORDINATOR:
        if not user.direction:
            return query.where(false())

        if model is Task:
            manager_ids = select(User.id).where(
                User.role.in_(list(MANAGER_ROLES))
            )
            return query.where(
                or_(
                    model.direction == user.direction,
                    (model.direction.is_(None))
                    & (model.created_by.in_(manager_ids)),
                )
            )

        return query.where(model.direction == user.direction)

    if user.role == SCHOOL_ADVISOR:
        return query.where(model.created_by == user.id)

    return query


def validate_direction_code(db: Session, code: str) -> str:
    """Yo'nalish kodi mavjud va faol ekanini tekshiradi."""
    code = (code or "").strip()
    found = db.scalar(select(Direction).where(Direction.code == code))

    if not found:
        raise HTTPException(
            status_code=422, detail="Bunday yo'nalish mavjud emas."
        )

    if not found.is_active:
        raise HTTPException(
            status_code=422, detail="Bu yo'nalish faol emas."
        )

    return found.code


def own_direction_for(user: User) -> str | None:
    """Yangi yozuv uchun yo'nalish: faqat koordinatorda bo'ladi."""
    if user.role != COORDINATOR:
        return None

    if not user.direction:
        raise HTTPException(
            status_code=400,
            detail="Hisobingizga yo'nalish biriktirilmagan.",
        )

    return user.direction


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


@app.get("/panel", include_in_schema=False)
def panel_page():
    return FileResponse(STATIC_DIR / "panel.html")

    return FileResponse(index_file)


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}


# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------


@app.post("/auth/login", response_model=TokenResponse)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    username = form.username.strip().lower()

    client_ip = request.client.host if request.client else "unknown"
    limiter_key = f"{client_ip}|{username}"

    wait = login_limiter.retry_after(limiter_key)

    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Juda ko'p muvaffaqiyatsiz urinish. "
                f"{wait} soniyadan keyin qayta urinib ko'ring."
            ),
            headers={"Retry-After": str(wait)},
        )

    user = db.scalar(
        select(User).where(User.username == username)
    )

    if (
        not user
        or not user.is_active
        or not verify_password(form.password, user.password_hash)
    ):
        if login_limiter.register_failure(limiter_key):
            audit(
                db,
                user,
                "login_locked",
                "user",
                user.id if user else None,
                f"Ko'p xato urinish sababli vaqtincha bloklandi: {username[:80]}",
            )
            db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username yoki parol noto'g'ri.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_limiter.reset(limiter_key)

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

@app.post("/auth/telegram-link-code")
def telegram_link_code(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        code, expires_at = create_link_code(db, user.id)

        audit(
            db,
            user,
            "create",
            "telegram_link",
            user.id,
            "Telegram akkauntini bog'lash kodi yaratildi",
        )
        db.commit()

        return {
            "code": code,
            "expires_at": expires_at.isoformat(),
            "expires_in_minutes": 10,
            "instruction": f"Telegram botga /link {code} yuboring.",
        }

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------
# SCHOOLS
# ---------------------------------------------------------

@app.get("/schools", response_model=list[SchoolOut])
def list_schools(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(School).order_by(School.name)

    if user.role in SCHOOL_BOUND_ROLES:
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
# DIRECTIONS
# ---------------------------------------------------------

@app.get("/directions", response_model=list[DirectionOut])
def list_directions(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = select(Direction).order_by(Direction.sort_order, Direction.id)

    if not (include_inactive and user.role == ADMIN):
        query = query.where(Direction.is_active.is_(True))

    return list(db.scalars(query).all())


@app.patch("/admin/directions/{direction_id}", response_model=DirectionOut)
def update_direction(
    direction_id: int,
    payload: DirectionUpdate,
    db: Session = Depends(get_db),
    user=Depends(role_guard(ADMIN)),
):
    direction = db.get(Direction, direction_id)

    if not direction:
        raise HTTPException(status_code=404, detail="Yo'nalish topilmadi.")

    changes = payload.model_dump(exclude_unset=True)

    # Faol koordinatori bor yo'nalishni o'chirib bo'lmaydi.
    if changes.get("is_active") is False and direction.is_active:
        in_use = db.scalar(
            select(User.id).where(
                User.role == COORDINATOR,
                User.direction == direction.code,
                User.is_active.is_(True),
            )
        )

        if in_use is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Bu yo'nalishda faol koordinator bor. "
                    "Avval uni boshqa yo'nalishga o'tkazing."
                ),
            )

    for key, value in changes.items():
        setattr(direction, key, value)

    audit(db, user, "update", "direction", direction.id, direction.code)
    commit_or_rollback(db)
    db.refresh(direction)

    return direction


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

    if user.role in SCHOOL_BOUND_ROLES:
        if user.school_id is None:
            return []
        query = query.where(User.school_id == user.school_id)

    elif user.role in MANAGER_ROLES and user.role != ADMIN:
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

    data["school_id"], data["direction"] = resolve_assignment(
        db,
        user,
        data["role"],
        data.get("school_id"),
        data.get("direction"),
    )

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

    # Adminning rolini bu endpoint orqali o'zgartirib bo'lmaydi.
    if target.role == ADMIN and "role" in changes:
        raise HTTPException(
            status_code=403,
            detail="Admin rolini bu endpoint orqali o'zgartirib bo'lmaydi.",
        )

    new_role = changes.get("role", target.role)

    changes["school_id"], changes["direction"] = resolve_assignment(
        db,
        user,
        new_role,
        changes.get("school_id", target.school_id),
        changes.get("direction", target.direction),
        is_active=changes.get("is_active", target.is_active),
        exclude_user_id=target.id,
        current_direction=target.direction,
    )

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
    user=Depends(role_guard(*SCHOOL_BOUND_ROLES)),
):
    report = Report(
        **payload.model_dump(),
        school_id=user.school_id or default_school_id(db),
        created_by=user.id,
        direction=own_direction_for(user),
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
    query = scope_query(
        select(Report).order_by(Report.created_at.desc()), Report, user
    )

    if user.role in MANAGER_ROLES and school_id is not None:
        query = query.where(Report.school_id == school_id)

    return list(db.scalars(query).all())


@app.patch("/reports/{report_id}/review", response_model=ReportOut)
def review_report(
    report_id: int,
    payload: ReportReview,
    db: Session = Depends(get_db),
    user=Depends(role_guard(*MANAGER_ROLES)),
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
    user=Depends(role_guard(*SCHOOL_BOUND_ROLES)),
):
    project = Project(
        **payload.model_dump(),
        school_id=user.school_id or default_school_id(db),
        created_by=user.id,
        direction=own_direction_for(user),
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
    query = scope_query(
        select(Project).order_by(Project.created_at.desc()), Project, user
    )

    if user.role in MANAGER_ROLES and school_id is not None:
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
    user=Depends(role_guard(*MANAGER_ROLES, *SCHOOL_BOUND_ROLES)),
):
    data = payload.model_dump()
    school_id = data.get("school_id")
    direction = (data.get("direction") or "").strip() or None

    if user.role in SCHOOL_BOUND_ROLES:
        school_id = user.school_id or default_school_id(db)

        # Koordinator faqat o'z yo'nalishi uchun topshiriq yaratadi.
        own = own_direction_for(user)

        if direction and direction != own:
            raise HTTPException(
                status_code=403,
                detail="Boshqa yo'nalish uchun topshiriq yarata olmaysiz.",
            )

        direction = own
    elif school_id is None:
        # Maktab ko'rsatilmasa, standart (bitta) maktab ishlatiladi.
        school_id = default_school_id(db)

    school_access(db, user, school_id)

    # Rahbariyat yo'nalish bermasa, topshiriq umumiy hisoblanadi.
    if direction and user.role in MANAGER_ROLES:
        direction = validate_direction_code(db, direction)

    data["school_id"] = school_id
    data["direction"] = direction
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
    query = scope_query(
        select(Task).order_by(Task.created_at.desc()), Task, user
    )

    if user.role in MANAGER_ROLES and school_id is not None:
        query = query.where(Task.school_id == school_id)

    return list(db.scalars(query).all())


@app.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # Ko'ra olmaydigan topshiriq uchun 404 qaytariladi (mavjudligi sezdirilmaydi).
    task = db.scalar(
        scope_query(select(Task).where(Task.id == task_id), Task, user)
    )

    if not task:
        raise HTTPException(status_code=404, detail="Topshiriq topilmadi.")

    changes = payload.model_dump(exclude_unset=True)

    if user.role in SCHOOL_BOUND_ROLES:
        # Maktab xodimi topshiriqning faqat holatini o'zgartiradi.
        if set(changes.keys()) - {"status"}:
            raise HTTPException(
                status_code=403,
                detail="Siz faqat topshiriq holatini o'zgartira olasiz.",
            )

        # Umumiy topshiriq holatini koordinatorlar emas, rahbariyat belgilaydi.
        if user.role == COORDINATOR and task.direction is None:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Umumiy topshiriq holatini faqat rahbariyat "
                    "o'zgartira oladi."
                ),
            )
    elif user.role not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Ruxsat yo'q.")

    if changes.get("direction"):
        changes["direction"] = validate_direction_code(
            db, changes["direction"]
        )

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

    if user.role in SCHOOL_BOUND_ROLES:
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

    if user.role in SCHOOL_BOUND_ROLES:
        user_query = user_query.where(User.school_id == user.school_id)

    # Hisobot, loyiha va topshiriqlar soni ruxsat doirasiga qarab hisoblanadi.
    report_query = scope_query(report_query, Report, user)
    project_query = scope_query(project_query, Project, user)
    pending_query = scope_query(pending_query, Task, user)
    completed_query = scope_query(completed_query, Task, user)

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


def load_ai_overview(db: Session, user: User, window_days: int) -> dict:
    """Foydalanuvchi ko'ra oladigan ma'lumotlar asosida AI tahlilini tuzadi.

    Ma'lumotlar scope_query() orqali cheklanadi, shuning uchun har kim
    faqat o'z vakolati doirasidagi tahlilni oladi.
    """
    active = list(
        db.scalars(
            select(Direction)
            .where(Direction.is_active.is_(True))
            .order_by(Direction.sort_order, Direction.id)
        ).all()
    )

    if user.role in MANAGER_ROLES:
        visible = active
    elif user.role == COORDINATOR:
        visible = [d for d in active if d.code == user.direction]
    else:
        visible = []

    directions = [{"code": d.code, "name": d.name} for d in visible]

    reports = [
        {"direction": r.direction, "status": r.status,
         "created_at": r.created_at}
        for r in db.execute(
            scope_query(
                select(Report.direction, Report.status, Report.created_at),
                Report,
                user,
            )
        ).all()
    ]
    projects = [
        {"direction": r.direction, "status": r.status,
         "created_at": r.created_at}
        for r in db.execute(
            scope_query(
                select(Project.direction, Project.status, Project.created_at),
                Project,
                user,
            )
        ).all()
    ]
    tasks = [
        {"id": r.id, "title": r.title, "direction": r.direction,
         "status": r.status, "deadline": r.deadline}
        for r in db.execute(
            scope_query(
                select(
                    Task.id,
                    Task.title,
                    Task.direction,
                    Task.status,
                    Task.deadline,
                ),
                Task,
                user,
            )
        ).all()
    ]

    return build_overview(
        directions, reports, projects, tasks, window_days=window_days
    )


@app.get("/ai/overview")
def ai_overview(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Yo'nalishlar bo'yicha statistik tahlil (API kalit talab qilmaydi)."""
    return load_ai_overview(db, user, window_days)


@app.get("/ai/report")
def ai_period_report(
    period: str = Query(default="week", pattern="^(week|month)$"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Haftalik yoki oylik matnli hisobotni tayyorlaydi."""
    days = 7 if period == "week" else 30
    overview = load_ai_overview(db, user, days)

    audit(db, user, "generate", "ai_report", None, f"period={period}")
    commit_or_rollback(db)

    return build_period_report(overview, period)
