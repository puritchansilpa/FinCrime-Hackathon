"""[Workstream A] Resolve an alert to the customer (SOP principles 2-4).

A2 (this file today): follow the link the alert carries.
    account_ref  -> accounts (a joint account has several holders) -> customer
    login_handle -> accounts -> customer
    email        -> customers.email
  When a link gives several records (joint holders), keep the ones the screened
  name and date of birth fit. Never mix in a record that does not fit.
A3: search for alerts with no link.        (not built yet)
A4: group records into persons.            (not built yet: one record = one person)
A6: verified facts from the KYC table/notes (not built yet)
"""
import re
import unicodedata

from . import names, normalize
from .load import name_tokens, norm_key
from .models import Fact, PartialDate, Person, Resolution

LINKS = ("account_ref", "login_handle", "email")
NAME_FIELDS = ("full_name", "preferred_name", "login_name")


# --- comparing a record with what was screened --------------------------------------
# B owns the real date parser and name matcher (normalize.parse_date, names.names_agree).
# Until those land we fall back to the small local versions below, which are strict:
# they only recognise exact token overlap and the date formats seen in the data.

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9


def _local_parse_date(s):
    """ISO, DD/MM/YYYY (day-first), '17 June 1976', 'June 17, 1976', 'June 1976', '1976', '1976-06'."""
    if not s:
        return None
    t = str(s).strip().casefold().replace(",", " ")
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t)
    m = re.fullmatch(r"(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?", t)
    if m:
        y, mo, d = m.groups()
        return _mk(int(y), mo and int(mo), d and int(d))
    m = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", t)
    if m:
        return _mk(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    parts = t.split()
    nums = [p for p in parts if p.isdigit()]
    month = next((MONTHS[p] for p in parts if p in MONTHS), None)
    years = [int(p) for p in nums if len(p) == 4]
    days = [int(p) for p in nums if len(p) <= 2]
    if len(years) == 1 and month and len(parts) == len(nums) + 1 and len(days) <= 1:
        return _mk(years[0], month, days[0] if days else None)
    return None


def _mk(y, mo=None, d=None):
    if mo is not None and not 1 <= mo <= 12:
        return None
    if d is not None and not 1 <= d <= 31:
        return None
    return PartialDate(y, mo, d)


def parse_date(s):
    return normalize.parse_date(s) or _local_parse_date(s)


def dob_fits(screened, record) -> bool:
    """True unless both dates are known and differ in a part both give.

    Unknown stays unknown: a missing or unparseable date never rules a record out.
    """
    a, b = parse_date(screened), parse_date(record)
    if a is None or b is None:
        return True
    for x, y in ((a.year, b.year), (a.month, b.month), (a.day, b.day)):
        if x is not None and y is not None and x != y:
            return False
    return True


def _tokens(s):
    return set(name_tokens(s))


def name_fits(screened, record_names) -> bool:
    """The screened name agrees with any of the record's names.

    B's names_agree (variants, joined parts, small edits) once it lands; until then,
    exact tokens: at least two shared, or every token of the shorter name shared.
    """
    a = _tokens(screened)
    for other in record_names:
        if not other:
            continue
        if names.names_agree(screened, other):
            return True
        b = _tokens(other)
        if not a or not b:
            continue
        shared = a & b
        if len(shared) >= 2 or shared == (a if len(a) <= len(b) else b):
            return True
    return False


def record_fits(alert, rec) -> bool:
    return (name_fits(alert.get("customer_name"), [rec.get(f) for f in NAME_FIELDS])
            and dob_fits(alert.get("dob"), rec.get("dob")))


# --- following the links ------------------------------------------------------------

def _follow(alert, data, path):
    """Records reached by the alert's links, as {record_id: record}. Logs each step in path."""
    found = {}
    for link in LINKS:
        value = alert.get(link)
        if not value:
            continue
        key = norm_key(value)
        if link == "email":
            rows = data.customers_by_email.get(key, [])
            ids = [r["record_id"] for r in rows]
            step = f"email {value} -> customers"
        else:
            index = data.accounts_by_id if link == "account_ref" else data.accounts_by_login
            accounts = index.get(key, [])
            ids = sorted({a["customer_id"] for a in accounts if a.get("customer_id")})
            step = f"{link} {value} -> accounts"
            if len(ids) > 1:
                step += ": joint holders " + " and ".join(ids)
        missing = [i for i in ids if i not in data.customers]
        ids = [i for i in ids if i in data.customers]
        if missing:
            step += f" (not in customers: {', '.join(missing)})"
        if not ids:
            step += " -> no customer found"
        elif len(ids) == 1 and "joint" not in step:
            step += f" -> {ids[0]}"
        path.append(step)
        for i in ids:
            found[i] = data.customers[i]
    return found


def _person_from_records(records, data) -> Person:
    """One Person from records already known to be the same person.

    A2 fills only the declared facts on the records; A6 adds the verified check
    (KYC table or kyc note) and residence-note countries.
    """
    records = sorted(records, key=lambda r: r["record_id"])
    declared_names, declared_dobs, countries = [], [], []
    for r in records:
        rid = r["record_id"]
        for f in NAME_FIELDS:
            if r.get(f):
                declared_names.append(Fact(r[f], rid, f))
        d = parse_date(r.get("dob"))
        if d is not None:
            declared_dobs.append(Fact(d, rid, "record"))
        for f in ("nationality", "residence_country"):
            if r.get(f):
                countries.append(Fact(normalize.to_country(r[f]) or r[f], rid, f))
    types = sorted({r.get("entity_type") for r in records if r.get("entity_type")})
    return Person(
        record_ids=[r["record_id"] for r in records],
        entity_type=types[0] if len(types) == 1 else (types[0] if types else ""),
        declared_names=declared_names,
        declared_dobs=declared_dobs,
        countries=countries,
    )


def resolve(alert: dict, data) -> Resolution:
    path = []
    found = _follow(alert, data, path)

    if not any(alert.get(link) for link in LINKS):
        path.append("no link on the alert (search not built yet)")
        return Resolution(alert_id=alert["alert_id"], persons=[], path=path)

    if not found:
        return Resolution(alert_id=alert["alert_id"], persons=[], path=path)

    candidates = [found[k] for k in sorted(found)]
    if len(candidates) == 1:
        chosen = candidates
    else:
        chosen = [r for r in candidates if record_fits(alert, r)]
        ids = [r["record_id"] for r in chosen]
        if len(chosen) == 1:
            path.append(f"the screened name and date of birth fit {ids[0]}")
        elif chosen:
            path.append(f"the screened name and date of birth fit {', '.join(ids)}")
        else:
            # Nobody fits: keep them all, so the policy sees every holder and can only
            # clear if every one of them is contradicted (otherwise AMBIGUOUS / REVIEW).
            chosen = candidates
            path.append("the screened name and date of birth fit none of them; keeping all")

    # A4 will group records into persons; until then each record is its own person.
    persons = [_person_from_records([r], data) for r in chosen]
    return Resolution(alert_id=alert["alert_id"], persons=persons, path=path)
