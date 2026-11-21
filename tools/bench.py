#!/usr/bin/env python3
"""Score the note readers on hand-labelled bench cases (HANDOFF P5).

Usage:
  python3 tools/bench.py [tests/bench/notes.jsonl ...] [--runs 5] [--show]

Modes:
  a  regex only               (notes_parse)
  b  regex + template learner (templates.json, no LLM)
  c  regex + learner + LLM    (needs XAI_API_KEY; run --runs times to check stability)

Each fact (name, dob, doc_country, result for kyc notes; each residence country for the
other channels) is scored:
  right    the value is the expected one, or both are unknown (expected null, read nothing)
  wrong    a value was read and it is not the expected one (including a value where the
           expected answer is null)
  unknown  the expected value exists but nothing was read
It also counts facts that were unknown in mode a and became wrong in b or c: the
"never turns an unknown into a wrong value" criterion.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from screening import customer, llm, notes_parse, templates  # noqa: E402

KYC_FIELDS = ("name", "dob", "doc_country", "result")
DEFAULT_BENCH = os.path.join(ROOT, "tests", "bench", "notes.jsonl")


def load_cases(paths):
    cases = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if line.strip():
                    row = json.loads(line)
                    row["_source"] = f"{os.path.basename(path)}:{i}"
                    cases.append(row)
    ids = Counter(c["case_id"] for c in cases)
    dup = [k for k, v in ids.items() if v > 1]
    if dup:
        raise SystemExit(f"duplicate case_id: {dup}")
    return sorted(cases, key=lambda c: c["case_id"])


def _date_str(d):
    if d is None:
        return None
    out = f"{d.year:04d}"
    if d.month:
        out += f"-{d.month:02d}"
        if d.day:
            out += f"-{d.day:02d}"
    return out


def _as_note(case):
    return {"note_id": case["case_id"], "text": case["text"], "created_at": case.get("created_at"),
            "channel": case.get("channel")}


def read(case, mode):
    """What the system reads from one bench note in a mode: {field: value} / {"countries": [...]}"""
    note = _as_note(case)
    text = note["text"]
    if str(note["channel"]).casefold() == "kyc":
        if mode == "a":
            p = notes_parse.parse_kyc_note(text, note["created_at"])
        else:  # the system's own path: regex, then the template learner (and the LLM in c)
            p = customer._parsed_kyc_note(note)
        p = p or {}
        return {"name": p.get("name"), "dob": _date_str(p.get("dob")),
                "doc_country": p.get("doc_country"), "result": p.get("result")}
    found = notes_parse.parse_residence_note(text)
    if not found and mode == "c" and llm.enabled() and notes_parse.looks_like_residence(text):
        found = llm.extract_residence_countries(text)
    return {"countries": sorted(set(found))}


def _same(field, got, want):
    if field == "name":
        return " ".join(str(got).split()).casefold() == " ".join(str(want).split()).casefold()
    return got == want


def score(case, got):
    """[(field, verdict, got, want)] with verdict right / wrong / unknown."""
    want = case["expected"]
    out = []
    if "countries" in got:
        exp = set(want.get("countries") or [])
        have = set(got["countries"])
        for c in sorted(exp):
            out.append(("countries", "right" if c in have else "unknown", c if c in have else None, c))
        for c in sorted(have - exp):
            out.append(("countries", "wrong", c, None))
        if not exp and not have:
            out.append(("countries", "right", None, None))
        return out
    for f in KYC_FIELDS:
        g, w = got.get(f), want.get(f)
        if g is None:
            verdict = "right" if w is None else "unknown"
        else:
            verdict = "right" if w is not None and _same(f, g, w) else "wrong"
        out.append((f, verdict, g, w))
    return out


def set_mode(mode):
    llm.configure(mode == "c")
    llm._state["cache"].clear()           # every run asks again: the stability check is real
    customer._parsed_kyc_note.cache.clear()
    templates.configure([])


def run_mode(cases, mode):
    set_mode(mode)
    templates.configure([_as_note(c) for c in cases])   # representatives come from the bench
    return {c["case_id"]: read(c, mode) for c in cases}


def table(cases, readings):
    by_field = defaultdict(Counter)
    for c in cases:
        for f, verdict, _g, _w in score(c, readings[c["case_id"]]):
            by_field[f][verdict] += 1
    total = Counter()
    lines = [f"  {'fact':12} {'right':>6} {'wrong':>6} {'unknown':>8}"]
    for f in KYC_FIELDS + ("countries",):
        n = by_field[f]
        total.update(n)
        lines.append(f"  {f:12} {n['right']:6} {n['wrong']:6} {n['unknown']:8}")
    lines.append(f"  {'TOTAL':12} {total['right']:6} {total['wrong']:6} {total['unknown']:8}")
    return total, "\n".join(lines)


def unknown_to_wrong(cases, base, other):
    out = []
    for c in cases:
        a = {(f, w): v for f, v, _g, w in score(c, base[c["case_id"]])}
        for f, v, g, w in score(c, other[c["case_id"]]):
            if v == "wrong" and a.get((f, w)) != "wrong":
                out.append((c["case_id"], f, g, w))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bench", nargs="*", default=[DEFAULT_BENCH])
    ap.add_argument("--runs", type=int, default=5, help="runs of mode c for the stability check")
    ap.add_argument("--show", action="store_true", help="list every wrong or unknown fact")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    cases = load_cases(args.bench)
    kyc = sum(1 for c in cases if str(c.get("channel")).casefold() == "kyc")
    print(f"{len(cases)} cases ({kyc} kyc, {len(cases) - kyc} other) from {', '.join(args.bench)}")

    results = {}
    modes = [("a", "regex only"), ("b", "regex + template learner")]
    have_key = bool(os.environ.get("XAI_API_KEY"))
    if have_key:
        modes.append(("c", "regex + learner + LLM"))
    for mode, label in modes:
        results[mode] = run_mode(cases, mode)
        total, text = table(cases, results[mode])
        extra = ""
        if mode == "b":
            s = templates.stats()
            extra = f"   (templates: {s})"
        print(f"\n[{mode}] {label}{extra}\n{text}")
        if mode == "c":
            runs = [results["c"]]
            for _ in range(max(0, args.runs - 1)):
                runs.append(run_mode(cases, "c"))
            same = all(r == runs[0] for r in runs[1:])
            print(f"  LLM: {llm.stats()}")
            print(f"  {len(runs)} runs identical: {'YES' if same else 'NO'}")
            if not same:
                for cid in sorted(runs[0]):
                    vals = [json.dumps(r[cid], sort_keys=True) for r in runs]
                    if len(set(vals)) > 1:
                        print(f"    differs: {cid}: {sorted(set(vals))}")
        if mode != "a":
            flips = unknown_to_wrong(cases, results["a"], results[mode])
            print(f"  facts not wrong in (a) but wrong in ({mode}): {len(flips)}")
            for cid, f, g, w in flips:
                print(f"    {cid} {f}: read {g!r}, expected {w!r}")
    if not have_key:
        print("\n[c] regex + learner + LLM: skipped (XAI_API_KEY is not set)")

    if args.show:
        for mode, _label in modes:
            print(f"\n== mode {mode}: wrong and unknown facts")
            for c in cases:
                for f, v, g, w in score(c, results[mode][c["case_id"]]):
                    if v != "right":
                        print(f"  {c['case_id']:8} {f:11} {v:7} read={g!r} expected={w!r}")
    set_mode("a")
    return 0


if __name__ == "__main__":
    sys.exit(main())
