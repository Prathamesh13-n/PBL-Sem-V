"""Approximate price estimates shown on the request form.

IMPORTANT: these rates are ESTIMATES. Check them against the AWS pricing page
for ap-south-1 (Mumbai) and edit the numbers below before the demo.
The real bill always comes from the AWS billing page.
"""
from decimal import Decimal

INSTANCE_USD_PER_HOUR = Decimal("0.0112")  # t3.micro (kept for reference)

# Estimated on-demand prices for ap-south-1 (Mumbai). Edit after checking the AWS pricing page.
INSTANCE_TYPES = {
    "t3.micro": {"usd_per_hour": Decimal("0.0112"), "vcpu": 2, "memory_gb": 1},
    "t3.small": {"usd_per_hour": Decimal("0.0224"), "vcpu": 2, "memory_gb": 2},
    # c7i-flex.large: price from aws-pricing.com (ap-south-1, Linux on-demand, 18 Oct 2026)
    "c7i-flex.large": {"usd_per_hour": Decimal("0.0848"), "vcpu": 2, "memory_gb": 4},
}
DEFAULT_INSTANCE_TYPE = "t3.micro"
STORAGE_USD_PER_GB_MONTH = Decimal("0.0912")  # gp3
PUBLIC_IP_USD_PER_HOUR = Decimal("0.005")
HOURS_PER_MONTH = Decimal("730")
USD_TO_INR = Decimal("88")

# (hours, label)
DURATION_OPTIONS = [
    (2, "2 hours"),
    (6, "6 hours"),
    (24, "1 day"),
    (72, "3 days"),
    (168, "7 days"),
]
ALLOWED_HOURS = {h for h, _ in DURATION_OPTIONS}  # the quick-pick cards
MIN_HOURS = 1
MAX_HOURS = 24 * 90  # custom end date: at most 90 days (admin approval is the safeguard)


def estimate(storage_gb: int, hours: int, instance_type: str = DEFAULT_INSTANCE_TYPE) -> dict:
    hours_d = Decimal(hours)
    per_hour = INSTANCE_TYPES.get(instance_type, INSTANCE_TYPES[DEFAULT_INSTANCE_TYPE])["usd_per_hour"]
    usd = (
        hours_d * per_hour
        + Decimal(storage_gb) * STORAGE_USD_PER_GB_MONTH * hours_d / HOURS_PER_MONTH
        + hours_d * PUBLIC_IP_USD_PER_HOUR
    )
    inr = usd * USD_TO_INR
    return {
        "usd": usd.quantize(Decimal("0.01")),
        "inr": inr.quantize(Decimal("0.01")),
    }


def options_with_prices(storage_gb: int, instance_type: str = DEFAULT_INSTANCE_TYPE) -> list:
    out = []
    for hours, label in DURATION_OPTIONS:
        e = estimate(storage_gb, hours, instance_type)
        out.append({"hours": hours, "label": label, "usd": float(e["usd"]), "inr": float(e["inr"])})
    return out