#!/usr/bin/env python3
"""Validate the adversarial set and score the current pipeline on it.

    python3 adversarial/run.py

Uses system/run (the merged pipeline on this branch). Stdlib only.
Prints decision accuracy, wrong DIFFERENT_ENTITY count, and misses by category.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "adversarial")

FILES = {
    "alerts.jsonl": "alert_id",
    "hits.jsonl": "hit_id",
    "customers.jsonl": "record_id",
    "accounts.jsonl": "account_id",
    "onboarding.jsonl": "kyc_applicant_id",
    "kyc_checks.jsonl": "check_id",
    "notes.jsonl": "note_id",
    "search_results.jsonl": "result_id",
}
CODES = {
    "TEMPORAL_IMPOSSIBILITY": "DIFFERENT_ENTITY",
    "DOB_MISMATCH": "DIFFERENT_ENTITY",
    "LOCATION_MISMATCH": "DIFFERENT_ENTITY",
    "NAME_MISMATCH_VERIFIED": "DIFFERENT_ENTITY",
    "ENTITY_TYPE_MISMATCH": "DIFFERENT_ENTITY",
    "DECEASED": "DIFFERENT_ENTITY",
    "NAME_DOB_LOCATION_MATCH": "SAME_ENTITY",
    "NAME_DOB_MATCH": "SAME_ENTITY",
    "NAME_LOCATION_MATCH": "SAME_ENTITY",
    "INSUFFICIENT_DATA": "REVIEW",
    "AMBIGUOUS_CUSTOMER_RECORD": "REVIEW",
}
DECISIONS = ("DIFFERENT_ENTITY", "SAME_ENTITY", "REVIEW")
COST = {
    "DIFFERENT_ENTITY": {"DIFFERENT_ENTITY": 0, "SAME_ENTITY": 3, "REVIEW": 3},
    "SAME_ENTITY": {"DIFFERENT_ENTITY": 60, "SAME_ENTITY": 0, "REVIEW": 2},
    "REVIEW": {"DIFFERENT_ENTITY": 60, "SAME_ENTITY": 2, "REVIEW": 0},
}


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit("%s:%s: %s" % (os.path.basename(path), number, exc))
    return rows


def split_ids(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(";") if part.strip()]


def validate():
    tables = {}
    ids = {}
    errors = []
    for name, key in FILES.items():
        rows = read_jsonl(os.path.join(DATA, name))
        tables[name] = rows
        for row in rows:
            ident = row.get(key)
            if not ident or not str(ident).startswith("ADV-"):
                errors.append("%s has a non-ADV %s: %r" % (name, key, ident))
                continue
            bucket = ids.setdefault(key, {})
            if ident in bucket and key != "account_id":
                errors.append("duplicate %s %s" % (key, ident))
            bucket.setdefault(ident, row)

    hits = {r["hit_id"]: r for r in tables["hits.jsonl"]}
    alerts = {r["alert_id"]: r for r in tables["alerts.jsonl"]}
    customers = {r["record_id"]: r for r in tables["customers.jsonl"]}
    accounts = {}
    for row in tables["accounts.jsonl"]:
        accounts.setdefault(row["account_id"], []).append(row)
    logins = {}
    for row in tables["accounts.jsonl"]:
        if row.get("login_handle"):
            logins.setdefault(row["login_handle"].casefold(), []).append(row)
    emails = {}
    for row in tables["customers.jsonl"]:
        if row.get("email"):
            emails.setdefault(row["email"].casefold(), []).append(row)
    applicants = {r["kyc_applicant_id"] for r in tables["onboarding.jsonl"]}
    known = set()
    for key, bucket in ids.items():
        known |= set(bucket)

    for alert in alerts.values():
        for hid in split_ids(alert.get("hit_ids")):
            if hid not in hits:
                errors.append("%s cites missing hit %s" % (alert["alert_id"], hid))
            elif hits[hid].get("alert_id") != alert["alert_id"]:
                errors.append("%s alert_id is %s" % (hid, hits[hid].get("alert_id")))
        ref = alert.get("account_ref")
        if ref and ref not in accounts:
            errors.append("%s account_ref %s missing" % (alert["alert_id"], ref))
        login = alert.get("login_handle")
        if login and login.casefold() not in logins:
            errors.append("%s login %s missing" % (alert["alert_id"], login))

    for row in tables["accounts.jsonl"]:
        if row.get("customer_id") not in customers:
            errors.append("%s customer %s missing" % (row["account_id"], row.get("customer_id")))
    for row in tables["onboarding.jsonl"]:
        if row.get("customer_id") not in customers:
            errors.append("onboarding customer %s missing" % row.get("customer_id"))
        if row.get("account_id") not in accounts:
            errors.append("onboarding account %s missing" % row.get("account_id"))
    for row in tables["kyc_checks.jsonl"]:
        if row.get("applicant_id") not in applicants:
            errors.append("%s applicant %s missing" % (row["check_id"], row.get("applicant_id")))
    for row in tables["notes.jsonl"]:
        if (row.get("requester_email") or "").casefold() not in emails:
            errors.append("%s email matches no customer" % row["note_id"])

    labels = read_jsonl(os.path.join(DATA, "practice_labels.jsonl"))
    seen = set()
    for row in labels:
        hid = row.get("hit_id")
        where = hid or "?"
        if hid not in hits:
            errors.append("label for unknown hit %s" % hid)
            continue
        if hid in seen:
            errors.append("duplicate label %s" % hid)
        seen.add(hid)
        if row.get("alert_id") != hits[hid].get("alert_id"):
            errors.append("%s alert_id does not match the hit" % where)
        decision = row.get("decision")
        if decision not in DECISIONS:
            errors.append("%s bad decision %r" % (where, decision))
        codes = split_ids(row.get("reason_codes"))
        if not codes:
            errors.append("%s has no reason code" % where)
        for code in codes:
            if CODES.get(code) != decision:
                errors.append("%s code %s does not belong to %s" % (where, code, decision))
        if not (row.get("reference_reason") or "").strip():
            errors.append("%s has no reference_reason" % where)
        if not (row.get("path") or "").strip():
            errors.append("%s has no path" % where)
        if not (row.get("category") or "").strip() or not (row.get("weakness") or "").strip():
            errors.append("%s missing category or weakness" % where)
        if row.get("naive_decision") not in DECISIONS:
            errors.append("%s bad naive_decision" % where)
        cust = row.get("customer_record_ids")
        if cust not in (None, "AMBIGUOUS"):
            for cid in split_ids(cust):
                if cid not in customers:
                    errors.append("%s customer %s missing" % (where, cid))
        elif decision != "REVIEW" and cust is None:
            errors.append("%s is %s with no customer" % (where, decision))
        for evid in split_ids(row.get("evidence")):
            if evid not in known:
                errors.append("%s evidence %s missing" % (where, evid))
        if row.get("ambiguous_policy") is True and not (row.get("ambiguous_policy_note") or "").strip():
            errors.append("%s ambiguous_policy without a note" % where)

    missing = sorted(set(hits) - seen)
    if missing:
        errors.append("hits with no label: %s" % ", ".join(missing))
    if errors:
        print("validation failed:", file=sys.stderr)
        for err in errors:
            print("  " + err, file=sys.stderr)
        raise SystemExit(1)
    print("validated %s hits, %s alerts, %s customers" % (len(hits), len(alerts), len(customers)))
    return labels


def run_pipeline(out_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(ROOT, "system") + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [os.path.join(ROOT, "system", "run"), DATA, out_path],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    if proc.stderr:
        print(proc.stderr.strip(), file=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit("system/run exited %s" % proc.returncode)
    return read_jsonl(out_path)


def customer_ok(label, predicted):
    gold = label.get("customer_record_ids")
    got = predicted.get("customer_record_id")
    if gold == "AMBIGUOUS":
        return got == "AMBIGUOUS"
    if gold is None:
        return got in (None, "")
    return got in split_ids(gold)


def score(labels, preds):
    by_hit = {row["hit_id"]: row for row in preds}
    categories = {}
    misses = []
    correct = wrong_de = reason_ok = customer_ok_n = 0
    cost = 0
    for label in sorted(labels, key=lambda r: r["hit_id"]):
        hid = label["hit_id"]
        pred = by_hit.get(hid)
        cat = label["category"]
        bucket = categories.setdefault(cat, {"n": 0, "miss": 0, "wrong_de": 0})
        bucket["n"] += 1
        if pred is None:
            bucket["miss"] += 1
            misses.append((hid, cat, label["decision"], "MISSING", "", label.get("title"), ""))
            cost += COST[label["decision"]]["REVIEW"]
            continue
        got = pred.get("decision")
        cost += COST[label["decision"]][got]
        if got == label["decision"]:
            correct += 1
            if pred.get("reason_code") in split_ids(label.get("reason_codes")):
                reason_ok += 1
        else:
            bucket["miss"] += 1
            misses.append((hid, cat, label["decision"], got, pred.get("reason_code"),
                           label.get("title"), label.get("module") or ""))
        if got == "DIFFERENT_ENTITY" and label["decision"] != "DIFFERENT_ENTITY":
            wrong_de += 1
            bucket["wrong_de"] += 1
        if customer_ok(label, pred):
            customer_ok_n += 1
    total = len(labels)
    print()
    print("pipeline: system/run on adversarial/")
    print("hits                 %s" % total)
    print("decision accuracy    %s/%s" % (correct, total))
    print("wrong DIFFERENT_ENTITY  %s" % wrong_de)
    print("reason code (when the decision is right)  %s/%s" % (reason_ok, correct or 0))
    print("customer id          %s/%s  (any record of that person counts)" % (customer_ok_n, total))
    print("decision cost        %s  (clearing a non-clear is 60)" % cost)
    print()
    print("category                         n  misses  wrong_DE")
    for cat in sorted(categories):
        row = categories[cat]
        print("  %-28s %3d %7d %9d" % (cat, row["n"], row["miss"], row["wrong_de"]))
    if misses:
        print()
        print("misses (gold -> pipeline)")
        for hid, cat, gold, got, code, title, module in misses:
            print("  %-10s %-18s %s -> %s %-22s  %s" % (
                hid, cat, gold, got, code or "", module or title or ""))
    return {"correct": correct, "total": total, "wrong_de": wrong_de, "misses": len(misses)}


def main():
    labels = validate()
    fd, out_path = tempfile.mkstemp(prefix="adv-", suffix=".jsonl")
    os.close(fd)
    try:
        preds = run_pipeline(out_path)
        if "--keep" in sys.argv:
            kept = os.path.join(DATA, "output", "predictions.jsonl")
            os.makedirs(os.path.dirname(kept), exist_ok=True)
            os.replace(out_path, kept)
            print("wrote %s" % kept, file=sys.stderr)
            out_path = None
    finally:
        if out_path and os.path.exists(out_path):
            os.remove(out_path)
    score(labels, preds)


if __name__ == "__main__":
    main()
