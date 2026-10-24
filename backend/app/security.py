"""Day 28: rule-based security validation.

The check reads the Terraform template that will really be deployed
(terraform/main.tf) and the request itself, then returns a score from
0 to 100 with a list of findings. It does not call AWS.
"""
import re
from pathlib import Path

from app.terraform_runner import TEMPLATE_DIR

# Must match the allowed_cidr value that terraform_runner writes into
# terraform.tfvars. Empty = SSH (port 22) is closed.
SSH_ALLOWED_CIDR = ""

# Ports that are acceptable to open to the internet for a web server.
WEB_PORTS = {80, 443}
RISKY_PORTS = {
    22: "SSH",
    3389: "RDP",
    3306: "MySQL",
    5432: "PostgreSQL",
    27017: "MongoDB",
    6379: "Redis",
}
LONG_REQUEST_HOURS = 168  # more than 7 days


def _read_template() -> str:
    try:
        return (Path(TEMPLATE_DIR) / "main.tf").read_text(encoding="utf-8")
    except OSError:
        return ""


def _static_ingress_rules(tf: str):
    """Return [(from_port, to_port, [cidrs])] for plain ingress blocks."""
    rules = []
    for block in re.findall(r"\bingress\s*\{(.*?)\n\s*\}", tf, flags=re.S):
        fp = re.search(r"from_port\s*=\s*(\d+)", block)
        tp = re.search(r"to_port\s*=\s*(\d+)", block)
        cidrs = re.findall(r'"([0-9./]+)"', block)
        if fp and tp:
            rules.append((int(fp.group(1)), int(tp.group(1)), cidrs))
    return rules


def _finding(check, status, title, detail, points=0):
    # status: pass | warn | fail | info
    return {
        "check": check,
        "status": status,
        "title": title,
        "detail": detail,
        "points": points,
    }


def validate(duration_hours, purpose, instance_type=None) -> dict:
    tf = _read_template()
    findings = []

    if not tf:
        findings.append(
            _finding("template", "warn", "Terraform template not found",
                     "The configuration could not be checked.", 15)
        )

    # --- 1. Public access -------------------------------------------------
    rules = _static_ingress_rules(tf)
    world_ports = set()
    for fp, tp, cidrs in rules:
        if "0.0.0.0/0" in cidrs:
            world_ports.update(range(fp, tp + 1) if tp - fp < 100 else [fp, tp])
    if not rules and tf:
        findings.append(_finding("public_access", "pass", "No public inbound ports",
                                 "No inbound rule is open to the internet."))
    elif world_ports <= WEB_PORTS and world_ports:
        findings.append(_finding(
            "public_access", "warn", "Web port open to the internet",
            f"Port(s) {', '.join(str(p) for p in sorted(world_ports))} are open to 0.0.0.0/0. "
            "This is normal for a web server but makes the instance publicly reachable.",
            5))
    elif world_ports - WEB_PORTS:
        extra = sorted(world_ports - WEB_PORTS)
        shown = ", ".join(str(p) for p in extra[:6])
        findings.append(_finding(
            "public_access", "fail", "Sensitive ports open to the internet",
            f"Port(s) {shown} are open to 0.0.0.0/0.", 30))

    # --- 2. SSH exposure --------------------------------------------------
    ssh_in_static = any(fp <= 22 <= tp and "0.0.0.0/0" in c for fp, tp, c in rules)
    if ssh_in_static or SSH_ALLOWED_CIDR == "0.0.0.0/0":
        findings.append(_finding("ssh", "fail", "SSH open to the whole internet",
                                 "Port 22 accepts connections from anywhere.", 40))
    elif SSH_ALLOWED_CIDR:
        findings.append(_finding("ssh", "warn", "SSH limited to one IP range",
                                 f"Port 22 is open only to {SSH_ALLOWED_CIDR}.", 5))
    else:
        findings.append(_finding("ssh", "pass", "SSH is closed",
                                 "Port 22 is not opened, so nobody can log in over SSH."))

    # --- 3. Required ports only ------------------------------------------
    opened = sorted({p for fp, tp, _ in rules for p in ([fp] if fp == tp else [fp, tp])})
    risky = [f"{p} ({RISKY_PORTS[p]})" for p in opened if p in RISKY_PORTS]
    if risky:
        findings.append(_finding("ports", "fail", "Risky ports in the rules",
                                 "Found: " + ", ".join(risky) + ".", 20))
    else:
        findings.append(_finding(
            "ports", "pass", "Only required ports",
            "Open inbound ports: " + (", ".join(str(p) for p in opened) or "none")
            + ". Nothing beyond what a web server needs."))

    # --- 4. Basic IAM / instance settings --------------------------------
    if "iam_instance_profile" in tf:
        findings.append(_finding("iam", "warn", "Instance has an IAM role",
                                 "The server could call AWS APIs. Review the role.", 10))
    else:
        findings.append(_finding("iam", "pass", "No IAM role on the instance",
                                 "The instance has no AWS permissions of its own."))

    if re.search(r"encrypted\s*=\s*true", tf):
        findings.append(_finding("encryption", "pass", "Disk is encrypted",
                                 "The root volume is encrypted at rest."))
    else:
        findings.append(_finding("encryption", "warn", "Disk is not encrypted",
                                 "The root volume is not encrypted at rest.", 10))

    if re.search(r'http_tokens\s*=\s*"required"', tf):
        findings.append(_finding("imds", "pass", "Metadata service v2 required",
                                 "IMDSv2 is enforced, which blocks a common credential-theft path."))
    else:
        findings.append(_finding("imds", "warn", "Metadata service v1 allowed",
                                 "IMDSv2 is not enforced on the instance.", 10))

    findings.append(_finding(
        "portal_iam", "info", "Portal IAM user",
        "Terraform runs as an IAM user with EC2 permissions. The admin should keep "
        "its keys private and rotate them regularly."))

    # --- 5. Request-based checks -----------------------------------------
    if duration_hours and duration_hours > LONG_REQUEST_HOURS:
        findings.append(_finding("duration", "warn", "Long-running instance",
                                 "The instance stays exposed for more than 7 days.", 10))
    if not purpose or len(purpose.strip()) < 10:
        findings.append(_finding("purpose", "warn", "No clear purpose given",
                                 "The admin cannot judge the need without a purpose.", 5))

    score = max(0, 100 - sum(f["points"] for f in findings))
    if score >= 85:
        level = "Low risk"
    elif score >= 60:
        level = "Medium risk"
    else:
        level = "High risk"

    return {"score": score, "level": level, "findings": findings}