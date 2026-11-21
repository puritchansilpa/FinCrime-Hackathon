"""[Workstream A] Resolve an alert to the customer (SOP principles 2-4).

STUB from kickoff: link resolution comes in A2, search in A3, grouping in A4,
the full Person in A6. Until then no customer is resolved.
"""
from .models import Resolution


def resolve(alert: dict, data) -> Resolution:
    return Resolution(alert_id=alert["alert_id"], persons=[], path=["(resolver not built yet)"])
