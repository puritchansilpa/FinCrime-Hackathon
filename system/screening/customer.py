"""Who the customer is: alert -> Resolution.  [Workstream A]

PLACEHOLDER so the official pipeline runs end to end. Workstream A replaces this file
(PLAN.md 6.2, steps A2-A6). What it does today:
  - follows the alert's link: account_ref -> accounts, login_handle -> accounts, email -> customers
  - filters joint holders / several records with the screened name and date of birth
  - builds one Person per record from the record plus its latest APPROVED KYC-table check
  - reads kyc notes as verified checks and residence notes as countries, by structure
    rather than wording (see _parse_kyc_note / _residence_countries)
What it does NOT do yet (A's work):
  - search for alerts without a link (they resolve to nobody -> REVIEW)
  - group records into one person (same phone + full DOB, same document number)
"""

import re
from typing import List, Optional, Tuple

from .models import Fact, PartialDate, Person, Resolution
from .names import names_agree
from .normalize import dates_compatible, find_countries, fold, parse_date, screened_details, to_country

# ---------------------------------------------------------------------------
# Notes (placeholder parsers, structure-based so reworded notes still parse)
# ---------------------------------------------------------------------------

_NEGATIVE = re.compile(r"\b(reject\w*|fail\w*|declin\w*|unsuccessful\w*|expir\w*|could not|couldn't|"
                       r"unable|not (?:be )?(?:verified|validated|confirmed|approved)|mismatch\w*|invalid|"
                       r"denied|refused|suspicious|fraudulent)\b", re.I)
_RESIDENCE = re.compile(r"\b(liv(?:ed|es|ing)|resid\w*|home|stay(?:ed|ing)?|based|relocat\w*|moved|"
                        r"worked and lived|employment and residency)\b", re.I)
_MONTHS = (r"January|February|March|April|May|June|July|August|September|October|November|December|"
           r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec")
_DATE_IN_TEXT = re.compile(
    r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}[/.]\d{1,2}[/.]\d{4}\b|"
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:" + _MONTHS + r")\.?,?\s+\d{4}\b|"
    r"\b(?:" + _MONTHS + r")\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b", re.I)
_NOT_NAME = {"DOB", "ID", "KYC", "AML", "UK", "USA", "US", "UAE", "EU", "PEP", "OK", "N/A", "NA"}


def _upper_name(text: str) -> Optional[str]:
    """Longest run of 2+ consecutive fully upper-case words (Unicode-aware): 'MILAN SETFANOVIĆ'."""
    best, run = None, []
    for tok in re.findall(r"[^\s,;:()]+", text) + [""]:
        core = tok.strip(".'\"")
        if core and core.upper() == core and any(ch.isalpha() for ch in core) and core not in _NOT_NAME \
                and not any(ch.isdigit() for ch in core):
            run.append(core)
            continue
        if len(run) >= 2 and (best is None or len(run) > len(best)):
            best = list(run)
        run = []
    return " ".join(best) if best else None


def _key(d: PartialDate) -> Tuple[int, int, int]:
    return (d.year or 0, d.month or 0, d.day or 0)


def _parse_kyc_note(note: dict) -> Optional[dict]:
    """A verification written up as a note: name, dob, document country, check date.
    The check date is the note's date (or the latest date in it); the other date is the DOB."""
    text = note.get("text") or ""
    if _NEGATIVE.search(text):
        return None                       # rejected / failed / expired checks are not evidence
    created = parse_date(note.get("created_at"))
    dates = []
    for m in _DATE_IN_TEXT.finditer(text):
        d = parse_date(re.sub(r"(\d)(st|nd|rd|th)", r"\1", m.group(0)))
        if d and d not in dates:
            dates.append(d)
    checked = created or (max(dates, key=_key) if dates else None)
    others = [d for d in dates if d != checked]
    dob = min(others, key=_key) if others else None
    name = _upper_name(text)
    countries = find_countries(text, ignore_names=[name] if name else [])
    return {"name": name, "dob": dob, "doc_country": countries[0] if countries else None, "checked": checked}


def _residence_countries(note: dict) -> List[str]:
    text = note.get("text") or ""
    return find_countries(text) if _RESIDENCE.search(text) else []


def _linked_records(alert: dict, data) -> (List[str], List[str]):
    path = []
    if alert.get("account_ref"):
        rows = data.accounts_by_id.get(alert["account_ref"], [])
        rids = sorted({r["customer_id"] for r in rows})
        path.append(f"account_ref {alert['account_ref']} -> accounts -> {', '.join(rids) or 'nobody'}")
        return rids, path
    if alert.get("login_handle"):
        rows = data.accounts_by_login.get(alert["login_handle"].strip().lower(), [])
        rids = sorted({r["customer_id"] for r in rows})
        path.append(f"login_handle {alert['login_handle']} -> accounts -> {', '.join(rids) or 'nobody'}")
        return rids, path
    if alert.get("email"):
        rids = list(data.customers_by_email.get(alert["email"].strip().lower(), []))
        path.append(f"email {alert['email']} -> customers -> {', '.join(rids) or 'nobody'}")
        return rids, path
    path.append("no link on the alert (search not implemented yet)")
    return [], path


def _fits_screened(rid: str, sc: dict, data) -> bool:
    c = data.customers.get(rid, {})
    company = (c.get("entity_type") or "").lower() == "company"
    names = [c.get(k) for k in ("full_name", "preferred_name", "login_name") if c.get(k)]
    if sc.get("name") and names and not any(names_agree(sc["name"], n, data.variants, company) for n in names):
        return False
    sdob, cdob = parse_date(sc.get("dob")), parse_date(c.get("dob"))
    if sdob and cdob and not dates_compatible(sdob, cdob):
        return False
    return True


def _latest_approved_check(rid: str, data) -> Optional[dict]:
    best = None
    for acc in data.accounts_by_customer.get(rid, []):
        for app in data.onboarding.get((acc["account_id"], rid), []):
            for k in data.kyc_by_applicant.get(app, []):
                if (k.get("result") or "").lower() != "approved":
                    continue
                when = parse_date(k.get("checked_at"))
                key = ((when.year, when.month or 0, when.day or 0) if when else (0, 0, 0), k["check_id"])
                if best is None or key > best[0]:
                    best = (key, k)
    return best[1] if best else None


def build_person(rids: List[str], data) -> Person:
    rids = sorted(rids)
    first = data.customers.get(rids[0], {})
    p = Person(record_ids=rids, entity_type=first.get("entity_type") or "")
    checks = []   # (date key, source id, name, dob, document country) for every approved check
    for rid in rids:
        c = data.customers.get(rid, {})
        for k in ("full_name", "preferred_name", "login_name"):
            if c.get(k):
                p.declared_names.append(Fact(c[k], rid, "record"))
        d = parse_date(c.get("dob"))
        if d:
            p.declared_dobs.append(Fact(d, rid, "record"))
        for k in ("residence_country", "nationality"):
            cc = to_country(c.get(k))
            if cc:
                p.countries.append(Fact(cc, rid, "record"))
        k = _latest_approved_check(rid, data)
        if k:
            when = parse_date(k.get("checked_at"))
            checks.append((_key(when) if when else (0, 0, 0), k["check_id"], k.get("verified_name"),
                           parse_date(k.get("verified_dob")), to_country(k.get("document_country")), "verified_kyc"))
        email = (c.get("email") or "").strip().lower()
        for n in data.notes_by_email.get(email, []) if email else []:
            if (n.get("channel") or "").lower() == "kyc":
                r = _parse_kyc_note(n)
                if r and r["checked"]:
                    checks.append((_key(r["checked"]), n["note_id"], r["name"], r["dob"], r["doc_country"],
                                   "verified_note"))
            else:
                for cc in _residence_countries(n):
                    p.countries.append(Fact(cc, n["note_id"], "residence_note"))
    if checks:
        _, sid, name, dob, dc, origin = max(checks, key=lambda c: (c[0], c[1]))
        if name:
            p.verified_name = Fact(name, sid, origin)
        if dob:
            p.verified_dob = Fact(dob, sid, origin)
        if dc:
            p.countries.append(Fact(dc, sid, origin))
    return p


def resolve(alert: dict, data) -> Resolution:
    rids, path = _linked_records(alert, data)
    rids = [r for r in rids if r in data.customers]
    if len(rids) > 1:
        sc = screened_details(alert)
        fitting = [r for r in rids if _fits_screened(r, sc, data)]
        if fitting and len(fitting) < len(rids):
            path.append(f"the screened name and date of birth fit {', '.join(fitting)}")
            rids = fitting
    persons = [build_person([r], data) for r in rids]
    return Resolution(alert_id=alert.get("alert_id") or "", persons=persons, path=path)
