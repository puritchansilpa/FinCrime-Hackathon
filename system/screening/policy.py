"""[Workstream B] SOP decision rules.

STUB from kickoff: B replaces decide() with the real rules (task B4).
Until then every hit is REVIEW / INSUFFICIENT_DATA, which scores 0.
"""
from .models import AMBIGUOUS, REVIEW, Decision


def decide(person, hp, alert) -> Decision:
    """Decide one hit against one resolved person (or None if no customer was found)."""
    return Decision(
        hit_id=hp.hit_id,
        alert_id=hp.alert_id,
        decision=REVIEW,
        reason_code="INSUFFICIENT_DATA",
        customer_record_id=person.record_ids[0] if person and person.record_ids else None,
        reason="No rule has been applied to this hit yet, so it is left for review.",
        evidence=[],
    )


def combine(decisions: list, hp) -> Decision:
    """Merge the per-person decisions for one hit.

    One person: that decision. Several persons: if they all agree, keep the decision
    with customer_record_id AMBIGUOUS; otherwise REVIEW / AMBIGUOUS_CUSTOMER_RECORD.
    """
    if len(decisions) == 1:
        return decisions[0]
    first = decisions[0]
    if all(d.decision == first.decision and d.reason_code == first.reason_code for d in decisions):
        evidence = sorted({e for d in decisions for e in d.evidence})
        return Decision(first.hit_id, first.alert_id, first.decision, first.reason_code,
                        AMBIGUOUS, first.reason, evidence)
    return Decision(
        hit_id=hp.hit_id,
        alert_id=hp.alert_id,
        decision=REVIEW,
        reason_code="AMBIGUOUS_CUSTOMER_RECORD",
        customer_record_id=AMBIGUOUS,
        reason="More than one customer fits this alert and they lead to different decisions.",
        evidence=sorted({e for d in decisions for e in d.evidence}),
    )
