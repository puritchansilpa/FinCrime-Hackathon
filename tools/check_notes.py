#!/usr/bin/env python3
"""Measure the note parsers over a whole data folder and list what they could not read.

Usage: python3 tools/check_notes.py dev [--show 20]

For every kyc-channel note it reports how often each field (name, dob, doc_country,
result, checked_at) could not be read, and prints examples of each failure. For the
other channels it counts notes that yield residence countries. Run it on any new data
folder to see whether the wording has drifted past what the regexes handle.
"""
import argparse
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "system"))

from screening.load import load_data  # noqa: E402
from screening.notes_parse import parse_kyc_note, parse_residence_note  # noqa: E402

FIELDS = ("name", "dob", "doc_country", "result", "checked_at")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("data_folder")
    ap.add_argument("--show", type=int, default=10, help="examples to print per failure kind")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    data = load_data(args.data_folder)
    kyc = [n for n in data.notes.values() if str(n.get("channel", "")).casefold() == "kyc"]
    other = [n for n in data.notes.values() if str(n.get("channel", "")).casefold() != "kyc"]

    missing, examples, results = Counter(), defaultdict(list), Counter()
    for n in sorted(kyc, key=lambda n: n["note_id"]):
        p = parse_kyc_note(n.get("text") or "", n.get("created_at"))
        if p is None:
            missing["not a kyc sentence"] += 1
            examples["not a kyc sentence"].append(n)
            continue
        results[p["result"]] += 1
        for f in FIELDS:
            if p[f] is None:
                missing[f] += 1
                examples[f].append(n)

    print(f"kyc notes: {len(kyc)}")
    for f in ("not a kyc sentence",) + FIELDS:
        share = 1 - missing[f] / len(kyc) if kyc else 0
        print(f"  {f:20} read {share:7.2%}   missing {missing[f]}")
    print(f"  results: {dict(results)}")
    residence = Counter(len(parse_residence_note(n.get("text") or "")) > 0 for n in other)
    print(f"other notes: {len(other)}   with residence countries: {residence[True]}")

    for kind, notes in examples.items():
        print(f"\n== {kind}: {len(notes)}")
        for n in notes[:args.show]:
            print(f"  {n['note_id']}: {n.get('text')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
