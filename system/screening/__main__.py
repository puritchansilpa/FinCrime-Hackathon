"""Entry point: python3 -m screening <data folder> <output file> [--no-llm]

The LLM is used automatically when XAI_API_KEY is set (in the environment or in a .env
file at the repo root), and the run works the same way without it. --no-llm turns it off.

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

from . import customer, hit, llm, policy, review_queue, templates
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
    templates.configure(data.notes.values())
    print("LLM: on (xAI)" if llm.enabled() else
          "LLM: off (" + ("--no-llm" if not use_llm else "XAI_API_KEY not set") + "); rules and regex only",
          file=sys.stderr)

    results = {}
    queue = []
    errors = 0

    def add_review(final, resolution, hit_row, alert):
        # Annotation only. `final` is already the official decision and is not replaced.
        if final.decision != REVIEW:
            return
        try:
            row = review_queue.build_task(final, resolution, hit_row, alert, data)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            row = review_queue.fallback_row(final, "The review task could not be built, so the hit stays a review.")
        if row is not None:
            queue.append(row)

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
                add_review(results[hid], resolution, hit_row, alert)
            except Exception as exc:
                errors += 1
                print(f"error on {hid}: {exc!r}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                results[hid] = _fallback(hid, alert["alert_id"], "internal error")
                queue.append(review_queue.fallback_row(
                    results[hid], "The hit could not be assessed, so it stays a review."))

    # Hits whose alert is not in alerts.jsonl still get a line.
    for hid, hit_row in data.hits.items():
        if hid not in results:
            results[hid] = _fallback(hid, hit_row.get("alert_id") or "", "its alert is missing")
            queue.append(review_queue.fallback_row(
                results[hid], "The hit could not be assessed, so it stays a review."))

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
        for hid in sorted(results):
            fh.write(json.dumps(results[hid].to_output(), ensure_ascii=False) + "\n")

    review_path = review_queue.queue_path(output_path)
    ranked = review_queue.write_queue(queue, review_path)
    stats = {"hits": len(results), "errors": errors, "seconds": round(time.time() - started, 1),
             "reviews": len(ranked), "review_queue": review_path}
    print(f"wrote {stats['hits']} hits to {output_path} in {stats['seconds']}s "
          f"({errors} errors)", file=sys.stderr)
    print(f"wrote {len(ranked)} review tasks to {review_path}", file=sys.stderr)
    stats["templates"] = templates.stats()
    if stats["templates"]["triggered"]:
        print(f"note templates: {stats['templates']}", file=sys.stderr)
    if llm.enabled():
        stats["llm"] = llm.stats()
        print(f"LLM: {stats['llm']}", file=sys.stderr)
    return stats


def _load_dotenv() -> None:
    """Read XAI_* settings from a .env file at the repo root, if the environment lacks them."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:]
                key, sep, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if sep and key.startswith("XAI_") and value and not os.environ.get(key):
                    os.environ[key] = value
    except OSError:
        pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="system/run", description=__doc__.splitlines()[0])
    parser.add_argument("data_folder")
    parser.add_argument("output_file")
    parser.add_argument("--llm", action="store_true",
                        help="kept for compatibility: the LLM is on by default when XAI_API_KEY is set")
    parser.add_argument("--no-llm", action="store_true", help="never call the LLM")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.data_folder):
        parser.error(f"data folder not found: {args.data_folder}")
    _load_dotenv()
    run(args.data_folder, args.output_file, use_llm=not args.no_llm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
