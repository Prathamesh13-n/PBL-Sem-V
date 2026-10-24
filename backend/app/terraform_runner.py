"""Runs Terraform for one portal request.

Layout (project root = the folder that holds backend/ and terraform/):
    terraform/            template files (main.tf, variables.tf, outputs.tf)
    terraform_runs/       one working folder per request: request-<id>/
    .terraform-plugin-cache/   shared provider download cache
"""
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.database import SessionLocal
from app.models import (
    Deployment,
    DeploymentStatus,
    RequestStatus,
    ResourceRequest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = PROJECT_ROOT / "terraform"
RUNS_DIR = PROJECT_ROOT / "terraform_runs"
PLUGIN_CACHE_DIR = PROJECT_ROOT / ".terraform-plugin-cache"

TEMPLATE_FILES = ["main.tf", "variables.tf", "outputs.tf", ".terraform.lock.hcl"]
# Sizes an AWS free-plan account may launch (checked with describe-instance-types,
# free-tier-eligible=true). t3.medium is refused by AWS on such accounts.
ALLOWED_TYPES = {"t2.micro", "t3.micro", "t3.small", "c7i-flex.large"}
# old requests made before this change keep working with the equal-sized allowed type
LEGACY_TYPES = {"t3.medium": "c7i-flex.large"}
DEFAULT_TYPE = "t3.micro"
MIN_STORAGE, MAX_STORAGE = 8, 30


# Only one Terraform job per request at a time (stops double clicks).
_active = set()
_guard = threading.Lock()

# "terraform init" copies the AWS provider through the shared plugin cache.
# Two inits at the same moment collide ("text file busy"), so they take turns.
_init_lock = threading.Lock()


def try_start(request_id: int) -> bool:
    """Claim a request for a Terraform job. False if one is already running."""
    with _guard:
        if request_id in _active:
            return False
        _active.add(request_id)
        return True


def _release(request_id: int):
    with _guard:
        _active.discard(request_id)


# How long an instance may live before it is destroyed automatically.
# Change with the environment variable INSTANCE_MAX_HOURS (default 2 hours).
# True = approving a request starts provisioning straight away (one click).
# Set the environment variable AUTO_PROVISION=0 to go back to "Approve, then Provision".
AUTO_PROVISION = os.getenv("AUTO_PROVISION", "1") != "0"

INIT_TIMEOUT = int(os.getenv("TERRAFORM_INIT_TIMEOUT", "600"))
APPLY_TIMEOUT = int(os.getenv("TERRAFORM_APPLY_TIMEOUT", "900"))
DESTROY_TIMEOUT = int(os.getenv("TERRAFORM_DESTROY_TIMEOUT", "900"))

MAX_LIFETIME_HOURS = float(os.getenv("INSTANCE_MAX_HOURS", "2"))
CHECK_EVERY_SECONDS = 60


def aware(dt):
    """SQLite returns naive datetimes; treat them as UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# For quick tests only: set FORCE_LIFETIME_HOURS (for example 0.1) to make EVERY
# instance expire after that many hours, whatever the user chose.
FORCE_LIFETIME_HOURS = os.getenv("FORCE_LIFETIME_HOURS")


def lifetime_hours(dep) -> float:
    """Hours this deployment may live: forced test value, else the time the
    user chose on the form, else the default limit (old requests)."""
    if FORCE_LIFETIME_HOURS:
        return float(FORCE_LIFETIME_HOURS)
    chosen = dep.request.duration_hours if dep is not None and dep.request else None
    return float(chosen) if chosen else MAX_LIFETIME_HOURS


def expires_at(dep):
    if dep is None or dep.provisioned_at is None:
        return None
    return aware(dep.provisioned_at) + timedelta(hours=lifetime_hours(dep))


def _now():
    return datetime.now(timezone.utc)


def workdir_for(request_id: int) -> Path:
    return RUNS_DIR / f"request-{request_id}"


def _env():
    PLUGIN_CACHE_DIR.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["TF_PLUGIN_CACHE_DIR"] = str(PLUGIN_CACHE_DIR)
    env["TF_IN_AUTOMATION"] = "1"
    # use the cached provider even if the lock file was made on another OS (Windows)
    env["TF_PLUGIN_CACHE_MAY_BREAK_DEPENDENCY_LOCK_FILE"] = "true"
    return env


def _terraform(args, cwd: Path, timeout: int):
    exe = shutil.which("terraform")
    if not exe:
        raise RuntimeError("Terraform was not found on PATH for the backend process.")
    try:
        proc = subprocess.run(
            [exe, *args],
            cwd=str(cwd),
            env=_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"terraform {args[0]} timed out after {timeout} seconds and was stopped.")
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-1500:]
        raise RuntimeError(f"terraform {args[0]} failed: {tail}")
    return proc


def _prepare_workdir(req: ResourceRequest) -> Path:
    workdir = workdir_for(req.id)
    workdir.mkdir(parents=True, exist_ok=True)

    for name in TEMPLATE_FILES:
        src = TEMPLATE_DIR / name
        if src.exists():
            shutil.copy2(src, workdir / name)

    wanted = LEGACY_TYPES.get(req.instance_type, req.instance_type)
    instance_type = wanted if wanted in ALLOWED_TYPES else DEFAULT_TYPE
    storage = min(max(req.storage_gb or MIN_STORAGE, MIN_STORAGE), MAX_STORAGE)

    # the name was validated when the request was created; strip anything odd anyway
    safe_name = "".join(ch for ch in (req.instance_name or "") if ch.isalnum() or ch in " _.-")[:40]

    tfvars = (
        f'request_id    = "{req.id}"\n'
        f'instance_name = "{safe_name}"\n'
        f'instance_type = "{instance_type}"\n'
        f"storage_gb    = {storage}\n"
        f'allowed_cidr  = ""\n'
    )
    (workdir / "terraform.tfvars").write_text(tfvars, encoding="utf-8")
    return workdir


def _created_resources(workdir: Path):
    """Resources Terraform still tracks in this folder (empty = nothing exists)."""
    if not (workdir / "terraform.tfstate").exists():
        return []
    out = _terraform(["state", "list", "-no-color"], workdir, 120).stdout
    return [line for line in out.splitlines() if line.strip()]


def run_provision(request_id: int):
    """Background job: terraform init + apply, then save the result."""
    db = SessionLocal()
    try:
        req = db.get(ResourceRequest, request_id)
        dep = db.query(Deployment).filter(Deployment.request_id == request_id).first()
        if not req or not dep:
            return

        apply_started = False
        workdir = None
        try:
            workdir = _prepare_workdir(req)
            dep.terraform_state_path = str(workdir / "terraform.tfstate")
            db.commit()

            with _init_lock:
                _terraform(["init", "-input=false", "-no-color"], workdir, INIT_TIMEOUT)
            apply_started = True
            _terraform(["apply", "-auto-approve", "-input=false", "-no-color", "-lock-timeout=60s"], workdir, APPLY_TIMEOUT)
            out = json.loads(_terraform(["output", "-json", "-no-color"], workdir, 60).stdout)

            dep.instance_id = out["instance_id"]["value"]
            dep.public_ip = out["public_ip"]["value"]
            dep.deployment_status = DeploymentStatus.provisioned
            dep.provisioned_at = _now()
            dep.error_message = None
            req.status = RequestStatus.provisioned
        except Exception as exc:  # any failure -> mark failed, keep the reason
            message = str(exc)[-1500:]
            if apply_started and workdir is not None:
                # remove anything that was created before the failure
                try:
                    created = _created_resources(workdir)
                    if created:
                        _terraform(
                            ["destroy", "-auto-approve", "-input=false", "-no-color", "-lock-timeout=60s"],
                            workdir,
                            DESTROY_TIMEOUT,
                        )
                        message += "\n[Cleanup done: partially created resources were removed.]"
                    else:
                        message += "\n[Nothing was created in AWS, so no cleanup was needed.]"
                except Exception as cleanup_exc:
                    message += (
                        "\n[Cleanup FAILED - check the AWS console for leftover resources: "
                        f"{str(cleanup_exc)[-300:]}]"
                    )
            dep.deployment_status = DeploymentStatus.failed
            dep.error_message = message[-2000:]
            req.status = RequestStatus.failed

        req.updated_at = _now()
        db.commit()
    finally:
        db.close()
        _release(request_id)


def run_destroy(request_id: int):
    """Background job: terraform destroy for one request."""
    db = SessionLocal()
    try:
        dep = db.query(Deployment).filter(Deployment.request_id == request_id).first()
        if not dep or dep.deployment_status == DeploymentStatus.destroyed:
            return
        try:
            workdir = workdir_for(request_id)
            if not workdir.exists():
                raise RuntimeError("Working folder for this request was not found.")
            _terraform(["destroy", "-auto-approve", "-input=false", "-no-color", "-lock-timeout=60s"], workdir, DESTROY_TIMEOUT)
            dep.deployment_status = DeploymentStatus.destroyed
            dep.destroyed_at = _now()
            dep.error_message = None
            req = db.get(ResourceRequest, request_id)
            if req:
                req.status = RequestStatus.destroyed
                req.updated_at = _now()
        except Exception as exc:
            dep.error_message = f"Destroy failed: {str(exc)[-1800:]}"
        db.commit()
    finally:
        db.close()
        _release(request_id)


def check_expired():
    """Destroy every provisioned instance that has outlived its time limit."""
    db = SessionLocal()
    try:
        deps = (
            db.query(Deployment)
            .filter(Deployment.deployment_status == DeploymentStatus.provisioned)
            .all()
        )
        due = [d.request_id for d in deps if expires_at(d) and expires_at(d) <= _now()]
    finally:
        db.close()

    for request_id in due:
        if try_start(request_id):  # skips requests already being handled
            run_destroy(request_id)  # releases the slot itself


_scheduler_started = False


def start_scheduler():
    """Start the background loop once per backend process."""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def loop():
        while True:
            try:
                check_expired()
            except Exception:
                pass  # never let the loop die
            time.sleep(CHECK_EVERY_SECONDS)

    threading.Thread(target=loop, name="auto-destroy", daemon=True).start()


def recover_stuck():
    """Run once at startup. Nothing can be running yet, so any request still
    marked 'provisioning' was interrupted by a restart: mark it failed so the
    admin can press Retry (Terraform continues from the saved state)."""
    db = SessionLocal()
    try:
        stuck = (
            db.query(ResourceRequest)
            .filter(ResourceRequest.status == RequestStatus.provisioning)
            .all()
        )
        for req in stuck:
            req.status = RequestStatus.failed
            req.updated_at = _now()
            dep = req.deployment
            if dep:
                dep.deployment_status = DeploymentStatus.failed
                dep.error_message = (
                    "The backend restarted while this request was provisioning. "
                    "Press Retry - Terraform will continue from the saved state."
                )
        if stuck:
            db.commit()
        return len(stuck)
    finally:
        db.close()