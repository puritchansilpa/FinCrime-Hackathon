"""What would settle each REVIEW, and which one an analyst should open first.

This module only annotates. policy.decide does not read it, and nothing here can
clear a hit or change a decision.

A task is a counterfactual against the rules already in policy.py: set the one
missing or conflicting fact to the values those rules distinguish, call decide()
for each value, and record the decision. The wording comes from those results.

Cost model, from CHALLENGE.md (row = right answer, column = what we said):

    right \\ said   DIFFERENT_ENTITY   SAME_ENTITY   REVIEW
    DIFFERENT_ENTITY         0              3           3
    SAME_ENTITY             60              0           2
    REVIEW                  60              2           0

Saying REVIEW costs 3 when the hit is really someone else, 2 when it is the
customer, and 0 when it really needs review. expected_cost_saved averages that
over the regions of the one next fact. Each region counts once. The 60 is the
penalty for a wrong clearance; this file never clears, so 60 is not a saving.

Band: date of birth and country vote. A verified name votes only when one of
those also agrees. A declared or screened name that agrees is a plain name
match (the alert was raised on the name) and does not vote. A verified name
with nothing else agreeing does not vote either.
"""
import json
import os

from . import hit as hit_mod
from . import policy
from .explain import fmt_date
from .models import COMPANY, DIFFERENT_ENTITY, REVIEW, SAME_ENTITY, Fact, HitProfile, PartialDate, Person
from .names import names_agree, real_parts
from .normalize import search_query, to_country

QUEUE_FILENAME = "review_queue.jsonl"

COST = {
    DIFFERENT_ENTITY: {DIFFERENT_ENTITY: 0, SAME_ENTITY: 3, REVIEW: 3},
    SAME_ENTITY: {DIFFERENT_ENTITY: 60, SAME_ENTITY: 0, REVIEW: 2},
    REVIEW: {DIFFERENT_ENTITY: 60, SAME_ENTITY: 2, REVIEW: 0},
}

_PRIORITY = {
    "customer_record": 0, "verified_dob": 1, "hit_dob": 2, "verified_name": 3,
    "hit_name": 4, "customer_country": 5, "hit_country": 6, "entity_type": 7,
}
_SENTINELS = ("Mongolia", "Paraguay", "Iceland", "Laos", "Bhutan", "Malta", "Fiji", "Nepal")
_DISAGREEING = ("Xylophone Quarantine", "Quincunx Vellum", "Brobdingnag Lilliput")


def saved_if_resolved(decision):
    return COST.get(decision, {}).get(REVIEW, 0)


def region_weight(_outcome):
    """One weight per region. Replace this to change the prior; decisions do not read it."""
    return 1


def expected_cost_saved(outcomes):
    if not outcomes:
        return 0.0
    weights = [region_weight(outcome) for outcome in outcomes]
    total = sum(weights) or 1
    saved = sum(weight * saved_if_resolved(outcome["decision"]) for weight, outcome in zip(weights, outcomes))
    return saved / total


def queue_path(output_path):
    folder = os.path.dirname(os.path.abspath(output_path))
    return os.path.join(folder, QUEUE_FILENAME)


def rank_queue(rows):
    ordered = sorted(rows, key=lambda row: (-float(row["expected_cost_saved"]), row["hit_id"]))
    ranked = []
    for index, row in enumerate(ordered, 1):
        item = dict(row)
        item["rank"] = index
        ranked.append(item)
    return ranked


def write_queue(rows, path):
    ranked = rank_queue(rows)
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in ranked:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return ranked


def fallback_row(official, why):
    task = {
        "fact": "review task", "side": "customer", "kind": "missing",
        "summary": why, "where": "",
        "outcomes": [{"when": "the hit cannot be assessed", "decision": REVIEW,
                      "reason_code": official.reason_code}],
    }
    return _row(official, "neutral", why, [], [], task, 0)


def build_task(official, resolution, hit_row, alert, data):
    """One review task, or None when the hit is not a REVIEW.

    Rebuilds the hit with main's build_hit and decide(). If that does not
    reproduce `official`, the probes are not trusted and the caller keeps the
    original decision.
    """
    if official is None or official.decision != REVIEW:
        return None
    alert = alert or {}
    variants = getattr(data, "variants", None) if data is not None else None
    hp = hit_mod.build_hit(hit_row, data)
    persons = list(resolution.persons) if resolution is not None and resolution.persons else []
    before = [_decide(person, hp, alert, variants).to_output() for person in (persons or [None])]
    combined = policy.combine(
        [_decide(person, hp, alert, variants) for person in (persons or [None])],
        hp, persons or None,
    )
    if combined.to_output() != official.to_output():
        raise RuntimeError("review task does not match the decision already made")
    if official.reason_code == "AMBIGUOUS_CUSTOMER_RECORD" and len(persons) > 1:
        row = _ambiguous_task(official, persons, hp, alert, variants)
    elif not persons:
        row = _missing_customer_task(official, hp, alert, variants)
    else:
        row = _best_fact_task(official, persons, hp, alert, variants, data)
    after = [_decide(person, hp, alert, variants).to_output() for person in (persons or [None])]
    if after != before:
        raise RuntimeError("review probes changed a decision")
    return row


def _decide(person, hp, alert, variants):
    return policy.decide(person, hp, alert, variants)


def _number(value):
    value = round(float(value), 4)
    if value == int(value):
        return int(value)
    return value


def _row(official, band, reason, agrees, contradicts, task, saved):
    return {
        "hit_id": official.hit_id,
        "alert_id": official.alert_id,
        "official_decision": REVIEW,
        "reason_code": official.reason_code,
        "customer_record_id": official.customer_record_id,
        "band": band,
        "band_reason": reason,
        "agrees": list(agrees),
        "contradicts": list(contradicts),
        "task": task,
        "expected_cost_saved": _number(saved),
    }


def _summary(outcomes, where, prefix=""):
    parts = []
    for outcome in outcomes:
        verb = "Would stay" if outcome["decision"] == REVIEW else "Would be"
        parts.append("%s %s if %s" % (verb, outcome["reason_code"], outcome["when"]))
    text = "; ".join(parts) if parts else "Would stay REVIEW"
    if prefix:
        text = prefix + text[0].lower() + text[1:]
    if where:
        return text + "; " + where + "."
    return text + "."


def _views(person, hp, alert, variants):
    cv = policy.customer_view(person, alert)
    return cv, policy.assess_name(cv, hp, variants), policy.assess_dob(cv, hp), policy.assess_countries(cv, hp)


def _name_vote(cv, name, dob, loc):
    """'agree', 'contradict', 'plain', 'alone', or 'ignore'.

    'plain': a declared or screened name agrees. The alert was raised on that
    name, so it is not a separate agreeing fact.
    'alone': the verified legal name agrees and neither the date of birth nor
    the country does. The name by itself is not a lean.
    """
    if name.state == policy.CONTRADICT:
        return "contradict"
    if name.state != policy.AGREE:
        return "ignore"
    verified = cv.verified_name is not None and name.cust is cv.verified_name
    if not verified:
        return "plain"
    if dob.state == policy.AGREE or loc.state == policy.AGREE:
        return "agree"
    return "alone"


def _band_from(cv, name, dob, loc):
    agrees, contradicts = [], []
    vote = _name_vote(cv, name, dob, loc)
    if vote == "agree":
        agrees.append("verified name")
    elif vote == "contradict":
        contradicts.append("verified name")
    if dob.state == policy.AGREE:
        agrees.append("date of birth")
    elif dob.state == policy.CONTRADICT:
        contradicts.append("date of birth")
    if loc.state == policy.AGREE:
        agrees.append("country")
    elif loc.state == policy.CONTRADICT:
        contradicts.append("country")
    if len(agrees) > len(contradicts):
        band = "leaning SAME"
    elif len(contradicts) > len(agrees):
        band = "leaning DIFFERENT"
    else:
        band = "neutral"
    if agrees and contradicts:
        reason = "Agrees on %s; contradicts on %s." % (", ".join(agrees), ", ".join(contradicts))
    elif agrees:
        reason = "Agrees on %s, and nothing contradicts." % ", ".join(agrees)
    elif contradicts:
        reason = "Contradicts on %s, and nothing agrees." % ", ".join(contradicts)
    else:
        reason = "No compared fact agrees or contradicts."
    if vote == "plain":
        reason += " The name agrees, but it is not a verified legal name, so that plain name match is not counted."
    elif vote == "alone":
        reason += (" The verified name agrees and neither the date of birth nor the country does, "
                   "so the name match alone is not counted.")
    return band, reason, agrees, contradicts


def _copy_person(person, **changes):
    if person is None:
        person = Person(record_ids=[], entity_type="Individual")
    clone = Person(
        record_ids=list(person.record_ids),
        entity_type=person.entity_type,
        verified_name=person.verified_name,
        verified_dob=person.verified_dob,
        declared_names=list(person.declared_names or []),
        declared_dobs=list(person.declared_dobs or []),
        countries=list(person.countries or []),
    )
    for key, value in changes.items():
        setattr(clone, key, value)
    return clone


def _copy_hit(hp, **changes):
    clone = HitProfile(
        hit_id=hp.hit_id, alert_id=hp.alert_id, entity_type=hp.entity_type,
        names=list(hp.names), dob_candidates=list(hp.dob_candidates), dob_origin=hp.dob_origin,
        earliest_report=hp.earliest_report, death_date=hp.death_date, countries=list(hp.countries),
    )
    for key, value in changes.items():
        setattr(clone, key, value)
    return clone


def _cap(ids, limit=5):
    ids = [item for item in ids if item]
    if len(ids) <= limit:
        return ", ".join(ids)
    return ", ".join(ids[:limit]) + " and %d more" % (len(ids) - limit)


def _where_customer_dob(person, data):
    if person is None or person.verified_dob is None:
        note_ids, check_ids = [], []
        customers = getattr(data, "customers", {}) if data is not None and person is not None else {}
        records = [customers[rid] for rid in (person.record_ids if person else []) if rid in customers]
        if records:
            from .customer import verified_checks
            from .load import norm_key
            for rec in records:
                for note in data.notes_by_email.get(norm_key(rec.get("email")), []):
                    if str(note.get("channel") or "").casefold() == "kyc" and note.get("note_id"):
                        note_ids.append(note["note_id"])
            for check in verified_checks(records, data):
                if check.get("origin") == "verified_kyc" and check.get("source_id"):
                    check_ids.append(check["source_id"])
        note_ids, check_ids = sorted(set(note_ids)), sorted(set(check_ids))
        bits = []
        if check_ids:
            bits.append("check " + _cap(check_ids))
        if note_ids:
            bits.append("check kyc notes " + _cap(note_ids))
        if not bits:
            return "request KYC; no approved KYC check exists"
        bits.append("no approved KYC check records a date of birth")
        return "; ".join(bits)
    return "compare the verified date of birth on %s" % person.verified_dob.source_id


def _where_hit_dob(hp, data):
    name = hp.names[0].value if hp.names else ""
    ids = []
    if data is not None and name:
        ids = [row["result_id"] for row in data.search_by_query.get(search_query(name), []) if row.get("result_id")]
    used = {cand.source_id for cand in hp.dob_candidates if cand.origin == "search"}
    unused = [result_id for result_id in ids if result_id not in used]
    bits = ["the hit's dobs field and profile notes do not give a date of birth"]
    if unused:
        bits.append("check search results " + _cap(unused))
    elif ids:
        bits.append("search results " + _cap(ids) + " were already considered")
    else:
        bits.append("no search result is filed under this hit's name")
    return "; ".join(bits)


def _sentinel(used):
    for name in _SENTINELS:
        country = to_country(name)
        if country and country not in used:
            return country
    return "Mongolia"


def _disagreeing_name(hp, company, variants):
    need = 1 if company else 2
    for candidate in _DISAGREEING:
        if len(real_parts(candidate, company, variants)) < need:
            continue
        if not hp.names or all(not names_agree(candidate, fact.value, variants, company) for fact in hp.names):
            return candidate
    return _DISAGREEING[0]


def _dob_label(company, side):
    noun = "incorporation date" if company else "date of birth"
    return ("the customer's verified " if side == "customer" else "the hit's ") + noun


def _years_of(value):
    if isinstance(value, (set, frozenset)):
        return [int(year) for year in value]
    if isinstance(value, PartialDate) and value.year is not None:
        return [value.year]
    return []


def _customer_dobs(person):
    if person is None:
        return []
    verified = person.verified_dob
    if verified is not None and verified.value is not None and getattr(verified.value, "year", None):
        return [verified]
    found, seen = [], set()
    for fact in person.declared_dobs or []:
        if fact.value is not None and getattr(fact.value, "year", None) and fact.value not in seen:
            seen.add(fact.value)
            found.append(fact)
    return found


def _report_years(hp):
    report = hp.earliest_report.value if hp.earliest_report is not None else None
    if report is None or report.year is None:
        return []
    return [report.year, report.year - policy.MIN_AGE]


def _hit_anchors(hp):
    years = []
    for cand in hp.dob_candidates:
        years.extend(_years_of(cand.value))
    years.extend(_report_years(hp))
    return years


def _window(anchors):
    anchors = [int(year) for year in anchors]
    if not anchors:
        return []
    return list(range(min(anchors) - 2, max(anchors) + 2 + 1))


def _phrase_ranges(scored, left, right, lo, hi, label):
    ranges, start, prev = [], scored[0], scored[0]
    for item in scored[1:]:
        if item[0] == prev[0] + 1 and item[1:] == prev[1:]:
            prev = item
            continue
        ranges.append((start, prev))
        start = prev = item
    ranges.append((start, prev))
    outcomes = []
    for first, last in ranges:
        year1, decision, code = first
        year2 = last[0]
        same = (decision, code)
        if year1 == lo and left == same and year2 == hi and right == same:
            when = "%s is any year" % label
        elif year1 == lo and left == same:
            when = "%s is before %d" % (label, year2 + 1)
        elif year2 == hi and right == same:
            when = "%s is after %d" % (label, year1 - 1)
        elif year1 == year2:
            when = "%s is in %d" % (label, year1)
        else:
            when = "%s is from %d to %d" % (label, year1, year2)
        outcomes.append({"when": when, "decision": decision, "reason_code": code})
    return outcomes


def _scan_years(anchors, apply, label):
    years = _window(anchors)
    if not years:
        first, second = apply(PartialDate(1950)), apply(PartialDate(2000))
        if (first.decision, first.reason_code) == (second.decision, second.reason_code):
            return [{"when": "%s is any year" % label, "decision": first.decision, "reason_code": first.reason_code}]
        return [
            {"when": "%s is in 1950" % label, "decision": first.decision, "reason_code": first.reason_code},
            {"when": "%s is in 2000" % label, "decision": second.decision, "reason_code": second.reason_code},
        ]
    lo, hi = years[0], years[-1]
    scored = []
    for year in years:
        decision = apply(PartialDate(year))
        scored.append((year, decision.decision, decision.reason_code))
    left, right = apply(PartialDate(lo - 1)), apply(PartialDate(hi + 1))
    return _phrase_ranges(scored, (left.decision, left.reason_code), (right.decision, right.reason_code), lo, hi, label)


def _first_dated(values):
    for value in values:
        if isinstance(value, PartialDate) and value.year is not None and value.month is not None:
            return value
    return None


def _month_day_regions(dated, apply, label):
    if dated is None:
        return []
    base = apply(PartialDate(dated.year))
    extra = []
    other_month = 1 if dated.month != 1 else 2
    flipped = apply(PartialDate(dated.year, other_month))
    if (flipped.decision, flipped.reason_code) != (base.decision, base.reason_code):
        extra.append({
            "when": "%s is in %04d-%02d, a different month from %04d-%02d" % (
                label, dated.year, other_month, dated.year, dated.month),
            "decision": flipped.decision, "reason_code": flipped.reason_code,
        })
    if dated.day is not None:
        other_day = 1 if dated.day != 1 else 2
        flipped_day = apply(PartialDate(dated.year, dated.month, other_day))
        if (flipped_day.decision, flipped_day.reason_code) != (base.decision, base.reason_code):
            extra.append({
                "when": "%s is in %04d-%02d-%02d, a different day from %s" % (
                    label, dated.year, dated.month, other_day, fmt_date(dated)),
                "decision": flipped_day.decision, "reason_code": flipped_day.reason_code,
            })
    return extra


def _outcome(decision, when):
    return {"when": when, "decision": decision.decision, "reason_code": decision.reason_code}


def _collapse(outcomes, when):
    keys = {(item["decision"], item["reason_code"]) for item in outcomes}
    if len(keys) == 1 and outcomes:
        return [{"when": when, "decision": outcomes[0]["decision"], "reason_code": outcomes[0]["reason_code"]}]
    return outcomes


def _slots(person, hp, alert, variants):
    cv, name, dob, loc = _views(person, hp, alert, variants)
    slots = []
    if dob.state == policy.UNKNOWN and not _customer_dobs(person):
        slots.append("verified_dob")
    elif dob.state == policy.NEITHER and _customer_dobs(person):
        slots.append("verified_dob")
    if dob.state == policy.UNKNOWN and not hp.dob_candidates:
        slots.append("hit_dob")
    if name.state in (policy.UNKNOWN, policy.NEITHER):
        slots.append("verified_name")
    if not hp.names:
        slots.append("hit_name")
    if loc.state == policy.UNKNOWN:
        if not loc.cust:
            slots.append("customer_country")
        if not loc.hit:
            slots.append("hit_country")
    elif loc.state == policy.CONTRADICT:
        slots.append("customer_country")
    if cv.entity_type is None or policy._kind(hp.entity_type) is None:
        slots.append("entity_type")
    return slots, cv, name, dob, loc


def _probe_customer_dob(person, hp, alert, variants, found_dob, company, data):
    label = _dob_label(company, "customer")

    def apply(partial):
        return _decide(_copy_person(person, verified_dob=Fact(partial, "hypothetical", "hypothetical")),
                       hp, alert, variants)

    if found_dob == policy.NEITHER:
        cust = _customer_dobs(person)[0].value
        trials = []
        if cust.month is None:
            for month in (1, 6, 12):
                trials.append(("%s is in %s with month %02d" % (label, cust.year, month), PartialDate(cust.year, month)))
        elif cust.day is None:
            for day in (1, 15, 28):
                trials.append(("%s is %04d-%02d with day %02d" % (label, cust.year, cust.month, day),
                               PartialDate(cust.year, cust.month, day)))
        else:
            trials.append(("%s stays %s" % (label, fmt_date(cust)), cust))
        outcomes = _collapse([_outcome(apply(partial), when) for when, partial in trials],
                             "%s keeps the year %s" % (label, cust.year))
        kind = "conflicting"
    else:
        outcomes = _scan_years(_hit_anchors(hp), apply, label)
        outcomes.extend(_month_day_regions(_first_dated([c.value for c in hp.dob_candidates]), apply, label))
        kind = "missing"
    fact = "verified incorporation date" if company else "verified date of birth"
    return outcomes, {"fact": fact, "side": "customer", "kind": kind, "where": _where_customer_dob(person, data)}


def _probe_hit_dob(person, hp, alert, variants, company, data):
    label = _dob_label(company, "hit")

    def apply(partial):
        probed = _copy_hit(hp, dob_candidates=[Fact(partial, "hypothetical", "dobs")], dob_origin="dobs")
        return _decide(person, probed, alert, variants)

    anchors = [fact.value.year for fact in _customer_dobs(person)] + _report_years(hp)
    outcomes = _scan_years(anchors, apply, label)
    dobs = _customer_dobs(person)
    dated = dobs[0].value if dobs and isinstance(dobs[0].value, PartialDate) and dobs[0].value.month else None
    outcomes.extend(_month_day_regions(dated, apply, label))
    return outcomes, {"fact": "hit date of birth", "side": "hit", "kind": "missing", "where": _where_hit_dob(hp, data)}


def _probe_customer_name(person, hp, alert, variants, company, name_state):
    if hp.names:
        agree = hp.names[0].value
        disagree = _disagreeing_name(hp, company, variants)
        trials = [
            ("the customer's verified legal name agrees with the hit's name %s" % agree, agree),
            ("the customer's verified legal name agrees with none of the hit's names", disagree),
        ]
    else:
        trials = [("the customer's verified legal name is supplied and the hit has no name", "Ana Silva Example")]
    outcomes = [_outcome(_decide(_copy_person(person, verified_name=Fact(name, "hypothetical", "hypothetical")),
                                 hp, alert, variants), when) for when, name in trials]
    if person is not None and person.verified_name is not None and name_state == policy.UNKNOWN:
        where = "check %s; the verified name has too few real parts to compare" % person.verified_name.source_id
    elif person is None or person.verified_name is None:
        where = "request KYC; no verified legal name is on file"
    else:
        where = "the verified legal name on %s does not settle the hit" % person.verified_name.source_id
    kind = "missing" if name_state == policy.UNKNOWN else "conflicting"
    return outcomes, {"fact": "verified legal name", "side": "customer", "kind": kind, "where": where}


def _probe_hit_name(person, hp, alert, variants, company):
    if person is not None and person.verified_name is not None:
        names = [person.verified_name]
    elif person is not None:
        names = list(person.declared_names or [])
    else:
        names = []
    customer_name = names[0].value if names else ""
    if not customer_name:
        outcomes = [_outcome(_decide(person, hp, alert, variants),
                             "the hit has no name and the customer has no comparable name")]
    else:
        disagree = _disagreeing_name(hp, company, variants)
        outcomes = []
        for when, name in (
            ("the hit's name agrees with the customer's name %s" % customer_name, customer_name),
            ("the hit's name agrees with none of the customer's names", disagree),
        ):
            outcomes.append(_outcome(
                _decide(person, _copy_hit(hp, names=[Fact(name, hp.hit_id, "name")]), alert, variants), when))
    return outcomes, {"fact": "hit name", "side": "hit", "kind": "missing", "where": "read the hit's name and aliases"}


def _probe_customer_country(person, hp, alert, variants, loc):
    hit_countries, cust_countries = list(loc.hit), list(loc.cust)
    used = set(hit_countries) | set(cust_countries)
    if loc.state == policy.CONTRADICT and hit_countries:
        shared = next(country for country in hit_countries if country not in set(cust_countries))
        added = _decide(
            _copy_person(person, countries=list(person.countries) + [Fact(shared, "hypothetical", "hypothetical")]),
            hp, alert, variants)
        stayed = _decide(person, hp, alert, variants)
        outcomes = [
            _outcome(added, "the customer is also linked to %s" % shared),
            _outcome(stayed, "the customer's countries stay %s" % ", ".join(cust_countries)),
        ]
        sources = sorted({fact.source_id for fact in person.countries
                          if fact.source_id and fact.source_id != "hypothetical"})
        where = "check KYC or a residence note for a link to %s" % shared
        if sources:
            where += "; countries on file come from " + _cap(sources)
        kind = "conflicting"
    elif hit_countries:
        shared, other = hit_countries[0], _sentinel(used)
        same = _decide(_copy_person(person, countries=[Fact(shared, "hypothetical", "hypothetical")]), hp, alert, variants)
        different = _decide(_copy_person(person, countries=[Fact(other, "hypothetical", "hypothetical")]), hp, alert, variants)
        outcomes = [
            _outcome(same, "the customer is linked to %s" % shared),
            _outcome(different, "the customer is linked only to %s" % other),
        ]
        where, kind = "request KYC; no document country or residence note is on file", "missing"
    else:
        same_name = _sentinel(set())
        other = _sentinel({same_name})
        both = _copy_hit(hp, countries=[Fact(same_name, hp.hit_id, "hit_country")])
        split = _copy_hit(hp, countries=[Fact(other, hp.hit_id, "hit_country")])
        agreed = _decide(_copy_person(person, countries=[Fact(same_name, "hypothetical", "hypothetical")]), both, alert, variants)
        differed = _decide(_copy_person(person, countries=[Fact(same_name, "hypothetical", "hypothetical")]), split, alert, variants)
        outcomes = [
            _outcome(agreed, "the customer and the hit are both linked to %s" % same_name),
            _outcome(differed, "the customer is linked only to %s and the hit only to %s" % (same_name, other)),
        ]
        where, kind = "request KYC; neither side has a country on file", "missing"
    return outcomes, {"fact": "customer country", "side": "customer", "kind": kind, "where": where}


def _probe_hit_country(person, hp, alert, variants, loc):
    if loc.cust:
        shared, other = loc.cust[0], _sentinel(set(loc.cust))
        same = _copy_hit(hp, countries=[Fact(shared, hp.hit_id, "hit_country")])
        different = _copy_hit(hp, countries=[Fact(other, hp.hit_id, "hit_country")])
        outcomes = [
            _outcome(_decide(person, same, alert, variants), "the hit is linked to %s" % shared),
            _outcome(_decide(person, different, alert, variants), "the hit is linked only to %s" % other),
        ]
        return outcomes, {
            "fact": "hit country", "side": "hit", "kind": "missing",
            "where": "read the hit's countries, nationality, addresses and place of birth",
        }
    outcomes, meta = _probe_customer_country(person, hp, alert, variants, loc)
    meta = dict(meta)
    meta.update(fact="hit country", side="hit",
                where="read the hit's countries, nationality, addresses and place of birth")
    return outcomes, meta


def _probe_entity_type(person, hp, alert, variants, cv):
    customer_type, hit_type = cv.entity_type, policy._kind(hp.entity_type)
    if customer_type is None and hit_type is None:
        trials = [
            ("the customer and the hit are both people", "Individual", "Individual"),
            ("the customer and the hit are both companies", "Company", "Company"),
            ("the customer is a person and the hit is a company", "Individual", "Company"),
        ]
    elif customer_type is None:
        trials = [("the customer is a person", "Individual", hp.entity_type),
                  ("the customer is a company", "Company", hp.entity_type)]
    else:
        trials = [("the hit is a person", person.entity_type, "Individual"),
                  ("the hit is a company", person.entity_type, "Company")]
    outcomes = [_outcome(_decide(_copy_person(person, entity_type=cust), _copy_hit(hp, entity_type=hit_kind),
                                 alert, variants), when) for when, cust, hit_kind in trials]
    side = "hit" if customer_type is not None and hit_type is None else "customer"
    return outcomes, {"fact": "entity type", "side": side, "kind": "missing",
                      "where": "confirm whether the customer and the hit are a person or a company"}


def _best_fact_task(official, persons, hp, alert, variants, data):
    best = None
    for person in persons:
        slots, cv, name, dob, loc = _slots(person, hp, alert, variants)
        company = cv.entity_type == COMPANY
        for slot in slots:
            if slot == "verified_dob":
                outcomes, meta = _probe_customer_dob(person, hp, alert, variants, dob.state, company, data)
            elif slot == "hit_dob":
                outcomes, meta = _probe_hit_dob(person, hp, alert, variants, company, data)
            elif slot == "verified_name":
                outcomes, meta = _probe_customer_name(person, hp, alert, variants, company, name.state)
            elif slot == "hit_name":
                outcomes, meta = _probe_hit_name(person, hp, alert, variants, company)
            elif slot == "customer_country":
                outcomes, meta = _probe_customer_country(person, hp, alert, variants, loc)
            elif slot == "hit_country":
                outcomes, meta = _probe_hit_country(person, hp, alert, variants, loc)
            else:
                outcomes, meta = _probe_entity_type(person, hp, alert, variants, cv)
            if not outcomes:
                continue
            saved = expected_cost_saved(outcomes)
            rank_key = (-saved, _PRIORITY[slot], tuple(person.record_ids))
            if best is None or rank_key < best[0]:
                best = (rank_key, person, cv, name, dob, loc, outcomes, meta, saved)
    if best is None:
        cv, name, dob, loc = _views(persons[0], hp, alert, variants)
        band, reason, agrees, contradicts = _band_from(cv, name, dob, loc)
        task = {
            "fact": "compared facts", "side": "customer", "kind": "conflicting",
            "summary": "Would stay INSUFFICIENT_DATA if the known facts stay as they are.",
            "where": "a reviewer looks at the customer record and the hit together",
            "outcomes": [{"when": "the known facts stay as they are", "decision": REVIEW,
                          "reason_code": "INSUFFICIENT_DATA"}],
        }
        return _row(official, band, reason, agrees, contradicts, task, 0)
    _key, person, cv, name, dob, loc, outcomes, meta, saved = best
    band, reason, agrees, contradicts = _band_from(cv, name, dob, loc)
    where, prefix = meta["where"], ""
    if len(persons) > 1 and person.record_ids:
        prefix = "For " + ", ".join(person.record_ids) + ", "
        where = "for " + ", ".join(person.record_ids) + ": " + where
    elif len(person.record_ids) > 1:
        where = "for " + ", ".join(person.record_ids) + ": " + where
    task = {
        "fact": meta["fact"], "side": meta["side"], "kind": meta["kind"],
        "summary": _summary(outcomes, where, prefix), "where": where, "outcomes": outcomes,
    }
    return _row(official, band, reason, agrees, contradicts, task, saved)


def _ambiguous_task(official, persons, hp, alert, variants):
    decisions = [_decide(person, hp, alert, variants) for person in persons]
    outcomes, groups, same, different = [], [], 0, 0
    for person, decision in zip(persons, decisions):
        ids = ", ".join(person.record_ids) or "?"
        groups.append(ids)
        outcomes.append(_outcome(decision, "the screened customer is %s" % ids))
        if decision.decision == SAME_ENTITY:
            same += 1
        elif decision.decision == DIFFERENT_ENTITY:
            different += 1
    if same and not different:
        band = "leaning SAME"
    elif different and not same:
        band = "leaning DIFFERENT"
    else:
        band = "neutral"
    bits = ["%s would be %s (%s)" % (", ".join(person.record_ids) or "?", decision.decision, decision.reason_code)
            for person, decision in zip(persons, decisions)]
    where = ("resolve which customer was screened; compare the screened name and date of birth with "
             + "; ".join(groups))
    task = {"fact": "which customer record", "side": "customer", "kind": "conflicting",
            "summary": _summary(outcomes, where), "where": where, "outcomes": outcomes}
    return _row(official, band, "Candidate records disagree: " + "; ".join(bits) + ".", [], [], task,
                expected_cost_saved(outcomes))


def _missing_customer_task(official, hp, alert, variants):
    decided = _decide(None, hp, alert, variants)
    outcomes = [_outcome(decided, "no customer record is resolved")]
    where = ("find the customer from the alert's account, login or email, or search the system of record "
             "for the screened name")
    task = {"fact": "customer record", "side": "customer", "kind": "missing",
            "summary": _summary(outcomes, where), "where": where, "outcomes": outcomes}
    return _row(official, "neutral", "No customer record was resolved, so no fact agrees or contradicts.",
                [], [], task, expected_cost_saved(outcomes))
