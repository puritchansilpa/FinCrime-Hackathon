#!/usr/bin/env python3
"""Audit Workstream A's customer resolution on a data folder.

Usage: python3 tools/check_resolution.py dev [--verbose]

1. Against practice labels: does each labelled alert resolve to exactly the person
   the label names (same record set, or several persons for AMBIGUOUS), and are the
   KYC-/NOTE- records the label cites among the person's fact sources?
2. Over every alert: how many resolve to 0, 1 or several persons, how many persons
   have verified facts, and sanity flags (type, name or DOB that contradicts what
   was screened) to eyeball.
Exit code 1 if any labelled alert resolves to the wrong person.
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "system"))

from screening.customer import (LINKS, NAME_FIELDS, dob_fits, name_fits, resolve,  # noqa: E402
                                type_fits)
from screening.load import as_list, load_data  # noqa: E402


def fact_sources(person) -> set:
    facts = [person.verified_name, person.verified_dob] + person.countries + person.declared_names \
        + person.declared_dobs
    return {f.source_id for f in facts if f}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("data_folder")
    ap.add_argument("--verbose", action="store_true", help="print the path of every labelled alert")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    data = load_data(args.data_folder)
    alerts = {a["alert_id"]: a for a in data.alerts}
    res = {aid: resolve(a, data) for aid, a in alerts.items()}

    wrong = ev_missing = 0
    for lab in data.practice_labels:
        r = res.get(lab["alert_id"])
        want = set(as_list(lab.get("customer_record_ids")))
        got = [p.record_ids for p in r.persons] if r else []
        if want == {"AMBIGUOUS"}:
            ok = len(got) > 1
        elif not want:
            ok = not got
        else:
            ok = len(got) == 1 and set(got[0]) == want
        sources = set().union(*(fact_sources(p) for p in r.persons)) if r and r.persons else set()
        need = {e for e in as_list(lab.get("evidence")) if e.startswith(("KYC-", "NOTE-"))}
        ev_ok = need <= sources
        wrong += not ok
        ev_missing += not ev_ok
        if not ok or not ev_ok or args.verbose:
            mark = "ok" if ok and ev_ok else "XX"
            print(f"{mark} {lab['hit_id']} ({lab['alert_id']}): ours {got}  label {sorted(want)}")
            if not ev_ok:
                print(f"   evidence not among our facts: {sorted(need - sources)}")
            print(f"   our path:   {' -> '.join(r.path) if r else '-'}")
            print(f"   label path: {lab.get('path', '')[:400]}")
    n = len(data.practice_labels)
    print(f"\nLabelled alerts resolved to the right person(s): {n - wrong}/{n}")
    print(f"Labels whose KYC/NOTE evidence is among our facts: {n - ev_missing}/{n}")

    counts, flags = Counter(), []
    for aid, r in sorted(res.items()):
        a = alerts[aid]
        kind = "linked" if any(a.get(k) for k in LINKS) else "search"
        counts[(kind, min(len(r.persons), 3))] += 1
        for p in r.persons:
            counts["persons"] += 1
            counts["persons with verified name"] += p.verified_name is not None
            counts["persons with verified dob"] += p.verified_dob is not None
            counts["persons with several records"] += len(p.record_ids) > 1
            if kind == "linked" and len(r.persons) == 1:
                rec = data.customers[p.record_ids[0]]
                if not type_fits(a, rec):
                    flags.append(f"{aid}: type {a.get('entity_type')} vs {rec.get('entity_type')}")
                if not name_fits(a.get("customer_name"), [rec.get(f) for f in NAME_FIELDS]):
                    flags.append(f"{aid}: name {a.get('customer_name')!r} vs {rec.get('full_name')!r}")
                if not dob_fits(a.get("dob"), rec.get("dob")):
                    flags.append(f"{aid}: dob {a.get('dob')} vs {rec.get('dob')}")
    print("\nAll alerts:")
    for k in sorted(counts, key=str):
        label = f"{k[0]} alerts -> {k[1]}{'+' if k[1] == 3 else ''} person(s)" if isinstance(k, tuple) else k
        print(f"  {label:42} {counts[k]}")
    print(f"\nSanity flags on single linked records ({len(flags)}):")
    for f in flags:
        print(f"  {f}")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
