
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


Role = Literal[
    "admin",
    "director",
    "kelajak_leader",
    "coordinator",
    "school_advisor",
    "district_coordinator",
    "school_coordinator",
]

ReportStatus = Literal[
    "submitted",
    "reviewed",
    "needs_revision",
]

ProjectStatus = Literal[
    "planned",
    "in_progress",
    "completed",
    "paused",
]

TaskStatus = Literal[
    "pending",
    "in_progress",
    "completed",
    "cancelled",
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=128)
    role: Role
    school_id: int | None = Field(default=None, ge=1)
    direction: str | None = Field(default=None, max_length=50)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip().lower()

        allowed = set(
            "abcdefghijklmnopqrstuvwxyz"
            "0123456789._-"
        )

        if not value or any(char not in allowed for char in value):
            raise ValueError(
                "Login faqat lotin harflari, raqam, nuqta, "
                "pastki chiziq va defisdan iborat bo'lishi mumkin."
            )

        return value

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Ism-familiya bo'sh bo'lmasligi kerak.")
        return value


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    role: Role | None = None
    school_id: int | None = Field(default=None, ge=1)
    direction: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class UserOut(ORMModel):
    id: int
    username: str
    full_name: str
    role: str
    school_id: int | None
    direction: str | None = None
    is_active: bool
    created_at: datetime


class DirectionOut(ORMModel):
    id: int
    code: str
    name: str
    sort_order: int
    is_active: bool


class DirectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value


class SchoolCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    district: str = Field(default="", max_length=150)
    address: str = Field(default="", max_length=300)

    @field_validator("name", "district", "address")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return " ".join(value.split())


class SchoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    district: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None

    @field_validator("name", "district", "address")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())


class SchoolOut(ORMModel):
    id: int
    name: str
    district: str
    address: str
    is_active: bool
    created_at: datetime


class ReportCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    period: str = Field(min_length=2, max_length=100)
    summary: str = Field(min_length=10, max_length=10000)
    evidence_url: str = Field(default="", max_length=1000)

    @field_validator("title", "period", "summary")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Bu maydon bo'sh bo'lmasligi kerak.")
        return value

    @field_validator("evidence_url")
    @classmethod
    def validate_evidence_url(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Dalil havolasi http:// yoki https:// bilan boshlansin.")
        return value


class ReportReview(BaseModel):
    status: ReportStatus
    review_note: str = Field(default="", max_length=3000)


class ReportOut(ORMModel):
    id: int
    school_id: int
    created_by: int
    title: str
    period: str
    summary: str
    status: str
    evidence_url: str
    direction: str | None = None
    created_at: datetime


class ProjectCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=10000)
    category: str = Field(default="AI", min_length=2, max_length=100)
    status: ProjectStatus = "planned"
    evidence_url: str = Field(default="", max_length=1000)

    @field_validator("title", "description", "category")
    @classmethod
    def normalize_project_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("evidence_url")
    @classmethod
    def validate_project_url(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Havola http:// yoki https:// bilan boshlansin.")
        return value


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    status: ProjectStatus | None = None
    evidence_url: str | None = Field(default=None, max_length=1000)


class ProjectOut(ORMModel):
    id: int
    school_id: int
    created_by: int
    title: str
    description: str
    category: str
    status: str
    evidence_url: str
    direction: str | None = None
    created_at: datetime


class TaskCreate(BaseModel):
    school_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=10000)
    deadline: datetime | None = None
    direction: str | None = Field(default=None, max_length=50)

    @field_validator("title")
    @classmethod
    def normalize_task_title(cls, value: str) -> str:
        return value.strip()


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    deadline: datetime | None = None
    status: TaskStatus | None = None
    direction: str | None = Field(default=None, max_length=50)


class TaskOut(ORMModel):
    id: int
    school_id: int
    created_by: int
    title: str
    description: str
    deadline: datetime | None
    status: str
    direction: str | None = None
    created_at: datetime


class AIAnalysisRequest(BaseModel):
    text: str = Field(min_length=10, max_length=15000)
    context: str = Field(default="report", max_length=50)


class AIAnalysisResponse(BaseModel):
    summary: str
    strengths: list[str]
    risks: list[str]
    recommendations: list[str]
    limitations: list[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    schools_count: int
    active_schools_count: int
    users_count: int
    reports_count: int
    projects_count: int
    tasks_pending_count: int
    tasks_completed_count: int
