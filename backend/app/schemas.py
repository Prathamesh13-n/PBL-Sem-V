from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models import UserRole, WorkloadLevel, RequestStatus


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

class ResourceRequestCreate(BaseModel):
    workload_level: WorkloadLevel
    os: str
    region: str
    storage_gb: int
    purpose: Optional[str] = None


class ResourceRequestOut(BaseModel):
    id: int
    user_id: int
    resource_type: str
    workload_level: WorkloadLevel
    instance_type: Optional[str]
    os: str
    region: str
    storage_gb: int
    purpose: Optional[str]
    estimated_cost: Optional[Decimal]
    security_score: Optional[int]
    status: RequestStatus
    reviewed_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class RejectRequest(BaseModel):
    reason: Optional[str] = None