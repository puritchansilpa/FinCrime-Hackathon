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
A4: group the fitting records into persons: same phone + same full DOB, or the same
    document number on approved checks; links chain, and linked records join the person.
A6: build each Person: declared facts from every record; verified name, DOB and document
    country from the most recent APPROVED check (KYC table or kyc note); countries from
    records, the document and residence notes. Every fact keeps its source record ID.

Never use another customer's records.
"""
from . import fallbacks, llm, names, normalize, notes_parse
from .load import name_tokens, norm_key, phone_key
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


# --- one person, one picture (principle 3) -----------------------------------------------

def _phones(rec, data) -> set:
    """The record's phone plus the phones on its own accounts, as digit strings."""
    rid = rec["record_id"]
    phones = {phone_key(rec.get("phone"))}
    phones |= {phone_key(a.get("phone")) for a in data.accounts_by_customer.get(rid, ())}
    return phones - {""}


def applicant_ids(rid, data) -> list:
    """KYC applicant IDs of a customer record, via onboarding (by customer and by account)."""
    apps = {o.get("kyc_applicant_id") for o in data.onboarding_by_customer.get(rid, ())}
    for acc in data.accounts_by_customer.get(rid, ()):
        for o in data.onboarding_by_account.get(norm_key(acc.get("account_id")), ()):
            if o.get("customer_id") in (None, "", rid):
                apps.add(o.get("kyc_applicant_id"))
    return sorted(a for a in apps if a)


def is_approved(check) -> bool:
    return str(check.get("result") or "").strip().casefold() == "approved"


def approved_checks(rid, data) -> list:
    """The record's approved KYC-table checks, oldest first. Rejected/expired are not evidence."""
    checks = [c for app in applicant_ids(rid, data) for c in data.kyc_by_applicant.get(app, ())
              if is_approved(c)]
    return sorted(checks, key=lambda c: (str(c.get("checked_at") or ""), str(c.get("check_id"))))


def _same_person_links(rec, data):
    """(other record_id, why) for records that are the same person as rec.

    Same phone AND the same full date of birth, or the same document number on
    approved checks. A shared phone or address alone is not enough (families share them).
    """
    rid = rec["record_id"]
    dob = parse_date(rec.get("dob"))
    if fallbacks.full_date(dob):
        for phone in sorted(_phones(rec, data)):
            for other in data.customers_by_phone.get(phone, ()):
                if other["record_id"] != rid and parse_date(other.get("dob")) == dob:
                    yield other["record_id"], "phone+dob"
    for check in approved_checks(rid, data):
        doc = norm_key(check.get("document_number"))
        if not doc:
            continue
        for other_check in data.kyc_by_document.get(doc, ()):
            if not is_approved(other_check):
                continue
            for o in data.onboarding_by_applicant.get(other_check.get("applicant_id"), ()):
                if o.get("customer_id") and o["customer_id"] != rid and o["customer_id"] in data.customers:
                    yield o["customer_id"], "document"


def group_into_persons(records, data, path) -> list:
    """Group the fitting records into persons; pull in every record linked to them.

    Returns a list of record lists, one per person, sorted by first record_id.
    """
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    queue = sorted(r["record_id"] for r in records)
    for rid in queue:
        parent[rid] = rid
    seen = set(queue)
    i = 0
    while i < len(queue):
        rid = queue[i]
        i += 1
        for other, _why in _same_person_links(data.customers[rid], data):
            if other not in parent:
                parent[other] = other
            union(rid, other)
            if other not in seen:
                seen.add(other)
                queue.append(other)

    groups = {}
    for rid in sorted(parent):
        groups.setdefault(find(rid), []).append(rid)
    persons = sorted(groups.values(), key=lambda ids: ids[0])

    merged = [ids for ids in persons if len(ids) > 1]
    if merged:
        path.append("same phone and date of birth, or same document number on approved checks -> "
                    + "; ".join("one person: " + ", ".join(ids) for ids in merged))
    if len(persons) > 1:
        path.append(f"{len(persons)} different people fit (records "
                    + ", ".join(r for ids in persons for r in ids) + "); each is decided separately")
    return [[data.customers[r] for r in ids] for ids in persons]


# --- building persons -----------------------------------------------------------------

def _date_key(d):
    """Sort key for a PartialDate (unknown parts sort first)."""
    if d is None:
        return (0, 0, 0)
    return (d.year or 0, d.month or 0, d.day or 0)


def _notes_for(rec, data) -> list:
    return data.notes_by_email.get(norm_key(rec.get("email")), []) if rec.get("email") else []


def _parsed_kyc_note(note):
    """Parse once per note (several alerts can resolve to the same customer)."""
    cache = _parsed_kyc_note.cache
    key = (note["note_id"], note.get("text"), note.get("created_at"), note.get("channel"), llm.enabled())
    if key not in cache:
        parsed = None
        text = note.get("text") or ""
        is_kyc = str(note.get("channel") or "").casefold() == "kyc"
        p = notes_parse.parse_kyc_note(text, note.get("created_at"))
        # Outside the kyc channel, only a note that clearly records a check counts.
        if p and (is_kyc or (p["dob"] and p["name"] and (p["provider"] or p["doc_type"]))):
            parsed = p
        # LLM fallback (only with --llm): fill what the regex could not read in a kyc note.
        # Values the regex did read are kept; the LLM's values are verified against the text.
        if is_kyc and llm.enabled() and (parsed is None or not parsed.get("name")
                                         or not parsed.get("dob") or not parsed.get("result")):
            extra = llm.extract_kyc_note(text, note.get("created_at"))
            if extra:
                parsed = dict(extra) if parsed is None else {
                    k: (parsed.get(k) if parsed.get(k) is not None else extra.get(k)) for k in extra}
        cache[key] = parsed
    return cache[key]


_parsed_kyc_note.cache = {}


def verified_checks(records, data) -> list:
    """Every APPROVED identity check of the person, newest first, as dicts:
    {source_id, origin, checked_at, name, dob, doc_country}. KYC table and kyc notes alike.
    Rejected, expired or unreadable results are not evidence.
    """
    checks = []
    for rec in records:
        for c in approved_checks(rec["record_id"], data):
            checks.append({
                "source_id": c["check_id"], "origin": "verified_kyc",
                "checked_at": parse_date(c.get("checked_at")),
                "name": c.get("verified_name") or None,
                "dob": parse_date(c.get("verified_dob")),
                "doc_country": to_country(c.get("document_country")),
                "doc_country_raw": c.get("document_country"),
            })
        for note in _notes_for(rec, data):
            p = _parsed_kyc_note(note)
            if not p or p.get("result") != "approved":
                continue
            checks.append({
                "source_id": note["note_id"], "origin": "verified_note",
                "checked_at": p.get("checked_at") or parse_date(note.get("created_at")),
                "name": p.get("name"),
                "dob": p.get("dob"),
                "doc_country": p.get("doc_country"),
            })
    # newest first; ties broken by source kind and ID so the order never depends on input order
    checks.sort(key=lambda c: (_date_key(c["checked_at"]), c["origin"] == "verified_kyc", c["source_id"]),
                reverse=True)
    return checks


def _person_from_records(records, data) -> Person:
    """One Person from records already known to be the same person.

    Declared facts come from every record. The verified name, date of birth and
    document country come from the most recent approved identity check (KYC table or
    kyc note); a field the newest check does not give is taken from the next newest.
    Countries: residence and nationality on all records, the verified document country,
    and countries the notes say the customer lived or worked in.
    """
    records = sorted(records, key=lambda r: r["record_id"])
    declared_names, declared_dobs, countries = [], [], []
    unresolved = []   # places we could not tie to a country: location then cannot clear (HANDOFF P1)
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
            elif normalize.is_unresolved_place(r.get(f)):
                unresolved.append(f"{r.get(f)} ({rid})")

    checks = verified_checks(records, data)

    def newest(field):
        for c in checks:
            if c[field]:
                return Fact(c[field], c["source_id"], c["origin"])
        return None

    verified_name, verified_dob, doc_country = newest("name"), newest("dob"), newest("doc_country")
    if doc_country:
        countries.append(Fact(doc_country.value, doc_country.source_id, "document_country"))
    if checks and not checks[0]["doc_country"] and normalize.is_unresolved_place(checks[0].get("doc_country_raw")):
        unresolved.append(f"{checks[0]['doc_country_raw']} ({checks[0]['source_id']})")

    for r in records:
        for note in _notes_for(r, data):
            if str(note.get("channel") or "").casefold() == "kyc":
                continue
            text = note.get("text") or ""
            found = notes_parse.parse_residence_note(text)
            if not found and llm.enabled() and notes_parse.looks_like_residence(text):
                found = llm.extract_residence_countries(text)
            for c in found:
                countries.append(Fact(c, note["note_id"], "residence_note"))
            if not found and notes_parse.looks_like_residence(text):
                # The note says where they lived, but names no place we can tie to a country.
                unresolved.append(f"the place named in {note['note_id']}")

    # drop exact repeats (e.g. the same residence note read twice), keep order stable
    seen, unique = set(), []
    for f in countries:
        if f not in seen:
            seen.add(f)
            unique.append(f)

    types = sorted({r.get("entity_type") for r in records if r.get("entity_type")})
    return Person(
        record_ids=[r["record_id"] for r in records],
        entity_type=types[0] if types else "",
        verified_name=verified_name,
        verified_dob=verified_dob,
        declared_names=declared_names,
        declared_dobs=declared_dobs,
        countries=unique,
        unresolved_places=sorted(set(unresolved)),
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

    groups = group_into_persons(chosen, data, path) if chosen else []
    persons = [_person_from_records(records, data) for records in groups]
    return Resolution(alert_id=alert["alert_id"], persons=persons, path=path)
