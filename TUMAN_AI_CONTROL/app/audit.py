
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_audit(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: str = "",
) -> None:
    # Maxfiy ma'lumotlar: parol, token va API kalitlarini
    # details maydoniga yozmang.
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action[:100],
        entity_type=entity_type[:100],
        entity_id=entity_id,
        details=details[:4000],
    )
    db.add(entry)
