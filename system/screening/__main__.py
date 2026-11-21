"""Entry point: python3 -m screening <data folder> <output file> [--llm]

Decides every hit in the data folder and writes one JSON line per hit, sorted by hit_id.
A hit that crashes the pipeline is written as REVIEW / INSUFFICIENT_DATA (never a
clearance), and the error goes to stderr, so one bad record cannot sink a run.
"""
import argparse
import json
import os
import sys
import time
import traceback

from . import customer, hit, llm, policy
from .load import load_data
from .names import Variants
from .models import REVIEW, Decision, Resolution


def _fallback(hit_id: str, alert_id: str, why: str) -> Decision:
    return Decision(
        hit_id=hit_id,
        alert_id=alert_id,
        decision=REVIEW,
        reason_code="INSUFFICIENT_DATA",
        customer_record_id=None,
        reason=f"The system could not assess this hit ({why}), so it is left for review.",
        evidence=[],
    )


def decide_hit(hit_row: dict, alert: dict, resolution: Resolution, data) -> Decision:
    hp = hit.build_hit(hit_row, data)
    persons = resolution.persons or [None]
    variants = getattr(data, "variants", None)   # B's name-variant groups (POLICY.md principle 8)
    decisions = [policy.decide(p, hp, alert, variants) for p in persons]
    return policy.combine(decisions, hp, resolution.persons or None)


def run(data_folder: str, output_path: str, use_llm: bool = False) -> dict:
    started = time.time()
    data = load_data(data_folder)
    data.variants = Variants.load(data_folder)  # for B's name matching in policy.decide
    data.use_llm = use_llm  # read by A7/B7 LLM pieces; off by default
    llm.configure(use_llm)
    if use_llm and not llm.enabled():
        print("warning: --llm given but OPENROUTER_API_KEY is not set; running without the LLM",
              file=sys.stderr)

    results = {}
    errors = 0

    def safe_resolve(alert):
        try:
            return customer.resolve(alert, data)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return None

    for alert in data.alerts:
        resolution = safe_resolve(alert)
        for hit_row in data.hits_for_alert(alert):
            hid = hit_row["hit_id"]
            try:
                if resolution is None:
                    raise RuntimeError("customer resolution failed")
                results[hid] = decide_hit(hit_row, alert, resolution, data)
            except Exception as exc:
                errors += 1
                print(f"error on {hid}: {exc!r}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                results[hid] = _fallback(hid, alert["alert_id"], "internal error")

    # Hits whose alert is not in alerts.jsonl still get a line.
    for hid, hit_row in data.hits.items():
        if hid not in results:
            results[hid] = _fallback(hid, hit_row.get("alert_id") or "", "its alert is missing")

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
        for hid in sorted(results):
            fh.write(json.dumps(results[hid].to_output(), ensure_ascii=False) + "\n")

    stats = {"hits": len(results), "errors": errors, "seconds": round(time.time() - started, 1)}
    print(f"wrote {stats['hits']} hits to {output_path} in {stats['seconds']}s "
          f"({errors} errors)", file=sys.stderr)
    if llm.enabled():
        stats["llm"] = llm.stats()
        print(f"LLM: {stats['llm']}", file=sys.stderr)
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="system/run", description=__doc__.splitlines()[0])
    parser.add_argument("data_folder")
    parser.add_argument("output_file")
    parser.add_argument("--llm", action="store_true",
                        help="enable the OpenRouter LLM fallbacks (needs OPENROUTER_API_KEY)")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.data_folder):
        parser.error(f"data folder not found: {args.data_folder}")
    run(args.data_folder, args.output_file, use_llm=args.llm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
