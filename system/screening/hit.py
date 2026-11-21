"""[Workstream B] Build a HitProfile from a hit row.

STUB from kickoff: B replaces this with the real version (task B3).
"""
from .models import Fact, HitProfile


def build_hit(hit_row: dict, data) -> HitProfile:
    hit_id = hit_row["hit_id"]
    names = [Fact(hit_row["name"], hit_id, "name")] if hit_row.get("name") else []
    return HitProfile(
        hit_id=hit_id,
        alert_id=hit_row.get("alert_id") or "",
        entity_type=hit_row.get("entity_type") or "",
        names=names,
        dob_candidates=[],
        dob_origin=None,
    )
