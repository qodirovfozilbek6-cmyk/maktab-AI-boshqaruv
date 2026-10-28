
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ADMIN = "admin"
DIRECTOR = "director"
KELAJAK_LEADER = "kelajak_leader"
COORDINATOR = "coordinator"
SCHOOL_ADVISOR = "school_advisor"

# Eski rollar (Tuman AI Control). Mavjud foydalanuvchilar buzilmasligi
# uchun saqlab qolindi.
DISTRICT_COORDINATOR = "district_coordinator"
SCHOOL_COORDINATOR = "school_coordinator"

VALID_ROLES = {
    ADMIN,
    DIRECTOR,
    KELAJAK_LEADER,
    COORDINATOR,
    SCHOOL_ADVISOR,
    DISTRICT_COORDINATOR,
    SCHOOL_COORDINATOR,
}

# Barcha maktab ma'lumotlarini ko'ra oladigan va hisobotlarni tekshiradigan rollar.
MANAGER_ROLES = frozenset(
    {ADMIN, DIRECTOR, KELAJAK_LEADER, DISTRICT_COORDINATOR}
)

# Faqat o'z maktabi doirasida ishlaydigan rollar.
SCHOOL_BOUND_ROLES = frozenset(
    {COORDINATOR, SCHOOL_ADVISOR, SCHOOL_COORDINATOR}
)

# Admin API orqali yaratilmaydi, shuning uchun u bu to'plamda yo'q.
ASSIGNABLE_ROLES = VALID_ROLES - {ADMIN}


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kirish muddati tugagan yoki token yaroqsiz.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if not payload:
        raise credentials_error

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError, KeyError):
        raise credentials_error

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise credentials_error

    # Rol token ichidagi eski qiymatdan emas, bazadagi joriy qiymatdan olinadi.
    if user.role not in VALID_ROLES:
        raise credentials_error

    return user


def require_roles(*roles: str):
    def dependency(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu amalni bajarishga ruxsatingiz yo'q.",
            )
        return user

    return dependency


def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if user.role != ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faqat administrator uchun.",
        )
    return user


def require_district_access(
    user: User = Depends(get_current_user),
) -> User:
    if user.role not in {ADMIN, DISTRICT_COORDINATOR}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tuman ma'lumotlariga kirish ruxsati yo'q.",
        )
    return user


def require_school_assignment(user: User) -> int:
    if user.role != SCHOOL_COORDINATOR or user.school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foydalanuvchiga maktab biriktirilmagan.",
        )
    return user.school_id
