from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ResourceRequest, User
from app.dependencies import get_current_user   # if the error says it can't be found, use: from app.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])

STATUSES = ["pending", "approved", "rejected", "provisioning", "provisioned", "failed"]


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if str(getattr(current_user.role, "value", current_user.role)).lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


def status_value(req) -> str:
    return str(getattr(req.status, "value", req.status)).lower()


def serialize(r: ResourceRequest) -> dict:
    owner = getattr(r, "owner", None) or getattr(r, "user", None)
    return {
        "id": r.id,
        "user_id": getattr(r, "user_id", None),
        "user_name": getattr(owner, "full_name", None) or getattr(owner, "email", None),
        "instance_type": getattr(r, "instance_type", None),
        "os": getattr(r, "os", None),
        "region": getattr(r, "region", None),
        "storage": getattr(r, "storage", None),
        "purpose": getattr(r, "purpose", None),
        "status": status_value(r),
        "rejection_reason": getattr(r, "rejection_reason", None),
        "created_at": getattr(r, "created_at", None),
    }


def get_pending_or_fail(db: Session, request_id: int) -> ResourceRequest:
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if status_value(req) != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Only pending requests can be reviewed. This one is {status_value(req)}.",
        )
    return req


@router.get("/stats")
def admin_stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    counts = {s: 0 for s in STATUSES}
    for req in db.query(ResourceRequest).all():
        key = status_value(req)
        counts[key] = counts.get(key, 0) + 1
    counts["total"] = sum(counts[s] for s in STATUSES)
    return counts


@router.get("/requests")
def list_all_requests(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rows = db.query(ResourceRequest).order_by(ResourceRequest.id.desc()).all()
    if status:
        rows = [r for r in rows if status_value(r) == status.lower()]
    return [serialize(r) for r in rows]


@router.patch("/requests/{request_id}/approve")
def approve_request(
    request_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    req = get_pending_or_fail(db, request_id)
    req.status = "approved"
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(req)
    return serialize(req)


@router.patch("/requests/{request_id}/reject")
def reject_request(
    request_id: int,
    body: RejectBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    req = get_pending_or_fail(db, request_id)
    req.status = "rejected"
    req.rejection_reason = body.reason
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(req)
    return serialize(req)