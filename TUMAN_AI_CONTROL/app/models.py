
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(200), unique=True, index=True, nullable=False
    )
    district: Mapped[str] = mapped_column(
        String(150), default="", nullable=False
    )
    address: Mapped[str] = mapped_column(
        String(300), default="", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    users: Mapped[list["User"]] = relationship(back_populates="school")
    reports: Mapped[list["Report"]] = relationship(back_populates="school")
    projects: Mapped[list["Project"]] = relationship(back_populates="school")
    tasks: Mapped[list["Task"]] = relationship(back_populates="school")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(80), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str] = mapped_column(
        String(40), index=True, nullable=False
    )
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Koordinatorning yo'nalishi (directions.code). Boshqa rollarda bo'sh.
    direction: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    school: Mapped["School | None"] = relationship(back_populates="users")
    reports: Mapped[list["Report"]] = relationship(back_populates="creator")
    projects: Mapped[list["Project"]] = relationship(back_populates="creator")
    tasks_created: Mapped[list["Task"]] = relationship(
        back_populates="creator",
        foreign_keys="Task.created_by",
    )


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_school_period", "school_id", "period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    period: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="submitted", index=True, nullable=False
    )
    evidence_url: Mapped[str] = mapped_column(
        String(1000), default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Yo'nalish kodi (directions.code). Bo'sh bo'lsa: yo'nalishga bog'lanmagan.
    direction: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    school: Mapped["School"] = relationship(back_populates="reports")
    creator: Mapped["User"] = relationship(back_populates="reports")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), default="AI", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="planned", index=True, nullable=False
    )
    evidence_url: Mapped[str] = mapped_column(
        String(1000), default="", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Yo'nalish kodi (directions.code). Bo'sh bo'lsa: yo'nalishga bog'lanmagan.
    direction: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    school: Mapped["School"] = relationship(back_populates="projects")
    creator: Mapped["User"] = relationship(back_populates="projects")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Yo'nalish kodi (directions.code). Bo'sh bo'lsa: yo'nalishga bog'lanmagan.
    direction: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )

    school: Mapped["School"] = relationship(back_populates="tasks")
    creator: Mapped["User"] = relationship(
        back_populates="tasks_created",
        foreign_keys=[created_by],
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Direction(Base):
    """Kengash yo'nalishlari. Nomlari admin tomonidan o'zgartiriladi."""

    __tablename__ = "directions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
