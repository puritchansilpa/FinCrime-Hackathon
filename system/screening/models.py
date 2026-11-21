"""Shared contract between Workstream A (customer side) and B (hit side + decision).

Change this file only by agreement between both workstreams (PLAN.md section 6.1).
Python 3.9 compatible: use Optional/List, not `X | Y`.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional

# Decisions (both spellings are part of the contract: B uses DIFFERENT/SAME, A uses the long names)
DIFFERENT_ENTITY = DIFFERENT = "DIFFERENT_ENTITY"
SAME_ENTITY = SAME = "SAME_ENTITY"
REVIEW = "REVIEW"

# Reason codes (POLICY.md)
TEMPORAL_IMPOSSIBILITY = "TEMPORAL_IMPOSSIBILITY"
DOB_MISMATCH = "DOB_MISMATCH"
LOCATION_MISMATCH = "LOCATION_MISMATCH"
NAME_MISMATCH_VERIFIED = "NAME_MISMATCH_VERIFIED"
ENTITY_TYPE_MISMATCH = "ENTITY_TYPE_MISMATCH"
DECEASED = "DECEASED"
NAME_DOB_LOCATION_MATCH = "NAME_DOB_LOCATION_MATCH"
NAME_DOB_MATCH = "NAME_DOB_MATCH"
NAME_LOCATION_MATCH = "NAME_LOCATION_MATCH"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
AMBIGUOUS_CUSTOMER_RECORD = "AMBIGUOUS_CUSTOMER_RECORD"

# The reason codes that belong to each decision (POLICY.md; validate.py checks this)
REASON_CODES = {
    DIFFERENT_ENTITY: (TEMPORAL_IMPOSSIBILITY, DOB_MISMATCH, LOCATION_MISMATCH,
                       NAME_MISMATCH_VERIFIED, ENTITY_TYPE_MISMATCH, DECEASED),
    SAME_ENTITY: (NAME_DOB_LOCATION_MATCH, NAME_DOB_MATCH, NAME_LOCATION_MATCH),
    REVIEW: (INSUFFICIENT_DATA, AMBIGUOUS_CUSTOMER_RECORD),
}

AMBIGUOUS = "AMBIGUOUS"  # customer_record_id when more than one person fits

INDIVIDUAL = "Individual"
COMPANY = "Company"


@dataclass(frozen=True)
class PartialDate:
    """A date where unknown parts stay None ("unknown stays unknown")."""
    year: Optional[int]
    month: Optional[int] = None
    day: Optional[int] = None

    def iso(self) -> str:
        if self.year is None:
            return ""
        s = f"{self.year:04d}"
        if self.month is not None:
            s += f"-{self.month:02d}"
            if self.day is not None:
                s += f"-{self.day:02d}"
        return s


@dataclass(frozen=True)
class Fact:
    """A value plus the exact record ID it came from, so it can be cited as evidence."""
    value: Any          # str name | PartialDate | canonical country name | frozenset of years
    source_id: str      # "CUS-…", "KYC-…", "NOTE-…", "SR-…", "H-…"
    origin: str = ""    # "verified_kyc", "verified_note", "record", "residence_note",
                        # "dobs", "profile_age", "search", "report", "name", "alias", …


@dataclass
class Person:
    """One real person or company: a cluster of customer records. Built by A."""
    record_ids: List[str]                                  # sorted CUS-… IDs
    entity_type: str                                       # INDIVIDUAL | COMPANY
    verified_name: Optional[Fact] = None                   # latest APPROVED check (KYC table or kyc note)
    verified_dob: Optional[Fact] = None                    # same check; companies: incorporation date
    declared_names: List[Fact] = field(default_factory=list)  # full/preferred/login names on records
    declared_dobs: List[Fact] = field(default_factory=list)   # dob on the records (PartialDate values)
    countries: List[Fact] = field(default_factory=list)       # canonical country names, any source


@dataclass
class Resolution:
    """Who the alert's customer is. Built by A."""
    alert_id: str
    persons: List[Person]   # [] none found · [p] resolved · [p, q, …] several people fit
    path: List[str] = field(default_factory=list)  # human-readable trace, like the labels' `path`


@dataclass
class HitProfile:
    """Who the listed person is. Built by B."""
    hit_id: str
    alert_id: str
    entity_type: str
    names: List[Fact]                                  # name + every alias (source_id = hit_id)
    dob_candidates: List[Fact] = field(default_factory=list)  # PartialDate or frozenset-of-years values
    dob_origin: Optional[str] = None                   # "dobs" | "profile_age" | "search" | None
    earliest_report: Optional[Fact] = None             # PartialDate of the earliest dated report
    death_date: Optional[Fact] = None                  # PartialDate
    countries: List[Fact] = field(default_factory=list)  # canonical country names tied to the hit


@dataclass
class Decision:
    """One output line. Built by B (policy.decide / policy.combine)."""
    hit_id: str
    alert_id: str
    decision: str
    reason_code: str
    customer_record_id: Optional[str]   # CUS-… | AMBIGUOUS | None
    reason: str
    evidence: List[str]                 # sorted IDs of the records that decided it

    def to_output(self) -> dict:
        """One output line, in the field order the brief lists."""
        return {
            "hit_id": self.hit_id,
            "alert_id": self.alert_id,
            "decision": self.decision,
            "reason_code": self.reason_code,
            "customer_record_id": self.customer_record_id,
            "reason": self.reason,
            "evidence": sorted(set(self.evidence)),
        }

    to_json = to_output
