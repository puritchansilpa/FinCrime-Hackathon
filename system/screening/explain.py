"""Reason sentences, in the style of the practice labels' `reference_reason`.  [Workstream B]

Every sentence uses the hit's own facts and names the record each customer fact came from.
"""

from typing import Iterable, List, Optional

from .models import COMPANY, Fact, PartialDate


def fmt_date(d) -> str:
    if isinstance(d, PartialDate):
        return d.iso()
    if isinstance(d, (set, frozenset)):
        ys = sorted(d)
        return " or ".join(str(y) for y in ys)
    return str(d)


def fmt_list(items: Iterable[str]) -> str:
    return ", ".join(sorted(set(items)))


def hit_dob_phrase(cands: List[Fact]) -> str:
    """'the hit's listed date of birth is 1962-09-10' / '… profile notes put its birth year at 1986 or 1987'."""
    listed = [c for c in cands if c.origin == "dobs"]
    stated = [c for c in cands if c.origin == "profile_dob"]
    profile = [c for c in cands if c.origin == "profile_age"]
    search = [c for c in cands if c.origin == "search"]
    parts = []
    if listed:
        vals = ", ".join(fmt_date(c.value) for c in listed)
        parts.append(("the hit's listed date of birth is " if len(listed) == 1 else
                      "the hit's listed dates of birth are ") + vals)
    if stated:
        vals = ", ".join(fmt_date(c.value) for c in stated)
        parts.append("the hit's profile notes put its birth date at " + vals)
    if profile:
        parts.append("the hit's profile notes put its birth year at " + "; ".join(fmt_date(c.value) for c in profile))
    if search:
        parts.append("the hit's search results put its birth year at " +
                     "; ".join(f"{fmt_date(c.value)} ({c.source_id})" if len(search) > 1 else fmt_date(c.value)
                               for c in search))
    return " and ".join(parts)


def hit_dob_values(cands: List[Fact]) -> str:
    """'1967 or 1968' / '1994, 1995' / '1968-02' for agreement sentences."""
    listed = [c for c in cands if c.origin == "dobs"]
    if listed:
        return ", ".join(fmt_date(c.value) for c in listed)
    return "; ".join(fmt_date(c.value) for c in cands)


# --- contradiction sentences ------------------------------------------------

def s_type(cust_type: str, hit_type: str, src: Optional[str]) -> str:
    a = "a company" if cust_type == COMPANY else "an individual"
    b = "a company" if hit_type == COMPANY else "an individual"
    where = f" ({src})" if src else ""
    return f"The customer is {a}{where} but the hit is {b}."


def s_deceased(death: PartialDate, screened: PartialDate) -> str:
    return (f"The hit's profile gives a date of death of {fmt_date(death)}, before the customer "
            f"was screened on {fmt_date(screened)}.")


def s_temporal_person(birth: Fact, age: int, report: PartialDate) -> str:
    b = birth.value
    if b.month is not None and b.day is not None:
        return (f"The customer was born on {fmt_date(b)} ({birth.source_id}), so they were {age} "
                f"when the hit's profile reports activity on {fmt_date(report)}.")
    return (f"The customer was born in {fmt_date(b)} ({birth.source_id}), so they were at most {age} "
            f"when the hit's profile reports activity on {fmt_date(report)}.")


def s_temporal_company(inc: Fact, report: PartialDate) -> str:
    return (f"The customer was incorporated on {fmt_date(inc.value)} ({inc.source_id}), after the hit's "
            f"profile reports activity on {fmt_date(report)}.")


def s_dob_mismatch(cust: Fact, cands: List[Fact], company: bool = False) -> str:
    what = "incorporation date" if company else "date of birth"
    return f"The customer's {what} is {fmt_date(cust.value)} ({cust.source_id}) but {hit_dob_phrase(cands)}."


def s_location_mismatch(cust_countries: Iterable[str], hit_countries: Iterable[str]) -> str:
    return (f"The customer is linked only to {fmt_list(cust_countries)} but the hit is linked only to "
            f"{fmt_list(hit_countries)}.")


def s_name_mismatch(verified: Fact, hit_name: str, has_aliases: bool) -> str:
    tail = " or any of its aliases" if has_aliases else ""
    return (f"The customer's verified name is {verified.value} ({verified.source_id}), which does not "
            f"match the hit's name {hit_name}{tail}.")


def s_cleared(company: bool) -> str:
    return f"This contradiction shows the hit is a different {'company' if company else 'person'}, so it is cleared."


# --- agreement sentences ----------------------------------------------------

def s_dob_agrees(cust: Fact, cands: List[Fact]) -> str:
    return (f"The customer's date of birth {fmt_date(cust.value)} ({cust.source_id}) agrees with the "
            f"hit's {hit_dob_values(cands)}.")


def s_shared_countries(shared: Iterable[str]) -> str:
    return f"Both the customer and the hit are linked to {fmt_list(shared)}."


def s_name_agrees(hit_name: str) -> str:
    return f"The customer's name agrees with the hit's name {hit_name}."


def s_location_exception(cust_countries, hit_countries) -> str:
    return (f"The customer is linked only to {fmt_list(cust_countries)} and the hit only to "
            f"{fmt_list(hit_countries)}, but a country difference does not clear a hit whose name and "
            f"date of birth agree, so the hit needs review.")


def s_review_tail(missing: str) -> str:
    return (f"Nothing in the customer's records contradicts the hit, and {missing}, so the hit can be "
            f"neither cleared nor confirmed.")


def s_no_customer(alert_id: str) -> str:
    return f"No customer record in the bank's systems fits alert {alert_id}."


def s_ambiguous(record_groups: List[List[str]], decisions: List[str]) -> str:
    people = "; ".join(", ".join(g) for g in record_groups)
    return (f"{len(record_groups)} different people in the system of record fit this alert ({people}). "
            f"They lead to different decisions ({', '.join(decisions)}), so the hit needs review.")


def s_unresolved_places(places) -> str:
    shown = "; ".join(sorted(places)[:3]) + ("; and others" if len(places) > 3 else "")
    shown = shown[:1].upper() + shown[1:]
    return f"{shown} could not be tied to a country, so the countries cannot rule the hit out."
