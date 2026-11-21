#!/usr/bin/env python3
"""Our own scorer for predictions against practice labels (until validate.py turns up).

Usage:
  python3 tools/score.py output/dev.jsonl dev/practice_labels.jsonl [--data dev] [--all] [--quiet]

Reports, in this order:
  1. format problems in the predictions file (and missing hits, if --data is given);
  2. the decision score from the brief's cost matrix, and every UNSAFE CLEARANCE;
  3. the reason checks on correct decisions: code, customer record, evidence, reason text;
  4. a per-hit diff for every labelled hit we got wrong (or all with --all), with the
     label's `path`, so it is clear whether it is a resolution bug (A) or a rules bug (B).

Exit code is 1 if there is any unsafe clearance or format error, else 0.
"""
import argparse
import json
import os
import re
import sys

DE, SAME, REV = "DIFFERENT_ENTITY", "SAME_ENTITY", "REVIEW"

# COST[truth][ours], from the brief.
COST = {
    DE:   {DE: 0,  SAME: 3, REV: 3},
    SAME: {DE: 60, SAME: 0, REV: 2},
    REV:  {DE: 60, SAME: 2, REV: 0},
}

REASON_CODES = {
    DE: {"TEMPORAL_IMPOSSIBILITY", "DOB_MISMATCH", "LOCATION_MISMATCH",
         "NAME_MISMATCH_VERIFIED", "ENTITY_TYPE_MISMATCH", "DECEASED"},
    SAME: {"NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH", "NAME_LOCATION_MATCH"},
    REV: {"INSUFFICIENT_DATA", "AMBIGUOUS_CUSTOMER_RECORD"},
}

OUTPUT_FIELDS = ("hit_id", "alert_id", "decision", "reason_code", "customer_record_id",
                 "reason", "evidence")


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(";") if v.strip()]


def read_jsonl(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for lineno, line in enumerate(fh, 1):
            if line.strip():
                try:
                    rows.append((lineno, json.loads(line)))
                except json.JSONDecodeError as exc:
                    rows.append((lineno, exc))
    return rows


def sentence_count(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])


def decision_score(cost: float, baseline: float) -> float:
    """Share of cost saved versus sending everything to REVIEW, floored at 0."""
    if baseline == 0:
        return 1.0 if cost == 0 else 0.0
    return max(0.0, 1.0 - cost / baseline)


# --- checks ------------------------------------------------------------------------

def check_format(pred_rows, hit_ids=None):
    """Return (predictions by hit_id, list of format problems)."""
    problems, preds = [], {}
    for lineno, row in pred_rows:
        if isinstance(row, Exception):
            problems.append(f"line {lineno}: not JSON ({row})")
            continue
        missing = [f for f in OUTPUT_FIELDS if f not in row]
        if missing:
            problems.append(f"line {lineno}: missing fields {missing}")
        hid = row.get("hit_id")
        if hid in preds:
            problems.append(f"line {lineno}: duplicate hit_id {hid}")
        dec, code = row.get("decision"), row.get("reason_code")
        if dec not in COST:
            problems.append(f"line {lineno} {hid}: bad decision {dec!r}")
        elif code not in REASON_CODES[dec]:
            problems.append(f"line {lineno} {hid}: reason_code {code!r} does not belong to {dec}")
        if not isinstance(row.get("evidence"), list):
            problems.append(f"line {lineno} {hid}: evidence must be a list")
        cid = row.get("customer_record_id")
        if cid is not None and not isinstance(cid, str):
            problems.append(f"line {lineno} {hid}: customer_record_id must be a string or null")
        if not isinstance(row.get("reason"), str) or not row.get("reason", "").strip():
            problems.append(f"line {lineno} {hid}: empty reason")
        preds[hid] = row
    if hit_ids is not None:
        absent = sorted(set(hit_ids) - set(preds))
        extra = sorted(set(preds) - set(hit_ids))
        if absent:
            problems.append(f"{len(absent)} hits have no prediction, e.g. {absent[:5]}")
        if extra:
            problems.append(f"{len(extra)} predictions are for unknown hits, e.g. {extra[:5]}")
    return preds, problems


def score(preds: dict, labels: list) -> dict:
    """Score predictions against labels. Returns totals and per-hit details."""
    cost = baseline = 0
    confusion = {t: {o: 0 for o in COST} for t in COST}
    unsafe, rows = [], []
    reason_checks = {"code": [], "customer": [], "evidence_exact": [], "reason_text": []}
    ev_precision, ev_recall = [], []

    for lab in labels:
        hid, truth = lab["hit_id"], lab["decision"]
        pred = preds.get(hid)
        ours = pred.get("decision") if pred else None
        if ours not in COST:
            ours = REV  # a missing or broken line counts as REVIEW
        c = COST[truth][ours]
        cost += c
        baseline += COST[truth][REV]
        confusion[truth][ours] += 1
        if ours == DE and truth != DE:
            unsafe.append(hid)

        detail = {"hit_id": hid, "truth": truth, "ours": ours, "cost": c, "label": lab,
                  "pred": pred, "problems": []}
        if pred is None:
            detail["problems"].append("no prediction")
        elif ours == truth:
            label_codes = set(as_list(lab.get("reason_codes")))
            code_ok = pred.get("reason_code") in label_codes
            label_ids = set(as_list(lab.get("customer_record_ids")))
            cid = pred.get("customer_record_id")
            cust_ok = (cid in label_ids) if label_ids else cid is None
            label_ev = set(as_list(lab.get("evidence")))
            our_ev = set(as_list(pred.get("evidence")))
            ev_ok = our_ev == label_ev
            reason = pred.get("reason") or ""
            text_ok = 2 <= sentence_count(reason) <= 4
            reason_checks["code"].append(code_ok)
            reason_checks["customer"].append(cust_ok)
            reason_checks["evidence_exact"].append(ev_ok)
            reason_checks["reason_text"].append(text_ok)
            if our_ev:
                ev_precision.append(len(our_ev & label_ev) / len(our_ev))
            else:
                ev_precision.append(1.0 if not label_ev else 0.0)
            ev_recall.append(len(our_ev & label_ev) / len(label_ev) if label_ev else 1.0)
            if not code_ok:
                detail["problems"].append(f"code {pred.get('reason_code')} not in {sorted(label_codes)}")
            if not cust_ok:
                detail["problems"].append(f"customer {cid} not in {sorted(label_ids) or [None]}")
            if not ev_ok:
                detail["problems"].append(
                    f"evidence missing {sorted(label_ev - our_ev)} extra {sorted(our_ev - label_ev)}")
            if not text_ok:
                detail["problems"].append(f"reason has {sentence_count(reason)} sentences (want 2-4)")
        else:
            detail["problems"].append(f"decision {ours}, want {truth}")
        rows.append(detail)

    def rate(xs):
        return sum(xs) / len(xs) if xs else 0.0

    reason_rates = {k: rate(v) for k, v in reason_checks.items()}
    # Our guess at the reason score: equal weight on the four checks.
    reason_score = rate(list(reason_rates.values())) if reason_checks["code"] else 0.0
    dscore = decision_score(cost, baseline)
    return {
        "n": len(labels),
        "cost": cost,
        "baseline": baseline,
        "decision_score": dscore,
        "raw_decision_score": 1.0 - cost / baseline if baseline else 0.0,
        "confusion": confusion,
        "unsafe": unsafe,
        "correct": sum(confusion[t][t] for t in COST),
        "reason_rates": reason_rates,
        "evidence_precision": rate(ev_precision),
        "evidence_recall": rate(ev_recall),
        "reason_score": reason_score,
        # Reasons are only checked on correct decisions, so scale them by accuracy.
        "combined": 0.75 * dscore + 0.25 * reason_score * (
            sum(confusion[t][t] for t in COST) / len(labels) if labels else 0),
        "rows": rows,
    }


# --- report ------------------------------------------------------------------------

def report(res: dict, problems: list, show_all: bool, quiet: bool) -> None:
    out = sys.stdout
    if problems:
        print(f"FORMAT PROBLEMS ({len(problems)}):", file=out)
        for p in problems[:30]:
            print(f"  - {p}", file=out)
        if len(problems) > 30:
            print(f"  ... and {len(problems) - 30} more", file=out)
        print(file=out)

    n = res["n"]
    print(f"Labelled hits: {n}   correct decisions: {res['correct']}/{n}", file=out)
    print(f"Decision score: {res['decision_score']:.3f}  (cost {res['cost']} vs all-REVIEW "
          f"{res['baseline']}; raw {res['raw_decision_score']:+.3f})", file=out)
    flag = "  <-- MUST BE 0" if res["unsafe"] else ""
    print(f"UNSAFE CLEARANCES: {len(res['unsafe'])}{flag}", file=out)
    for hid in res["unsafe"]:
        print(f"  ! {hid}", file=out)
    print(file=out)

    print("Confusion (rows = label, cols = ours):", file=out)
    print(f"  {'':18}{'DE':>6}{'SAME':>6}{'REV':>6}", file=out)
    for t, name in ((DE, "DIFFERENT_ENTITY"), (SAME, "SAME_ENTITY"), (REV, "REVIEW")):
        c = res["confusion"][t]
        print(f"  {name:18}{c[DE]:>6}{c[SAME]:>6}{c[REV]:>6}", file=out)
    print(file=out)

    r = res["reason_rates"]
    print(f"Reason checks on the {res['correct']} correct decisions:", file=out)
    print(f"  reason code fits   {r['code']:.0%}", file=out)
    print(f"  customer record    {r['customer']:.0%}", file=out)
    print(f"  evidence exact     {r['evidence_exact']:.0%}   (precision {res['evidence_precision']:.0%}, "
          f"recall {res['evidence_recall']:.0%})", file=out)
    print(f"  reason 2-4 sents   {r['reason_text']:.0%}   (facts in the text are not checked)", file=out)
    print(f"Estimated dev score (0.75 decisions + 0.25 reasons): {res['combined']:.3f}", file=out)

    if quiet:
        return
    shown = [row for row in res["rows"] if show_all or row["problems"]]
    if not shown:
        return
    print(f"\nPER-HIT DIFF ({len(shown)} hits):", file=out)
    for row in sorted(shown, key=lambda r: (-r["cost"], r["hit_id"])):
        lab, pred = row["label"], row["pred"] or {}
        mark = "!!" if row["hit_id"] in res["unsafe"] else ("ok" if not row["problems"] else "--")
        print(f"\n{mark} {row['hit_id']} ({lab.get('alert_id')})  cost {row['cost']}", file=out)
        print(f"   label: {lab['decision']} {as_list(lab.get('reason_codes'))} "
              f"cust={as_list(lab.get('customer_record_ids'))} ev={as_list(lab.get('evidence'))}", file=out)
        print(f"   ours:  {pred.get('decision')} {pred.get('reason_code')} "
              f"cust={pred.get('customer_record_id')} ev={pred.get('evidence')}", file=out)
        for p in row["problems"]:
            print(f"   * {p}", file=out)
        if pred.get("reason"):
            print(f"   our reason: {pred['reason']}", file=out)
        if lab.get("path"):
            print(f"   path: {lab['path']}", file=out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score predictions against practice labels.")
    ap.add_argument("predictions")
    ap.add_argument("labels")
    ap.add_argument("--data", help="data folder: also check every hit in hits.jsonl has a line")
    ap.add_argument("--all", action="store_true", help="show every labelled hit in the diff")
    ap.add_argument("--quiet", action="store_true", help="summary only, no per-hit diff")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    hit_ids = None
    if args.data:
        hit_ids = [row["hit_id"] for _, row in read_jsonl(os.path.join(args.data, "hits.jsonl"))
                   if isinstance(row, dict) and row.get("hit_id")]
    preds, problems = check_format(read_jsonl(args.predictions), hit_ids)
    labels = [row for _, row in read_jsonl(args.labels) if isinstance(row, dict)]
    res = score(preds, labels)
    report(res, problems, args.all, args.quiet)
    return 1 if (res["unsafe"] or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
