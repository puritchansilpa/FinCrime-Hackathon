"""Decisions (POLICY.md principles 6-7, 9).  [Workstream B]

decide(person, hit_profile, alert, variants) -> Decision
combine(decisions, hit_profile, persons)      -> Decision   (several people fit the alert)

Clear only on a contradiction, confirm only on agreement, otherwise REVIEW.
Contradictions are checked in a fixed order (type, deceased, temporal, DOB, location, name);
the first gives the reason code, and every one found is stated in the reason and cited.
"""

import calendar
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from . import explain as ex
from .models import (
    AMBIGUOUS, AMBIGUOUS_CUSTOMER_RECORD, COMPANY, DECEASED, DIFFERENT, DOB_MISMATCH,
    ENTITY_TYPE_MISMATCH, INDIVIDUAL, INSUFFICIENT_DATA, LOCATION_MISMATCH, NAME_DOB_LOCATION_MATCH,
    NAME_DOB_MATCH, NAME_LOCATION_MATCH, NAME_MISMATCH_VERIFIED, REVIEW, SAME, TEMPORAL_IMPOSSIBILITY,
    Decision, Fact, HitProfile, PartialDate, Person,
)
from .names import Variants, names_agree, real_parts
from .normalize import age_at, parse_date, screened_details, to_country

AGREE, CONTRADICT, NEITHER, UNKNOWN = "agree", "contradict", "neither", "unknown"
MIN_AGE = 16


# ---------------------------------------------------------------------------
# Date comparisons (principles 6 and 7)
# ---------------------------------------------------------------------------

def dob_agrees(cust: PartialDate, hit) -> bool:
    """Customer's birth year is one of the hit's possible years and every part both give is equal."""
    if cust is None or cust.year is None:
        return False
    if isinstance(hit, (set, frozenset)):
        return cust.year in hit
    if hit is None or hit.year is None or cust.year != hit.year:
        return False
    if cust.month is not None and hit.month is not None and cust.month != hit.month:
        return False
    if cust.day is not None and hit.day is not None and cust.day != hit.day:
        return False
    return True


def dob_contradicts(cust: PartialDate, hit) -> bool:
    """Birth year more than 1 year outside, or same year with a differing month (or day)."""
    if cust is None or cust.year is None:
        return False
    if isinstance(hit, (set, frozenset)):
        return bool(hit) and (cust.year < min(hit) - 1 or cust.year > max(hit) + 1)
    if hit is None or hit.year is None:
        return False
    if abs(cust.year - hit.year) > 1:
        return True
    if cust.year == hit.year and cust.month is not None and hit.month is not None:
        if cust.month != hit.month:
            return True
        if cust.day is not None and hit.day is not None and cust.day != hit.day:
            return True
    return False


def _earliest(d: PartialDate) -> Tuple[int, int, int]:
    return (d.year, d.month or 1, d.day or 1)


def _latest(d: PartialDate) -> Tuple[int, int, int]:
    m = d.month or 12
    return (d.year, m, d.day or calendar.monthrange(d.year, m)[1])


# ---------------------------------------------------------------------------
# The customer as the policy sees it
# ---------------------------------------------------------------------------

@dataclass
class CustomerView:
    record_ids: List[str]
    entity_type: Optional[str]
    verified_name: Optional[Fact]
    name_facts: List[Fact]          # names used for agreement (verified outranks declared)
    dob_facts: List[Fact]           # verified DOB, else declared ones
    countries: List[Fact]
    screened_at: Optional[PartialDate]
    resolved: bool = True
    unresolved: List[str] = field(default_factory=list)   # customer places with no known country


def customer_view(person: Optional[Person], alert: dict) -> CustomerView:
    aid = alert.get("alert_id") or ""
    screened_at = parse_date(alert.get("screened_at"))
    sc = screened_details(alert)
    if person is None:
        name = sc["name"]
        dob = parse_date(sc["dob"])
        c = to_country(sc["country"])
        return CustomerView(
            record_ids=[], entity_type=_kind(sc["entity_type"]), verified_name=None,
            name_facts=[Fact(name, aid, "screened")] if name else [],
            dob_facts=[Fact(dob, aid, "screened")] if dob else [],
            countries=[Fact(c, aid, "screened")] if c else [],
            screened_at=screened_at, resolved=False,
        )
    if person.verified_name is not None:
        names = [person.verified_name]
    else:
        names = list(person.declared_names)
        if sc["name"]:
            names.append(Fact(sc["name"], aid, "screened"))
    if person.verified_dob is not None and person.verified_dob.value is not None:
        dobs = [person.verified_dob]
    else:
        dobs, seen = [], set()
        for f in person.declared_dobs:
            if f.value is not None and f.value not in seen:
                seen.add(f.value)
                dobs.append(f)
    return CustomerView(
        record_ids=sorted(person.record_ids), entity_type=_kind(person.entity_type),
        verified_name=person.verified_name, name_facts=names, dob_facts=dobs,
        countries=[f for f in person.countries if f.value], screened_at=screened_at,
        unresolved=list(getattr(person, "unresolved_places", None) or []),
    )


def _kind(v) -> Optional[str]:
    v = (v or "").strip().lower()
    if v in ("individual", "person", "natural person"):
        return INDIVIDUAL
    if v in ("company", "organisation", "organization", "entity", "corporation", "business"):
        return COMPANY
    return None


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------

@dataclass
class NameResult:
    state: str
    cust: Optional[Fact] = None
    hit: Optional[Fact] = None


def assess_name(cv: CustomerView, hp: HitProfile, variants: Optional[Variants]) -> NameResult:
    company = cv.entity_type == COMPANY
    usable = [f for f in cv.name_facts if f.value and
              len(real_parts(f.value, company, variants)) >= (1 if company else 2)]
    # A hit name made only of placeholders ('N/A', 'UNKNOWN') is no name at all: it can
    # neither agree nor contradict (ADV-H-110).
    hit_names = [hf for hf in hp.names if hf.value and real_parts(hf.value, company, variants)]
    if not usable or not hit_names:
        return NameResult(UNKNOWN)
    for cf in usable:
        for hf in hit_names:
            if names_agree(cf.value, hf.value, variants, company):
                return NameResult(AGREE, cf, hf)
    if cv.verified_name is not None and cv.verified_name in usable:
        return NameResult(CONTRADICT, cv.verified_name, hit_names[0])
    return NameResult(NEITHER)          # declared names only: no agreement, but no contradiction


@dataclass
class DobResult:
    state: str
    cust: Optional[Fact] = None
    hit: List[Fact] = field(default_factory=list)


def assess_dob(cv: CustomerView, hp: HitProfile) -> DobResult:
    cust = [f for f in cv.dob_facts if f.value is not None and f.value.year is not None]
    cands = [c for c in hp.dob_candidates if c.value is not None]
    if not cust or not cands:
        return DobResult(UNKNOWN)
    for cf in cust:
        agreeing = [h for h in cands if dob_agrees(cf.value, h.value)]
        if agreeing:
            return DobResult(AGREE, cf, agreeing)
    if all(dob_contradicts(cf.value, h.value) for cf in cust for h in cands):
        return DobResult(CONTRADICT, cust[0], cands)
    return DobResult(NEITHER, cust[0], cands)


@dataclass
class CountryResult:
    state: str
    shared: List[str] = field(default_factory=list)
    cust: List[str] = field(default_factory=list)
    hit: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)   # places on either side with no known country


def assess_countries(cv: CustomerView, hp: HitProfile) -> CountryResult:
    """AGREE on a shared country. CONTRADICT only when every country tied to the customer
    differs from every country tied to the hit, which can only be known when no place on
    either side is unresolved; otherwise UNKNOWN (an unmapped place is never a mismatch)."""
    cust = sorted({f.value for f in cv.countries})
    hit = sorted({f.value for f in hp.countries})
    unresolved = sorted(set(cv.unresolved) | set(getattr(hp, "unresolved_places", None) or []))
    if not cust or not hit:
        return CountryResult(UNKNOWN, cust=cust, hit=hit, unresolved=unresolved)
    shared = sorted(set(cust) & set(hit))
    if shared:
        src = sorted({f.source_id for f in cv.countries if f.value in shared})
        return CountryResult(AGREE, shared, cust, hit, src, unresolved)
    if unresolved:
        return CountryResult(UNKNOWN, [], cust, hit, [], unresolved)
    src = sorted({f.source_id for f in cv.countries})
    return CountryResult(CONTRADICT, [], cust, hit, src)


def assess_temporal(cv: CustomerView, hp: HitProfile) -> Optional[Tuple[Fact, Optional[int], PartialDate]]:
    """(customer dob fact, max age or None for companies, report date) when time rules it out."""
    if hp.earliest_report is None:
        return None
    report = hp.earliest_report.value
    dobs = [f for f in cv.dob_facts if f.value is not None and f.value.year is not None]
    if not dobs:
        return None
    if cv.entity_type == COMPANY:
        if all(_earliest(f.value) > _earliest(report) for f in dobs):
            return dobs[0], None, report
        return None
    ages = [(age_at(f.value, report), f) for f in dobs]
    if all(a is not None and a < MIN_AGE for a, _ in ages):
        age, f = max(ages, key=lambda x: x[0])
        return f, age, report
    return None


def assess_deceased(cv: CustomerView, hp: HitProfile) -> Optional[PartialDate]:
    if hp.death_date is None or cv.screened_at is None:
        return None
    death = hp.death_date.value
    if death is not None and death.year is not None and _latest(death) < _earliest(cv.screened_at):
        return death
    return None


# ---------------------------------------------------------------------------
# decide / combine
# ---------------------------------------------------------------------------

def _record_id(cv: CustomerView) -> Optional[str]:
    return cv.record_ids[0] if cv.record_ids else None


def _src(f: Optional[Fact], cv: CustomerView) -> List[str]:
    """Citable source of a customer fact (screened alert details are not records)."""
    if f is None or f.origin == "screened":
        return []
    return [f.source_id]


def no_customer(hp: HitProfile, alert: dict) -> Decision:
    """No customer record fits the alert. The screened details alone (which can be nicknames,
    typos or login names) are not enough to clear or confirm, so a person looks at it."""
    return Decision(hp.hit_id, hp.alert_id, REVIEW, INSUFFICIENT_DATA, None,
                    ex.s_no_customer(alert.get("alert_id") or hp.alert_id) +
                    " Nothing verified can be compared with the hit, so it needs review.", [])


def decide(person: Optional[Person], hp: HitProfile, alert: dict,
           variants: Optional[Variants] = None) -> Decision:
    if person is None:
        return no_customer(hp, alert)
    cv = customer_view(person, alert)
    company = cv.entity_type == COMPANY
    hit_company = hp.entity_type == COMPANY
    name = assess_name(cv, hp, variants)
    dob = assess_dob(cv, hp)
    loc = assess_countries(cv, hp)

    found: List[Tuple[str, str, List[str]]] = []   # (code, sentence, evidence)

    # 1. Type
    if cv.entity_type in (INDIVIDUAL, COMPANY) and hp.entity_type in (INDIVIDUAL, COMPANY) \
            and cv.entity_type != hp.entity_type:
        found.append((ENTITY_TYPE_MISMATCH, ex.s_type(cv.entity_type, hp.entity_type, _record_id(cv)),
                      list(cv.record_ids)))
    # 2. Deceased before screening
    death = assess_deceased(cv, hp)
    if death is not None:
        found.append((DECEASED, ex.s_deceased(death, cv.screened_at), list(cv.record_ids[:1])))
    # 3. Time
    t = assess_temporal(cv, hp)
    if t is not None:
        f, age, report = t
        s = ex.s_temporal_company(f, report) if age is None else ex.s_temporal_person(f, age, report)
        found.append((TEMPORAL_IMPOSSIBILITY, s, _src(f, cv)))
    # 4. Date of birth
    if dob.state == CONTRADICT:
        sr = [c.source_id for c in dob.hit if c.origin == "search"]
        found.append((DOB_MISMATCH, ex.s_dob_mismatch(dob.cust, dob.hit, company), _src(dob.cust, cv) + sr))
    # 5. Location (not when name and date of birth agree)
    location_blocked = False
    if loc.state == CONTRADICT:
        if name.state == AGREE and dob.state == AGREE:
            location_blocked = True
        else:
            found.append((LOCATION_MISMATCH, ex.s_location_mismatch(loc.cust, loc.hit),
                          [s for s in loc.sources if not s.startswith("A-")]))
    # 6. Verified name
    if name.state == CONTRADICT:
        found.append((NAME_MISMATCH_VERIFIED,
                      ex.s_name_mismatch(name.cust, hp.names[0].value, len(hp.names) > 1),
                      _src(name.cust, cv)))

    if found:
        sentences = [s for _, s, _ in found][:3]
        if len(sentences) < 2:
            sentences.append(ex.s_cleared(company))
        evidence = sorted({e for _, _, ev in found for e in ev})
        return Decision(hp.hit_id, hp.alert_id, DIFFERENT, found[0][0], _record_id(cv),
                        " ".join(sentences[:4]), evidence)

    # Agreement. Like the practice labels, cite the shared countries' and the date of birth's
    # sources; the agreeing name itself is not cited.
    agree_ev = set()
    if loc.state == AGREE:
        agree_ev.update(s for s in loc.sources if not s.startswith("A-"))

    if location_blocked:
        ev = agree_ev | set(_src(dob.cust, cv)) | {c.source_id for c in dob.hit if c.origin == "search"}
        ev |= set(s for s in loc.sources if not s.startswith("A-"))
        reason = " ".join([ex.s_dob_agrees(dob.cust, dob.hit), ex.s_name_agrees(name.hit.value),
                           ex.s_location_exception(loc.cust, loc.hit)])
        return Decision(hp.hit_id, hp.alert_id, REVIEW, INSUFFICIENT_DATA, _record_id(cv), reason, sorted(ev))

    if not company and not hit_company and name.state == AGREE and dob.state == AGREE:
        ev = agree_ev | set(_src(dob.cust, cv)) | {c.source_id for c in dob.hit if c.origin == "search"}
        sentences = [ex.s_dob_agrees(dob.cust, dob.hit)]
        if loc.state == AGREE:
            sentences.append(ex.s_shared_countries(loc.shared))
        sentences.append(ex.s_name_agrees(name.hit.value))
        code = NAME_DOB_LOCATION_MATCH if loc.state == AGREE else NAME_DOB_MATCH
        return Decision(hp.hit_id, hp.alert_id, SAME, code, _record_id(cv),
                        " ".join(sentences[:4]), sorted(ev))

    if company and hit_company and name.state == AGREE and loc.state == AGREE:
        sentences = [ex.s_shared_countries(loc.shared), ex.s_name_agrees(name.hit.value)]
        return Decision(hp.hit_id, hp.alert_id, SAME, NAME_LOCATION_MATCH, _record_id(cv),
                        " ".join(sentences[:4]), sorted(agree_ev))

    # Review: nothing settles it
    sentences = []
    if loc.state == AGREE:
        sentences.append(ex.s_shared_countries(loc.shared))
    if name.state == AGREE:
        sentences.append(ex.s_name_agrees(name.hit.value))
    if loc.state == UNKNOWN and loc.unresolved and loc.cust and loc.hit:
        sentences.append(ex.s_unresolved_places(loc.unresolved))
    sentences.append(ex.s_review_tail(_missing(cv, name, dob, loc, company)))
    ev = sorted(agree_ev) or list(cv.record_ids[:1])
    return Decision(hp.hit_id, hp.alert_id, REVIEW, INSUFFICIENT_DATA, _record_id(cv),
                    " ".join(sentences[-4:]), ev)


def _missing(cv, name: NameResult, dob: DobResult, loc: CountryResult, company: bool) -> str:
    if name.state == UNKNOWN:
        return ("the customer's name has too few real parts to compare" if cv.name_facts else
                "the customer's name is not known")
    if name.state == NEITHER:
        return "the customer's names on record do not agree with the hit's names but are not verified"
    if company:
        return "the countries cannot be compared with it" if loc.state == UNKNOWN else \
            "the countries do not settle it"
    if dob.state == UNKNOWN:
        return "the date of birth cannot be compared with it"
    return "the dates of birth neither agree nor contradict each other"


def combine(decisions: Sequence[Decision], hp: HitProfile,
            persons: Optional[Sequence[Person]] = None) -> Decision:
    """Several people fit the alert: one decision if they all agree, else REVIEW AMBIGUOUS."""
    decisions = list(decisions)
    if len(decisions) == 1:
        return decisions[0]
    evidence = sorted({e for d in decisions for e in d.evidence})
    kinds = [d.decision for d in decisions]
    if len(set(kinds)) == 1:
        first = decisions[0]
        return Decision(hp.hit_id, hp.alert_id, first.decision, first.reason_code, AMBIGUOUS,
                        first.reason, evidence)
    groups = [sorted(p.record_ids) for p in persons] if persons else [[d.customer_record_id or "?"] for d in decisions]
    ev = sorted({r for g in groups for r in g} | set(evidence))
    labels = [f"{d.decision} for {', '.join(g)}" for d, g in zip(decisions, groups)]
    return Decision(hp.hit_id, hp.alert_id, REVIEW, AMBIGUOUS_CUSTOMER_RECORD, AMBIGUOUS,
                    ex.s_ambiguous(groups, labels), ev)


def decide_alert_hit(persons: Sequence[Person], hp: HitProfile, alert: dict,
                     variants: Optional[Variants] = None) -> Decision:
    """Convenience for the runner: decide for each person (or none) and combine."""
    if not persons:
        return decide(None, hp, alert, variants)
    return combine([decide(p, hp, alert, variants) for p in persons], hp, persons)
