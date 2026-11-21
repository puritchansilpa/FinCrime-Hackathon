"""Shared contract between Workstream A (customer side) and Workstream B (hit side).

Agreed at kickoff, then frozen: change only by agreement, in its own small PR.
See PLAN.md section 6.1.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

# --- Decisions and the reason codes that belong to each (POLICY.md) -------------

DIFFERENT_ENTITY = "DIFFERENT_ENTITY"
SAME_ENTITY = "SAME_ENTITY"
REVIEW = "REVIEW"

REASON_CODES = {
    DIFFERENT_ENTITY: (
        "TEMPORAL_IMPOSSIBILITY",
        "DOB_MISMATCH",
        "LOCATION_MISMATCH",
        "NAME_MISMATCH_VERIFIED",
        "ENTITY_TYPE_MISMATCH",
        "DECEASED",
    ),
    SAME_ENTITY: (
        "NAME_DOB_LOCATION_MATCH",
        "NAME_DOB_MATCH",
        "NAME_LOCATION_MATCH",
    ),
    REVIEW: (
        "INSUFFICIENT_DATA",
        "AMBIGUOUS_CUSTOMER_RECORD",
    ),
}

AMBIGUOUS = "AMBIGUOUS"  # customer_record_id when more than one person fits


@dataclass(frozen=True)
class PartialDate:            # unknown parts stay None ("unknown stays unknown")
    year: Optional[int]
    month: Optional[int] = None
    day: Optional[int] = None


@dataclass(frozen=True)
class Fact:                   # every fact remembers where it came from, for evidence
    value: Any                # str name | PartialDate | canonical country name | frozenset of years
    source_id: str            # exact record ID: "CUS-…", "KYC-…", "NOTE-…", "SR-…", "H-…"
    origin: str = ""          # e.g. "verified_kyc", "verified_note", "record", "residence_note",
                              #      "dobs", "profile_age", "search"


@dataclass
class Person:                 # one real person/company = a cluster of customer records  [built by A]
    record_ids: list          # sorted CUS-… IDs
    entity_type: str          # "Individual" | "Company"
    verified_name: Optional[Fact] = None   # latest APPROVED check (KYC table or kyc note)
    verified_dob: Optional[Fact] = None    # same check; for companies = incorporation date
    declared_names: list = field(default_factory=list)  # Facts: full/preferred/login names
    declared_dobs: list = field(default_factory=list)   # Facts: dob on the records
    countries: list = field(default_factory=list)       # Facts: residence, nationality, doc country,
                                                        #        residence notes


@dataclass
class Resolution:             # [built by A]
    alert_id: str
    persons: list             # [] = no customer found, [p] = resolved, [p, q, …] = ambiguous
    path: list                # human-readable trace, like the labels' `path` column


@dataclass
class HitProfile:             # [built by B]
    hit_id: str
    alert_id: str
    entity_type: str
    names: list               # Facts: name + every alias, source_id = hit_id
    dob_candidates: list      # Facts with PartialDate or frozenset-of-years values
    dob_origin: Optional[str] # "dobs" | "profile_age" | "search" | None
    earliest_report: Optional[Fact] = None   # PartialDate of the earliest "According to …; <date>:" line
    death_date: Optional[Fact] = None
    countries: list = field(default_factory=list)


@dataclass
class Decision:               # [built by B]
    hit_id: str
    alert_id: str
    decision: str             # DIFFERENT_ENTITY | SAME_ENTITY | REVIEW
    reason_code: str
    customer_record_id: Optional[str]   # CUS-… | "AMBIGUOUS" | None
    reason: str
    evidence: list            # sorted IDs that decided it

    def to_output(self) -> dict:
        """One output line, with the field order the brief lists."""
        return {
            "hit_id": self.hit_id,
            "alert_id": self.alert_id,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "customer_record_id": self.customer_record_id,
            "reason": self.reason,
            "evidence": sorted(set(self.evidence)),
        }
