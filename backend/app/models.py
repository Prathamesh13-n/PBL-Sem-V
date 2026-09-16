import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Numeric,
    ForeignKey,
    DateTime,
    Enum,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class WorkloadLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    provisioning = "provisioning"
    provisioned = "provisioned"
    failed = "failed"


class DeploymentStatus(str, enum.Enum):
    provisioning = "provisioning"
    provisioned = "provisioned"
    failed = "failed"
    destroyed = "destroyed"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.user)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # One user can have many resource requests
    requests = relationship(
        "ResourceRequest",
        back_populates="user",
        foreign_keys="ResourceRequest.user_id",
    )


class ResourceRequest(Base):
    __tablename__ = "resource_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    resource_type = Column(String(20), default="EC2")
    workload_level = Column(Enum(WorkloadLevel), nullable=False)
    instance_type = Column(String(20), nullable=True)  # e.g. t3.micro (set by recommendation engine)
    os = Column(String(30), nullable=False)
    region = Column(String(20), nullable=False)
    storage_gb = Column(Integer, nullable=False)
    purpose = Column(Text, nullable=True)

    estimated_cost = Column(Numeric(10, 2), nullable=True)
    security_score = Column(Integer, nullable=True)

    status = Column(Enum(RequestStatus), nullable=False, default=RequestStatus.pending)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="requests", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    deployment = relationship(
        "Deployment", back_populates="request", uselist=False, cascade="all, delete-orphan"
    )


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("resource_requests.id"), unique=True, nullable=False)

    instance_id = Column(String(50), nullable=True)
    public_ip = Column(String(20), nullable=True)
    terraform_state_path = Column(String(255), nullable=True)

    deployment_status = Column(Enum(DeploymentStatus), nullable=False, default=DeploymentStatus.provisioning)
    error_message = Column(Text, nullable=True)

    provisioned_at = Column(DateTime(timezone=True), nullable=True)
    destroyed_at = Column(DateTime(timezone=True), nullable=True)

    request = relationship("ResourceRequest", back_populates="deployment")