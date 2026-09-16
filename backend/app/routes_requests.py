from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.database import get_db
from app.models import ResourceRequest, User, UserRole, RequestStatus
from app.schemas import ResourceRequestCreate, ResourceRequestOut, RejectRequest
from app.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/requests", tags=["requests"])


ALLOWED_TRANSITIONS = {
    RequestStatus.pending: {RequestStatus.approved, RequestStatus.rejected},
    RequestStatus.approved: {RequestStatus.provisioning},
    RequestStatus.provisioning: {RequestStatus.provisioned, RequestStatus.failed},
    RequestStatus.rejected: set(),
    RequestStatus.provisioned: set(),
    RequestStatus.failed: set(),
}


def transition_status(req: ResourceRequest, new_status: RequestStatus):
    allowed = ALLOWED_TRANSITIONS.get(req.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move a request from '{req.status.value}' to '{new_status.value}'",
        )
    req.status = new_status
    req.updated_at = datetime.now(timezone.utc)


@router.post("", response_model=ResourceRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    request_in: ResourceRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_request = ResourceRequest(
        user_id=current_user.id,
        workload_level=request_in.workload_level,
        os=request_in.os,
        region=request_in.region,
        storage_gb=request_in.storage_gb,
        purpose=request_in.purpose,
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request


@router.get("", response_model=List[ResourceRequestOut])
def list_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ResourceRequest)
    if current_user.role != UserRole.admin:
        query = query.filter(ResourceRequest.user_id == current_user.id)
    return query.order_by(ResourceRequest.created_at.desc()).all()


@router.get("/{request_id}", response_model=ResourceRequestOut)
def get_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()

    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if current_user.role != UserRole.admin and req.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this request")

    return req


@router.patch("/{request_id}/approve", response_model=ResourceRequestOut)
def approve_request(
    request_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    transition_status(req, RequestStatus.approved)
    req.reviewed_by = admin.id

    db.commit()
    db.refresh(req)
    return req


@router.patch("/{request_id}/reject", response_model=ResourceRequestOut)
def reject_request(
    request_id: int,
    body: RejectRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    transition_status(req, RequestStatus.rejected)
    req.reviewed_by = admin.id
    if body.reason:
        req.purpose = f"{req.purpose or ''}\n[Rejected: {body.reason}]".strip()

    db.commit()
    db.refresh(req)
    return req


@router.patch("/{request_id}/start-provisioning", response_model=ResourceRequestOut)
def start_provisioning(
    request_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    transition_status(req, RequestStatus.provisioning)

    db.commit()
    db.refresh(req)
    return req
