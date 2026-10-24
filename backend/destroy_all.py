"""Safety net: destroy every AWS resource this portal created.

    python destroy_all.py          -> only LISTS what would be destroyed (safe)
    python destroy_all.py --yes    -> really destroys it

Run it from the backend folder with the venv active. It looks at every
terraform_runs/request-<id> folder, destroys what is still in its state, and
marks the request as destroyed in the database.
"""
import sys
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import Deployment, DeploymentStatus, RequestStatus, ResourceRequest
from app.terraform_runner import RUNS_DIR, _terraform


def resources_in(workdir):
    """Names of the resources Terraform still tracks in this folder."""
    if not (workdir / "terraform.tfstate").exists():
        return []
    try:
        out = _terraform(["state", "list", "-no-color"], workdir, 120).stdout
    except Exception as exc:
        print(f"   could not read state: {str(exc)[-200:]}")
        return None  # unknown
    return [line.strip() for line in out.splitlines() if line.strip()]


def main():
    really = "--yes" in sys.argv
    if not RUNS_DIR.exists():
        print("No terraform_runs folder: nothing was ever provisioned.")
        return

    folders = sorted(p for p in RUNS_DIR.glob("request-*") if p.is_dir())
    problems = 0
    pending = 0
    db = SessionLocal()
    try:
        for folder in folders:
            request_id = int(folder.name.split("-")[1])
            found = resources_in(folder)
            if found is None:
                problems += 1
                print(f"[request {request_id}] UNKNOWN - check this one in the AWS console")
                continue
            if not found:
                print(f"[request {request_id}] nothing left to destroy")
                continue

            print(f"[request {request_id}] still has: {', '.join(found)}")
            pending += 1
            if not really:
                continue

            try:
                _terraform(
                    ["destroy", "-auto-approve", "-input=false", "-no-color", "-lock-timeout=60s"],
                    folder,
                    900,
                )
                print("   destroyed")
            except Exception as exc:
                problems += 1
                print(f"   DESTROY FAILED: {str(exc)[-300:]}")
                continue

            dep = db.query(Deployment).filter(Deployment.request_id == request_id).first()
            req = db.get(ResourceRequest, request_id)
            if dep:
                dep.deployment_status = DeploymentStatus.destroyed
                dep.destroyed_at = datetime.now(timezone.utc)
                dep.error_message = None
            if req:
                req.status = RequestStatus.destroyed
            db.commit()
    finally:
        db.close()

    if not really and pending == 0 and not problems:
        print("\nNothing to destroy.")
    elif not really:
        print("\nDry run only. Run 'python destroy_all.py --yes' to destroy the resources listed above.")
    elif problems:
        print(f"\nFinished with {problems} problem(s). Check the AWS console (EC2, Mumbai).")
    else:
        print("\nAll done. Also glance at the EC2 console to be sure.")


if __name__ == "__main__":
    main()
