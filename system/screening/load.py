"""Read a data room folder (JSON Lines) and build the indexes both workstreams use.  [Workstream A]

load_data(folder) -> Data. Reads only that folder. Missing files load as empty, so a run
never crashes on a partial folder; affected hits fall back to REVIEW.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from .names import Variants
from .normalize import search_query


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _key(s) -> str:
    return (s or "").strip().lower()


@dataclass
class Data:
    folder: Path
    alerts: List[dict] = field(default_factory=list)
    hits: List[dict] = field(default_factory=list)
    customers: Dict[str, dict] = field(default_factory=dict)                  # record_id -> row
    accounts_by_id: Dict[str, List[dict]] = field(default_factory=dict)       # account_id -> rows (joint holders)
    accounts_by_login: Dict[str, List[dict]] = field(default_factory=dict)    # login_handle (lower) -> rows
    accounts_by_customer: Dict[str, List[dict]] = field(default_factory=dict)
    onboarding: Dict[Tuple[str, str], List[str]] = field(default_factory=dict)  # (account_id, customer_id) -> applicant IDs
    kyc_by_applicant: Dict[str, List[dict]] = field(default_factory=dict)
    customers_by_email: Dict[str, List[str]] = field(default_factory=dict)    # email (lower) -> record IDs
    notes_by_email: Dict[str, List[dict]] = field(default_factory=dict)       # requester_email (lower) -> notes
    search_by_query: Dict[str, List[dict]] = field(default_factory=dict)      # normalised query -> results
    variants: Variants = field(default_factory=Variants)


def load_data(folder) -> Data:
    folder = Path(folder)
    d = Data(folder=folder)
    d.alerts = read_jsonl(folder / "alerts.jsonl")
    d.hits = read_jsonl(folder / "hits.jsonl")
    d.variants = Variants.load(folder)

    for c in read_jsonl(folder / "customers.jsonl"):
        d.customers[c["record_id"]] = c
    by_email = defaultdict(list)
    for rid in sorted(d.customers):
        e = _key(d.customers[rid].get("email"))
        if e:
            by_email[e].append(rid)
    d.customers_by_email = dict(by_email)

    by_id, by_login, by_cus = defaultdict(list), defaultdict(list), defaultdict(list)
    for a in read_jsonl(folder / "accounts.jsonl"):
        by_id[a["account_id"]].append(a)
        if a.get("login_handle"):
            by_login[_key(a["login_handle"])].append(a)
        by_cus[a["customer_id"]].append(a)
    d.accounts_by_id, d.accounts_by_login, d.accounts_by_customer = dict(by_id), dict(by_login), dict(by_cus)

    onb = defaultdict(list)
    for o in read_jsonl(folder / "onboarding.jsonl"):
        if o.get("kyc_applicant_id"):
            onb[(o["account_id"], o["customer_id"])].append(o["kyc_applicant_id"])
    d.onboarding = dict(onb)

    kyc = defaultdict(list)
    for k in read_jsonl(folder / "kyc_checks.jsonl"):
        kyc[k["applicant_id"]].append(k)
    d.kyc_by_applicant = dict(kyc)

    notes = defaultdict(list)
    for n in read_jsonl(folder / "notes.jsonl"):
        notes[_key(n.get("requester_email"))].append(n)
    d.notes_by_email = {k: sorted(v, key=lambda n: n["note_id"]) for k, v in notes.items()}

    search = defaultdict(list)
    for r in read_jsonl(folder / "search_results.jsonl"):
        search[search_query(r.get("query") or "")].append(r)
    d.search_by_query = {k: sorted(v, key=lambda r: r["result_id"]) for k, v in search.items()}
    return d
