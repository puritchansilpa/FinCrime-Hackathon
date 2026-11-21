"""[Workstream A] Load the data folder's JSON Lines files and build lookup indexes.

Reads the official data room format (screening/dev/) and stays robust to other shapes,
including our earlier rebuilt dev/ files:
  - the screened customer may be nested ("customer": {...}) or flat; it ends up flat;
  - name_variants.json may use "groups" (official) or "name_variants";
  - list fields may be JSON arrays or "; "-joined strings (both become lists);
  - hits may be in hits.jsonl, embedded in alerts ("hits": [...]), or both;
  - any file may be missing (it loads as empty, with a warning on stderr).

Every index maps a key to a *sorted list*, so iteration order never depends on
file order or hashing (needed for run-to-run determinism).
"""
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

# Fields that hold lists. In our rebuilt dev/ they are "; "-joined strings.
LIST_FIELDS = {
    "alerts": ("hit_ids",),
    "hits": ("aliases", "dobs", "nationality", "citizenship", "countries", "addresses",
             "identifiers", "categories", "sources", "source_urls", "relationships"),
    "practice_labels": ("reason_codes", "customer_record_ids", "evidence"),
}

FILES = ("alerts", "hits", "customers", "accounts", "onboarding", "kyc_checks",
         "notes", "search_results", "practice_labels")


# --- small helpers (also used by other modules) ---------------------------------

def as_list(value) -> list:
    """A JSON array, a "; "-joined string, a single value or None -> list of non-empty items."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    elif isinstance(value, str):
        items = value.split(";")
    else:
        items = [value]
    out = []
    for item in items:
        if isinstance(item, str):
            item = item.strip()
            if not item:
                continue
        elif item is None:
            continue
        out.append(item)
    return out


def norm_key(value) -> str:
    """Case- and whitespace-insensitive key for emails, logins and account refs."""
    return str(value).strip().casefold() if value is not None else ""


def phone_key(value) -> str:
    """Digits only, so '+34 672 768 027' and '+34672768027' meet."""
    return re.sub(r"\D", "", str(value)) if value else ""


def name_tokens(value) -> list:
    """Lowercase, accent-free alphanumeric tokens of a name, for the search index only.

    (Real name comparison is Workstream B's names.py; this is just to find candidates.)
    """
    if not value:
        return []
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return [t for t in re.split(r"[^0-9a-z]+", text) if len(t) >= 2]


def read_jsonl(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"warning: {os.path.basename(path)} line {lineno}: {exc}", file=sys.stderr)
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _load_rows(folder: str, name: str) -> list:
    path = os.path.join(folder, name + ".jsonl")
    if not os.path.exists(path):
        print(f"warning: {name}.jsonl not found in {folder}", file=sys.stderr)
        return []
    rows = read_jsonl(path)
    for row in rows:
        for fld in LIST_FIELDS.get(name, ()):
            if fld in row:
                row[fld] = as_list(row[fld])
    return rows


# The screened customer on an alert. The official files nest it as
# {"customer": {"name", "entity_type", "dob", "country", "city"}}; our rebuilt files had
# it flat as customer_name, entity_type, dob, country, city. Both end up flat.
SCREENED_FIELDS = {"name": "customer_name", "customer_name": "customer_name", "full_name": "customer_name",
                   "entity_type": "entity_type", "type": "entity_type", "dob": "dob",
                   "date_of_birth": "dob", "country": "country", "city": "city"}


def _flatten_screened(alert: dict) -> None:
    screened = alert.get("customer")
    if not isinstance(screened, dict):
        return
    for src, dst in SCREENED_FIELDS.items():
        if src in screened and alert.get(dst) in (None, ""):
            alert[dst] = screened[src]


def normalise_variants(loaded) -> dict:
    """name_variants.json in any shape -> {"name_variants": [[...]], "company_legal_forms": [...]}.

    The official file is {"description", "groups": [[...]], "company_legal_forms": [...]};
    our rebuilt one used "name_variants"; a bare list of groups is accepted too.
    The original keys are kept alongside.
    """
    if isinstance(loaded, list):
        return {"name_variants": loaded, "groups": loaded, "company_legal_forms": []}
    if not isinstance(loaded, dict):
        return {"name_variants": [], "groups": [], "company_legal_forms": []}
    out = dict(loaded)
    groups = loaded.get("groups") or loaded.get("name_variants") or loaded.get("variants") or []
    out["name_variants"] = groups
    out["groups"] = groups
    out["company_legal_forms"] = loaded.get("company_legal_forms") or loaded.get("legal_forms") or []
    return out


def _index(rows, key_fn, sort_key) -> dict:
    idx = defaultdict(list)
    for row in rows:
        keys = key_fn(row)
        if isinstance(keys, str):
            keys = [keys]
        for k in keys or ():
            if k:
                idx[k].append(row)
    return {k: sorted(v, key=sort_key) for k, v in idx.items()}


def _s(value) -> str:
    return "" if value is None else str(value)


# --- the loaded dataset -----------------------------------------------------------

@dataclass
class Data:
    folder: str
    alerts: list = field(default_factory=list)              # sorted by alert_id
    hits: dict = field(default_factory=dict)                # hit_id -> row
    customers: dict = field(default_factory=dict)           # record_id -> row
    kyc_checks: dict = field(default_factory=dict)          # check_id -> row
    notes: dict = field(default_factory=dict)               # note_id -> row
    search_results: dict = field(default_factory=dict)      # result_id -> row
    practice_labels: list = field(default_factory=list)
    policy_text: str = ""
    name_variants: dict = field(default_factory=dict)

    # indexes: key -> sorted list of rows
    accounts_by_id: dict = field(default_factory=dict)          # account_id -> [account] (joint = several)
    accounts_by_login: dict = field(default_factory=dict)       # login_handle -> [account]
    accounts_by_customer: dict = field(default_factory=dict)    # customer_id -> [account]
    onboarding_by_account: dict = field(default_factory=dict)   # account_id -> [onboarding]
    onboarding_by_customer: dict = field(default_factory=dict)  # customer_id -> [onboarding]
    onboarding_by_applicant: dict = field(default_factory=dict) # kyc_applicant_id -> [onboarding]
    kyc_by_applicant: dict = field(default_factory=dict)        # applicant_id -> [check] by checked_at
    kyc_by_document: dict = field(default_factory=dict)         # document_number -> [check]
    customers_by_email: dict = field(default_factory=dict)      # email -> [customer]
    customers_by_phone: dict = field(default_factory=dict)      # digits -> [customer] (customer + account phones)
    customers_by_name_token: dict = field(default_factory=dict) # token -> [customer]
    notes_by_email: dict = field(default_factory=dict)          # email -> [note] by created_at
    search_by_query: dict = field(default_factory=dict)         # query -> [result]
    customers_by_birth_year: dict = field(default_factory=dict) # year -> [customer]

    def hits_for_alert(self, alert: dict) -> list:
        """The alert's hit rows, sorted by hit_id (hits missing from hits.jsonl are skipped)."""
        return [self.hits[h] for h in sorted(set(alert.get("hit_ids") or [])) if h in self.hits]


def load_data(folder: str) -> Data:
    raw = {name: _load_rows(folder, name) for name in FILES}
    d = Data(folder=folder)

    # Hits: from hits.jsonl, plus any embedded in alerts (real files may do this).
    hits = {}
    for alert in raw["alerts"]:
        embedded = alert.pop("hits", None)
        if isinstance(embedded, list):
            for h in embedded:
                if isinstance(h, dict) and h.get("hit_id"):
                    for fld in LIST_FIELDS["hits"]:
                        if fld in h:
                            h[fld] = as_list(h[fld])
                    h.setdefault("alert_id", alert.get("alert_id"))
                    hits.setdefault(h["hit_id"], h)
                    if h["hit_id"] not in alert.get("hit_ids", []):
                        alert.setdefault("hit_ids", []).append(h["hit_id"])
    for h in raw["hits"]:
        if h.get("hit_id"):
            hits[h["hit_id"]] = h
    d.hits = dict(sorted(hits.items()))

    # Alerts: make sure hit_ids is a list and every hit that names an alert is in it.
    alerts = {a["alert_id"]: a for a in raw["alerts"] if a.get("alert_id")}
    for a in alerts.values():
        a["hit_ids"] = as_list(a.get("hit_ids"))
        _flatten_screened(a)
    for h in d.hits.values():
        a = alerts.get(h.get("alert_id"))
        if a is not None and h["hit_id"] not in a["hit_ids"]:
            a["hit_ids"].append(h["hit_id"])
    d.alerts = [alerts[k] for k in sorted(alerts)]

    d.customers = {c["record_id"]: c for c in sorted(raw["customers"], key=lambda r: _s(r.get("record_id")))
                   if c.get("record_id")}
    d.kyc_checks = {k["check_id"]: k for k in raw["kyc_checks"] if k.get("check_id")}
    d.notes = {n["note_id"]: n for n in raw["notes"] if n.get("note_id")}
    d.search_results = {r["result_id"]: r for r in raw["search_results"] if r.get("result_id")}
    d.practice_labels = raw["practice_labels"]

    by_account = lambda r: (_s(r.get("account_id")), _s(r.get("customer_id")))
    d.accounts_by_id = _index(raw["accounts"], lambda r: norm_key(r.get("account_id")), by_account)
    d.accounts_by_login = _index(raw["accounts"], lambda r: norm_key(r.get("login_handle")), by_account)
    d.accounts_by_customer = _index(raw["accounts"], lambda r: _s(r.get("customer_id")), by_account)
    d.onboarding_by_account = _index(raw["onboarding"], lambda r: norm_key(r.get("account_id")), by_account)
    d.onboarding_by_customer = _index(raw["onboarding"], lambda r: _s(r.get("customer_id")), by_account)
    d.onboarding_by_applicant = _index(raw["onboarding"], lambda r: _s(r.get("kyc_applicant_id")), by_account)

    by_check = lambda r: (_s(r.get("checked_at")), _s(r.get("check_id")))
    d.kyc_by_applicant = _index(raw["kyc_checks"], lambda r: _s(r.get("applicant_id")), by_check)
    d.kyc_by_document = _index(raw["kyc_checks"], lambda r: norm_key(r.get("document_number")), by_check)

    customers = list(d.customers.values())
    by_record = lambda r: _s(r.get("record_id"))
    d.customers_by_email = _index(customers, lambda r: norm_key(r.get("email")), by_record)
    d.customers_by_name_token = _index(
        customers,
        lambda r: sorted({t for f in ("full_name", "preferred_name", "login_name")
                          for t in name_tokens(r.get(f))}),
        by_record,
    )
    # Phones live on customer records and on accounts; index both, pointing at customers.
    phones = defaultdict(set)
    for c in customers:
        if phone_key(c.get("phone")):
            phones[phone_key(c.get("phone"))].add(c["record_id"])
    for acc in raw["accounts"]:
        if phone_key(acc.get("phone")) and acc.get("customer_id") in d.customers:
            phones[phone_key(acc.get("phone"))].add(acc["customer_id"])
    d.customers_by_phone = {k: [d.customers[r] for r in sorted(v)] for k, v in phones.items()}

    d.notes_by_email = _index(raw["notes"], lambda r: norm_key(r.get("requester_email")),
                              lambda r: (_s(r.get("created_at")), _s(r.get("note_id"))))
    d.search_by_query = _index(raw["search_results"], lambda r: norm_key(r.get("query")),
                               lambda r: _s(r.get("result_id")))

    # Birth-year buckets: a second way to find search candidates whose name has typos
    # in every part (the name-token index would miss them).
    from . import fallbacks
    years = defaultdict(list)
    for c in customers:
        dob = fallbacks.parse_date(c.get("dob"))
        if dob is not None and dob.year is not None:
            years[dob.year].append(c)
    d.customers_by_birth_year = dict(years)

    policy = os.path.join(folder, "POLICY.md")
    if os.path.exists(policy):
        with open(policy, encoding="utf-8-sig") as fh:
            d.policy_text = fh.read()
    variants = os.path.join(folder, "name_variants.json")
    if os.path.exists(variants):
        with open(variants, encoding="utf-8-sig") as fh:
            loaded = json.load(fh)
        d.name_variants = normalise_variants(loaded)
    fallbacks.configure(d.name_variants)
    return d
