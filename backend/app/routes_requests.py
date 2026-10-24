from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.database import get_db
from app.models import (
    ResourceRequest,
    User,
    UserRole,
    RequestStatus,
    Deployment,
    DeploymentStatus,
)
from app.schemas import ResourceRequestCreate, ResourceRequestOut, RejectRequest
from app.dependencies import get_current_user, require_admin
from app.models import WorkloadLevel
from app.pricing import estimate, options_with_prices, MIN_HOURS, MAX_HOURS
from app.recommendation import recommend, recommended_type
from app.security import validate as security_validate
from app.terraform_runner import (
    run_provision,
    run_destroy,
    try_start,
    expires_at,
    lifetime_hours,
    aware,
    AUTO_PROVISION,
)

router = APIRouter(prefix="/requests", tags=["requests"])


ALLOWED_TRANSITIONS = {
    RequestStatus.pending: {RequestStatus.approved, RequestStatus.rejected},
    RequestStatus.approved: {RequestStatus.provisioning},
    RequestStatus.provisioning: {RequestStatus.provisioned, RequestStatus.failed},
    RequestStatus.rejected: set(),
    # a provisioned instance can be destroyed
    RequestStatus.provisioned: {RequestStatus.destroyed},
    RequestStatus.destroyed: set(),
    # a failed provisioning can be retried
    RequestStatus.failed: {RequestStatus.provisioning},
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


def begin_provisioning(req: ResourceRequest, db: Session, background_tasks: BackgroundTasks):
    """approved (or failed) -> provisioning, then Terraform runs in the background."""
    transition_status(req, RequestStatus.provisioning)

    # create the deployment record, or reset it when retrying after a failure
    dep = req.deployment
    if dep is None:
        dep = Deployment(request_id=req.id)
        db.add(dep)
    dep.deployment_status = DeploymentStatus.provisioning
    dep.error_message = None
    dep.instance_id = None
    dep.public_ip = None

    db.commit()
    db.refresh(req)

    # Terraform runs in the background so the request returns immediately
    if try_start(req.id):
        background_tasks.add_task(run_provision, req.id)


@router.post("", response_model=ResourceRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    request_in: ResourceRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # rule-based recommendation: the workload level decides the instance type
    instance_type = recommended_type(request_in.workload_level.value)

    new_request = ResourceRequest(
        user_id=current_user.id,
        instance_name=request_in.instance_name,
        duration_hours=request_in.duration_hours,
        instance_type=instance_type,
        estimated_cost=estimate(
            request_in.storage_gb, request_in.duration_hours, instance_type
        )["inr"],
        workload_level=request_in.workload_level,
        os=request_in.os,
        region=request_in.region,
        storage_gb=request_in.storage_gb,
        purpose=request_in.purpose,
        security_score=security_validate(
            request_in.duration_hours, request_in.purpose, instance_type
        )["score"],
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


@router.get("/recommendation")
def recommendation(
    workload: WorkloadLevel = WorkloadLevel.low,
    storage_gb: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Recommended instance for a workload level, with an estimated monthly cost."""
    storage_gb = min(max(storage_gb, 8), 30)
    return recommend(workload.value, storage_gb)


@router.get("/duration-options")
def duration_options(
    storage_gb: int = 20,
    workload: WorkloadLevel = WorkloadLevel.low,
    current_user: User = Depends(get_current_user),
):
    """Time choices with an approximate price for the given storage and workload."""
    storage_gb = min(max(storage_gb, 8), 30)
    return options_with_prices(storage_gb, recommended_type(workload.value))


@router.get("/estimate")
def price_estimate(
    storage_gb: int = 20,
    hours: int = 2,
    workload: WorkloadLevel = WorkloadLevel.low,
    current_user: User = Depends(get_current_user),
):
    """Approximate price for any custom time (used by the custom end date)."""
    if hours < MIN_HOURS or hours > MAX_HOURS:
        raise HTTPException(
            status_code=400,
            detail=f"Time must be between {MIN_HOURS} hour and {MAX_HOURS // 24} days",
        )
    storage_gb = min(max(storage_gb, 8), 30)
    e = estimate(storage_gb, hours, recommended_type(workload.value))
    return {"hours": hours, "usd": float(e["usd"]), "inr": float(e["inr"])}


@router.get("/preview")
def request_preview(
    workload: WorkloadLevel = WorkloadLevel.low,
    storage_gb: int = 20,
    hours: int = 2,
    purpose: str = "",
    current_user: User = Depends(get_current_user),
):
    """Day 29: the whole review in one call - recommendation, cost and security check."""
    if hours < MIN_HOURS or hours > MAX_HOURS:
        raise HTTPException(
            status_code=400,
            detail=f"Time must be between {MIN_HOURS} hour and {MAX_HOURS // 24} days",
        )
    storage_gb = min(max(storage_gb, 8), 30)
    rec = recommend(workload.value, storage_gb)
    e = estimate(storage_gb, hours, rec["instance_type"])
    sec = security_validate(hours, purpose, rec["instance_type"])
    return {
        "recommendation": rec,
        "cost": {"hours": hours, "usd": float(e["usd"]), "inr": float(e["inr"])},
        "security": sec,
    }


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


@router.get("/{request_id}/security")
def get_security(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Security validation result for one request (owner or admin)."""
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if current_user.role != UserRole.admin and req.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this request")
    result = security_validate(req.duration_hours, req.purpose, req.instance_type)
    # keep the stored score in step with the current rules
    if req.security_score != result["score"]:
        req.security_score = result["score"]
        db.commit()
    return result


@router.get("/{request_id}/deployment")
def get_deployment(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if current_user.role != UserRole.admin and req.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this request")

    dep = req.deployment
    if not dep:
        return {"deployment_status": None}
    return {
        "deployment_status": dep.deployment_status.value,
        "instance_id": dep.instance_id,
        "public_ip": dep.public_ip,
        "error_message": dep.error_message if current_user.role == UserRole.admin else (
            "Provisioning failed. Please contact an administrator." if dep.error_message else None
        ),
        "provisioned_at": aware(dep.provisioned_at),
        "destroyed_at": aware(dep.destroyed_at),
        "expires_at": (
            expires_at(dep)
            if dep.deployment_status == DeploymentStatus.provisioned
            else None
        ),
        "lifetime_hours": lifetime_hours(dep),
    }


@router.patch("/{request_id}/approve", response_model=ResourceRequestOut)
def approve_request(
    request_id: int,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    transition_status(req, RequestStatus.approved)
    req.reviewed_by = admin.id
    req.reviewed_at = datetime.now(timezone.utc)

    if AUTO_PROVISION:
        # approved -> provisioning -> (Terraform) -> provisioned / failed
        begin_provisioning(req, db, background_tasks)
        return req

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
    req.reviewed_at = datetime.now(timezone.utc)
    req.rejection_reason = body.reason  # kept separate, the purpose stays unchanged

    db.commit()
    db.refresh(req)
    return req


@router.patch("/{request_id}/start-provisioning", response_model=ResourceRequestOut)
def start_provisioning(
    request_id: int,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    begin_provisioning(req, db, background_tasks)
    return req


@router.post("/{request_id}/destroy")
def destroy_deployment(
    request_id: int,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    req = db.query(ResourceRequest).filter(ResourceRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    dep = req.deployment
    if not dep or dep.deployment_status != DeploymentStatus.provisioned:
        raise HTTPException(
            status_code=400,
            detail="Only a provisioned deployment can be destroyed",
        )

    if not try_start(req.id):
        raise HTTPException(status_code=409, detail="A Terraform job is already running for this request")

    background_tasks.add_task(run_destroy, req.id)
    return {"message": "Destroy started"}