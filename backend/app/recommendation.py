"""Rule-based EC2 recommendation (Day 26). No AI: a simple table anyone can read.

    low    -> t3.micro
    medium -> t3.small
    high   -> c7i-flex.large (4 GiB; t3.medium is not allowed on an AWS free-plan account)
"""
from app.pricing import INSTANCE_TYPES, estimate, HOURS_PER_MONTH

RULES = {
    "low": (
        "t3.micro",
        "Light usage such as testing, learning or small scripts runs fine on 1 GiB of memory.",
    ),
    "medium": (
        "t3.small",
        "Small apps and development environments need more memory, so 2 GiB is a safer fit.",
    ),
    "high": (
        "c7i-flex.large",
        "Heavier workloads need room to grow, so 4 GiB of memory is recommended.",
    ),
}
DEFAULT_WORKLOAD = "low"


def recommended_type(workload: str) -> str:
    return RULES.get(workload, RULES[DEFAULT_WORKLOAD])[0]


def recommend(workload: str, storage_gb: int = 20) -> dict:
    """The recommended instance with its specs and an estimated monthly cost."""
    instance_type, reason = RULES.get(workload, RULES[DEFAULT_WORKLOAD])
    spec = INSTANCE_TYPES[instance_type]
    month = estimate(storage_gb, int(HOURS_PER_MONTH), instance_type)
    return {
        "workload": workload,
        "instance_type": instance_type,
        "vcpu": spec["vcpu"],
        "memory_gb": spec["memory_gb"],
        "reason": reason,
        "monthly_usd": float(month["usd"]),
        "monthly_inr": float(month["inr"]),
    }