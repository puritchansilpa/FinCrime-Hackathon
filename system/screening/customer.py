"""[Workstream A] Resolve an alert to the customer (SOP principles 2-4).

A2: follow the link the alert carries.
    account_ref  -> accounts (a joint account has several holders) -> customer
    login_handle -> accounts -> customer
    email        -> customers.email
  When a link gives several records, the screened details pick between them,
  exactly as in a search (principle 2).
A3: no link -> search for the records that fit what was screened:
    a full, preferred or login name that agrees with the screened name (principle 8),
    a date of birth equal in every part both give, the screened country as residence
    or nationality, and the screened city in the record's city or address.
A4: group records into persons.            (not built yet: one record = one person)
A6: verified facts from the KYC table/notes (not built yet)

Never use another customer's records.
"""
from . import fallbacks, names, normalize
from .load import name_tokens, norm_key
from .models import Fact, Person, Resolution

LINKS = ("account_ref", "login_handle", "email")
NAME_FIELDS = ("full_name", "preferred_name", "login_name")


# --- B's normalisers first, A's fallbacks when B returns nothing --------------------

def parse_date(s):
    return normalize.parse_date(s) or fallbacks.parse_date(s)


def to_country(s):
    return normalize.to_country(s) or fallbacks.to_country(s)


def names_agree(a, b, is_company=False) -> bool:
    return bool(names.names_agree(a, b)) or fallbacks.names_agree(a, b, is_company)


def _is_company(entity_type) -> bool:
    return str(entity_type or "").strip().casefold() == "company"


# --- does a record fit what was screened? --------------------------------------------

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


def name_fits(screened, record_names, is_company=False) -> bool:
    """The screened name agrees with any of the record's full, preferred or login names."""
    return bool(screened) and any(names_agree(screened, n, is_company) for n in record_names if n)


def country_fits(screened, rec) -> bool:
    """The screened country is the record's residence or nationality (unknown = fits)."""
    want = to_country(screened)
    if want is None:
        return True
    have = {to_country(rec.get(f)) for f in ("residence_country", "nationality")} - {None}
    return not have or want in have


def city_fits(screened, rec) -> bool:
    """The screened city appears in the record's city or address (unknown = fits)."""
    if not screened:
        return True
    hay = " ".join(fallbacks.fold_text(rec.get(f)) for f in ("city", "address")).strip()
    if not hay:
        return True
    hay = f" {hay} "
    full = fallbacks.fold_text(screened)
    first = fallbacks.fold_text(str(screened).split(",")[0])
    return any(n and f" {n} " in hay for n in (full, first))


def type_fits(alert, rec) -> bool:
    a, b = alert.get("entity_type"), rec.get("entity_type")
    return not a or not b or _is_company(a) == _is_company(b)


def record_fits(alert, rec) -> bool:
    return (type_fits(alert, rec)
            and name_fits(alert.get("customer_name"), [rec.get(f) for f in NAME_FIELDS],
                          _is_company(alert.get("entity_type") or rec.get("entity_type")))
            and dob_fits(alert.get("dob"), rec.get("dob"))
            and country_fits(alert.get("country"), rec)
            and city_fits(alert.get("city"), rec))


# --- following links ----------------------------------------------------------------

def _follow(alert, data, path):
    """Records reached by the alert's links, as {record_id: record}. Logs each step in path."""
    found = {}
    for link in LINKS:
        value = alert.get(link)
        if not value:
            continue
        key = norm_key(value)
        if link == "email":
            ids = [r["record_id"] for r in data.customers_by_email.get(key, [])]
            step = f"email {value} -> customers"
        else:
            index = data.accounts_by_id if link == "account_ref" else data.accounts_by_login
            ids = sorted({a["customer_id"] for a in index.get(key, []) if a.get("customer_id")})
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


# --- searching without a link -------------------------------------------------------

def _search_keys(name, data):
    """Index keys to look up: the name's tokens, its normalised parts and their variants."""
    keys = set(name_tokens(name)) | set(fallbacks.name_parts(name))
    for k in list(keys):
        keys |= fallbacks.variant_spellings(k)
    return keys


def search(alert, data):
    """Records that fit the screened details, sorted by record_id."""
    name = alert.get("customer_name")
    if not name:
        return []
    candidates = {}
    for key in _search_keys(name, data):
        for rec in data.customers_by_name_token.get(key, ()):
            candidates[rec["record_id"]] = rec
    # Names with a typo in every part share no token: also scan the screened birth year.
    dob = parse_date(alert.get("dob"))
    if dob is not None and dob.year is not None:
        for rec in data.customers_by_birth_year.get(dob.year, ()):
            candidates[rec["record_id"]] = rec
    return [candidates[k] for k in sorted(candidates) if record_fits(alert, candidates[k])]


# --- building persons -----------------------------------------------------------------

def _person_from_records(records, data) -> Person:
    """One Person from records already known to be the same person.

    Fills the declared facts on the records; A6 adds the verified check
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
            c = to_country(r.get(f))
            if c:
                countries.append(Fact(c, rid, f))
    types = sorted({r.get("entity_type") for r in records if r.get("entity_type")})
    return Person(
        record_ids=[r["record_id"] for r in records],
        entity_type=types[0] if types else "",
        declared_names=declared_names,
        declared_dobs=declared_dobs,
        countries=countries,
    )


def resolve(alert: dict, data) -> Resolution:
    path = []
    if any(alert.get(link) for link in LINKS):
        found = _follow(alert, data, path)
        candidates = [found[k] for k in sorted(found)]
        if len(candidates) > 1:
            chosen = [r for r in candidates if record_fits(alert, r)]
            ids = [r["record_id"] for r in chosen]
            if chosen:
                path.append(f"the screened name and date of birth fit {', '.join(ids)}")
            else:
                # Nobody fits: keep them all, so the policy sees every holder and can only
                # clear if every one of them is contradicted (otherwise AMBIGUOUS / REVIEW).
                chosen = candidates
                path.append("the screened details fit none of them; keeping all")
        else:
            chosen = candidates  # a single linked record is trusted
    else:
        chosen = search(alert, data)
        ids = [r["record_id"] for r in chosen]
        path.append("name, date of birth, country and city -> customers -> "
                    + (", ".join(ids) if ids else "no record fits"))

    # A4 will group records into persons; until then each record is its own person.
    persons = [_person_from_records([r], data) for r in chosen]
    return Resolution(alert_id=alert["alert_id"], persons=persons, path=path)
