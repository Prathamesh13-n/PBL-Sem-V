import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

from app.models import UserRole, WorkloadLevel, RequestStatus
from app.pricing import MIN_HOURS, MAX_HOURS


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Resource Requests ----

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{1,38}[A-Za-z0-9]$")


class ResourceRequestCreate(BaseModel):
    instance_name: str
    duration_hours: int
    workload_level: WorkloadLevel
    os: str
    region: str
    storage_gb: int
    purpose: Optional[str] = None

    @field_validator("instance_name")
    @classmethod
    def check_name(cls, v: str) -> str:
        v = v.strip()
        if not NAME_PATTERN.match(v):
            raise ValueError(
                "Name must be 3-40 characters: letters, numbers, spaces, '-', '_' or '.'"
            )
        return v

    @field_validator("duration_hours")
    @classmethod
    def check_hours(cls, v: int) -> int:
        if v < MIN_HOURS or v > MAX_HOURS:
            raise ValueError(
                f"Time must be between {MIN_HOURS} hour and {MAX_HOURS // 24} days. "
                f"For more than {MAX_HOURS // 24} days, please contact the admin."
            )
        return v

    @field_validator("storage_gb")
    @classmethod
    def check_storage(cls, v: int) -> int:
        if v < 8 or v > 30:
            raise ValueError("Storage must be between 8 and 30 GB")
        return v


class ResourceRequestOut(BaseModel):
    id: int
    user_id: int
    resource_type: str
    instance_name: Optional[str] = None
    duration_hours: Optional[int] = None
    workload_level: WorkloadLevel
    instance_type: Optional[str]
    os: str
    region: str
    storage_gb: int
    purpose: Optional[str]
    estimated_cost: Optional[Decimal]
    security_score: Optional[int]
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    status: RequestStatus
    reviewed_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class RejectRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def check_reason(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Please give a reason of at least 5 characters")
        if len(v) > 300:
            raise ValueError("The reason must be 300 characters or fewer")
        return v