"""system/run <data folder> <output file>: one JSON line per hit.  [Workstream A]

Deterministic: hits are processed in hit_id order and nothing depends on randomness,
time or set order. A hit that fails for any reason is written as REVIEW (fail closed),
so a bad record can never turn into a clearance or a missing line.
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

from . import customer
from .hit import build_hit
from .load import load_data
from .models import INSUFFICIENT_DATA, REVIEW, Decision, Resolution
from .policy import decide_alert_hit


def run(data_dir: str, out_path: str) -> Counter:
    data = load_data(data_dir)
    alerts = {a["alert_id"]: a for a in data.alerts}
    resolutions = {}
    counts = Counter()
    lines = []
    for hit_row in sorted(data.hits, key=lambda h: h["hit_id"]):
        hid, aid = hit_row["hit_id"], hit_row.get("alert_id")
        alert = alerts.get(aid, {"alert_id": aid})
        try:
            if aid not in resolutions:
                try:
                    resolutions[aid] = customer.resolve(alert, data)
                except Exception as e:  # resolver bug: nobody found -> REVIEW
                    print(f"warning: alert {aid}: customer lookup failed ({type(e).__name__}: {e})", file=sys.stderr)
                    resolutions[aid] = Resolution(aid, [], [])
            hp = build_hit(hit_row, data)
            d = decide_alert_hit(resolutions[aid].persons, hp, alert, data.variants)
        except Exception as e:
            print(f"warning: hit {hid}: {type(e).__name__}: {e}", file=sys.stderr)
            d = Decision(hid, aid, REVIEW, INSUFFICIENT_DATA, None,
                         "The hit could not be processed automatically. It needs review.", [])
        counts[d.decision] += 1
        lines.append(json.dumps(d.to_json(), ensure_ascii=False))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return counts


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: system/run <data folder> <output file>", file=sys.stderr)
        return 2
    start = time.time()
    counts = run(argv[0], argv[1])
    total = sum(counts.values())
    print(f"{total} hits written to {argv[1]} in {time.time() - start:.1f}s: " +
          ", ".join(f"{k} {counts[k]}" for k in sorted(counts)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
