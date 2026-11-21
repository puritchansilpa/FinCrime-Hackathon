"""Rebuild the dev/ data folder from the browse workbook.

The data room's JSON Lines files were not available, so this reconstructs them
from "Screening Dev Set - browse.xlsx". It is a dev-only tool (needs openpyxl);
the submitted system/ must not depend on it.

Faithfulness rules:
- Values are kept exactly as the workbook shows them (strings stay strings,
  "; "-joined lists stay joined). The real JSONL may use arrays; the system's
  loader must accept both.
- Only numeric cells become numbers (hit_count -> int, match_score -> float).
- Empty cells become null. Blank trailing rows are dropped.
- The workbook cuts long text at 32,000 characters; affected cells are listed
  in dev/CONVERSION_NOTES.md.

Usage: python3 tools/xlsx_to_jsonl.py "Screening Dev Set - browse.xlsx" dev
"""

import json
import sys
from pathlib import Path

import openpyxl

TABS = {
    "Alerts": "alerts.jsonl",
    "Hits": "hits.jsonl",
    "Customers": "customers.jsonl",
    "Accounts": "accounts.jsonl",
    "Onboarding": "onboarding.jsonl",
    "KYC checks": "kyc_checks.jsonl",
    "Notes": "notes.jsonl",
    "Search results": "search_results.jsonl",
    "Practice labels": "practice_labels.jsonl",
}
POLICY_HEADINGS = {"Decisions", "Principles", "Reason codes"}
TRUNCATION_MARK = "(cut; full text in the JSONL file)"


def clean(key, value):
    if value is None:
        return None
    if isinstance(value, float):
        return int(value) if key == "hit_count" else value
    if isinstance(value, str) and value == "":
        return None
    return value


def convert_tab(ws, out_path):
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    count, truncated = 0, []
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            if not row or row[0] is None:
                continue
            record = {k: clean(k, v) for k, v in zip(header, row)}
            for k, v in record.items():
                if isinstance(v, str) and TRUNCATION_MARK in v:
                    truncated.append((record[header[0]], k))
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count, truncated


def convert_policy(ws, out_dir):
    cells = [r[0] if r else None for r in ws.iter_rows(values_only=True)]
    split = cells.index("name_variants.json")

    lines = []
    for i, v in enumerate(cells[:split]):
        if v is None:
            lines.append("")
        elif i == 0:
            lines.append(f"# {v}")
        elif v in POLICY_HEADINGS:
            lines.append(f"## {v}")
        else:
            lines.append(v)
    policy = "\n".join(lines).strip() + "\n"
    (out_dir / "POLICY.md").write_text(policy, encoding="utf-8")

    groups, legal_forms = [], []
    for v in cells[split + 2:]:  # skip the heading and its description line
        if v is None:
            continue
        if v.startswith("Company legal forms:"):
            legal_forms = [p.strip() for p in v.split(":", 1)[1].split(",") if p.strip()]
        else:
            groups.append([p.strip() for p in v.split(",") if p.strip()])
    variants = {"name_variants": groups, "company_legal_forms": legal_forms}
    (out_dir / "name_variants.json").write_text(
        json.dumps(variants, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(groups), len(legal_forms)


def main(xlsx_path, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)

    notes = ["# Conversion notes", "",
             f"Rebuilt from `{Path(xlsx_path).name}` by `tools/xlsx_to_jsonl.py`.",
             "Replace this folder with the data room's real JSON Lines files if they become available.",
             "", "## Row counts", ""]
    all_truncated = []
    for tab, fname in TABS.items():
        n, truncated = convert_tab(wb[tab], out_dir / fname)
        all_truncated += [(fname, rid, field) for rid, field in truncated]
        notes.append(f"- `{fname}`: {n}")
        print(f"{fname:24} {n:6} rows")

    g, lf = convert_policy(wb["Policy"], out_dir)
    print(f"POLICY.md, name_variants.json ({g} variant groups, {lf} legal forms)")

    notes += ["", "## Cells cut at 32,000 characters in the workbook", ""]
    notes += [f"- `{f}` {rid}: `{field}`" for f, rid, field in all_truncated] or ["- none"]
    notes += ["", "## Format guesses", "",
              "- List fields are kept as `; `-joined strings, as in the workbook.",
              "- `name_variants.json` structure (`name_variants`, `company_legal_forms`) is a guess.",
              "- Policy section headings were turned into Markdown headings."]
    (out_dir / "CONVERSION_NOTES.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    for f, rid, field in all_truncated:
        print(f"TRUNCATED: {f} {rid} {field}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
