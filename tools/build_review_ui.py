#!/usr/bin/env python3
"""Build the analyst review app: one self-contained HTML file, opened offline in a browser.

    python3 tools/build_review_ui.py [--data dev] [--output output/dev.jsonl]
                                     [--queue output/review_queue.jsonl] [--out build/review_ui.html]

It re-runs the pipeline's own readers (customer resolution, hit facts, policy checks) so
every fact on screen is the one the system used, with the record it came from. It embeds
only the records the hits refer to. Like system/run, it uses the LLM when XAI_API_KEY is
set (environment or repo-root .env) and not otherwise; --no-llm turns it off. Build with
the same setting as the run you are explaining.

The file contains the event's data, so it is written to build/ (gitignored): never commit
or publish it. This tool is not part of system/run and cannot change any decision.
"""
import argparse
import json
import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from screening import __main__ as runner  # noqa: E402
from screening import customer, hit as hit_mod, llm, notes_parse, policy, templates  # noqa: E402
from screening.load import load_data  # noqa: E402
from screening.models import COMPANY, PartialDate  # noqa: E402
from screening.names import Variants  # noqa: E402
from screening.normalize import find_countries, screened_details, search_query  # noqa: E402

TEMPLATE = os.path.join(ROOT, "tools", "review_ui", "template.html")
NOTE_EXCERPT = 2500


def fmt(value):
    if value is None:
        return None
    if isinstance(value, PartialDate):
        return value.iso()
    if isinstance(value, (set, frozenset)):
        return " or ".join(str(y) for y in sorted(value))
    return str(value)


def fact_json(f):
    return {"value": fmt(f.value), "source": f.source_id, "origin": f.origin} if f is not None else None


def read_jsonl(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# --- people ---------------------------------------------------------------------------

def person_json(p, data):
    if p is None:
        return None
    def uniq(facts):
        seen, out = set(), []
        for f in facts:
            key = (fmt(f.value), f.source_id)
            if key not in seen:
                seen.add(key)
                out.append(fact_json(f))
        return out
    return {
        "records": list(p.record_ids),
        "entityType": p.entity_type,
        "verifiedName": fact_json(p.verified_name),
        "verifiedDob": fact_json(p.verified_dob),
        "declaredNames": uniq(p.declared_names),
        "declaredDobs": uniq(p.declared_dobs),
        "countries": uniq(p.countries),
        "unresolved": list(getattr(p, "unresolved_places", []) or []),
    }


STATE_TEXT = {policy.AGREE: "agree", policy.CONTRADICT: "contradict", policy.NEITHER: "neither",
              policy.UNKNOWN: "unknown"}


def facts_for(person, hp, alert, variants):
    """The fact-by-fact comparison, using policy.py's own checks."""
    cv = policy.customer_view(person, alert)
    name = policy.assess_name(cv, hp, variants)
    dob = policy.assess_dob(cv, hp)
    loc = policy.assess_countries(cv, hp)
    temporal = policy.assess_temporal(cv, hp)
    death = policy.assess_deceased(cv, hp)
    rows = []

    ctype, htype = cv.entity_type, hp.entity_type
    if ctype and htype in ("Individual", "Company"):
        tstate = "agree" if ctype == htype else "contradict"
    else:
        tstate = "unknown"
    rows.append({"fact": "Type", "customer": ctype or "Not known", "hit": htype or "Not known",
                 "state": tstate, "detail": {"agree": "Both the same kind", "contradict": "One is a person, the other a company",
                                             "unknown": "Not known on one side"}[tstate],
                 "evidence": list(cv.record_ids[:1])})

    cust_names = [fmt(f.value) for f in cv.name_facts]
    if name.state == policy.AGREE:
        detail = f"{fmt(name.cust.value)} agrees with {fmt(name.hit.value)}"
    elif name.state == policy.CONTRADICT:
        detail = f"Verified name {fmt(name.cust.value)} matches none of the hit's names"
    elif name.state == policy.NEITHER:
        detail = "The names on record do not agree, but they are not verified, so this is not a contradiction"
    else:
        detail = "Too few real name parts on one side to compare"
    rows.append({"fact": "Name",
                 "customer": (fmt(cv.verified_name.value) + " (verified)") if cv.verified_name else
                             ("; ".join(dict.fromkeys(cust_names)) or "Not known"),
                 "hit": "; ".join(fmt(f.value) for f in hp.names) or "Not known",
                 "state": STATE_TEXT[name.state], "detail": detail,
                 "evidence": [name.cust.source_id] if name.cust is not None and name.cust.origin != "screened" else []})

    cust_dobs = [f for f in cv.dob_facts if f.value is not None]
    hit_dobs = [f"{fmt(c.value)} ({_origin_label(c.origin)})" for c in hp.dob_candidates]
    dstate = STATE_TEXT[dob.state]
    ddetail = {"agree": "The birth year is one of the hit's and every part both give is equal",
               "contradict": "More than a year apart, or the same year with a different month or day",
               "neither": "Within a year, but not the same date",
               "unknown": "No date of birth on one side"}[dstate]
    rows.append({"fact": "Date of birth",
                 "customer": "; ".join(f"{fmt(f.value)}" for f in cust_dobs) or "Not known",
                 "hit": "; ".join(hit_dobs) or "Not given", "state": dstate, "detail": ddetail,
                 "evidence": sorted({f.source_id for f in cust_dobs if f.origin != "screened"} |
                                    {c.source_id for c in hp.dob_candidates if c.origin == "search"})})

    if loc.state == policy.AGREE:
        ldetail = "Shared: " + ", ".join(loc.shared)
    elif loc.state == policy.CONTRADICT:
        ldetail = "No country in common"
    elif getattr(loc, "unresolved", None):
        ldetail = "Not settled: " + "; ".join(loc.unresolved) + " could not be tied to a country"
    else:
        ldetail = "No countries on one side"
    rows.append({"fact": "Country", "customer": ", ".join(loc.cust) or "Not known",
                 "hit": ", ".join(loc.hit) or "Not known", "state": STATE_TEXT[loc.state], "detail": ldetail,
                 "evidence": [s for s in loc.sources if not s.startswith("A-")]})

    report = hp.earliest_report.value if hp.earliest_report else None
    if temporal is not None:
        f, age, rep = temporal
        tdetail = (f"Incorporated after the earliest report ({rep.iso()})" if age is None else
                   f"At most {age} at the earliest report ({rep.iso()}), under 16")
        rows.append({"fact": "Time", "customer": fmt(f.value), "hit": f"Earliest report {rep.iso()}",
                     "state": "contradict", "detail": tdetail, "evidence": [f.source_id]})
    else:
        rows.append({"fact": "Time", "customer": "; ".join(fmt(f.value) for f in cust_dobs) or "Not known",
                     "hit": f"Earliest report {report.iso()}" if report else "No dated report",
                     "state": "unknown" if not (report and cust_dobs) else "neither",
                     "detail": "No contradiction" if report and cust_dobs else "Nothing to compare",
                     "evidence": []})

    dd = hp.death_date.value if hp.death_date else None
    rows.append({"fact": "Deceased", "customer": f"Screened {fmt(cv.screened_at)}" if cv.screened_at else "Not known",
                 "hit": f"Died {dd.iso()}" if dd else "No date of death",
                 "state": "contradict" if death is not None else ("neither" if dd else "unknown"),
                 "detail": "Died before the customer was screened" if death is not None else
                           ("Death date is not before screening" if dd else "Nothing to compare"),
                 "evidence": []})
    return rows


def _origin_label(origin):
    return {"dobs": "listed", "profile_age": "age in profile", "profile_dob": "stated in profile",
            "search": "search result"}.get(origin, origin or "")


# --- watchlist side ----------------------------------------------------------------------

def hit_json(hit_row, hp):
    notes = hit_row.get("profile_notes") or ""
    return {
        "names": [{"value": f.value, "origin": f.origin} for f in hp.names],
        "type": hp.entity_type,
        "category": hit_mod.listing_category(hit_row),
        "phrase": hit_mod.listing_phrase(hit_row),
        "dobs": [{"value": fmt(c.value), "source": c.source_id, "origin": _origin_label(c.origin)} for c in hp.dob_candidates],
        "countries": [f.value for f in hp.countries],
        "unresolved": list(getattr(hp, "unresolved_places", []) or []),
        "earliestReport": fmt(hp.earliest_report.value) if hp.earliest_report else None,
        "death": fmt(hp.death_date.value) if hp.death_date else None,
        "position": hit_row.get("position_or_allegation"),
        "notesExcerpt": notes[:NOTE_EXCERPT],
        "notesTruncated": len(notes) > NOTE_EXCERPT,
        "sources": (hit_row.get("source_urls") or [])[:6] if isinstance(hit_row.get("source_urls"), list) else [],
    }


def search_rows(hit_row, data):
    """Every search result for the hit's name, and why each one was or was not used."""
    rows = hit_mod._search_index(data).get(search_query(hit_row.get("name") or ""), [])
    if not rows:
        return []
    countries = hit_mod.hit_countries(hit_row)
    used = {r["result_id"]: years for r, years in hit_mod.relevant_search_results(hit_row, countries, data)}
    phrase = hit_mod._phrase_core(hit_mod.listing_phrase(hit_row))
    phrases = {hit_mod._phrase_core(p): p for p in list(hit_mod.LISTING_PHRASES.values()) + [hit_mod.OTHER_PHRASE]}
    out = []
    for r in sorted(rows, key=lambda r: r.get("result_id") or ""):
        title, snippet = r.get("title") or "", r.get("snippet") or ""
        blob = " ".join(f"{title} {snippet}".lower().split())
        ignore = [hit_row.get("name") or ""] + ([title.split(" - ")[0]] if " - " in title else [])
        mentioned = find_countries(f"{title} {snippet}", ignore_names=ignore)
        if r["result_id"] in used:
            verdict, ok = "Used: puts the birth year at " + fmt(used[r["result_id"]]), True
        elif phrase not in blob:
            other = next((full for core, full in phrases.items() if core in blob), None)
            verdict, ok = (f"Not used: describes {other}, not this listing" if other
                           else "Not used: not a listing"), False
        elif not any(c in countries for c in mentioned):
            verdict, ok = ("Not used: " + (", ".join(mentioned) or "no country") + " is not tied to the hit"), False
        else:
            verdict, ok = "Not used: gives no age at a date", False
        out.append({"id": r["result_id"], "title": title, "snippet": snippet,
                    "countries": mentioned, "verdict": verdict, "used": ok})
    return out


# --- records -----------------------------------------------------------------------------

CUS_FIELDS = ("record_id", "entity_type", "full_name", "preferred_name", "login_name", "dob", "nationality",
              "residence_country", "city", "address", "email", "phone", "status", "onboarded_at")
KYC_FIELDS = ("check_id", "provider", "verified_name", "verified_dob", "document_type", "document_country",
              "result", "checked_at")


def note_json(note):
    text = note.get("text") or ""
    marks = []
    if (note.get("channel") or "").lower() == "kyc":
        p = notes_parse.parse_kyc_note(text, note.get("created_at")) or {}
        for role, key in (("name", "name"), ("dob", "dob_raw"), ("provider", "provider"), ("document", "doc_type")):
            v = p.get(key)
            if v and str(v).lower() in text.lower():
                marks.append({"text": str(v), "role": role})
        read = {"name": p.get("name"), "dob": fmt(p.get("dob")), "doc_country": p.get("doc_country"),
                "result": p.get("result"), "checked_at": fmt(p.get("checked_at"))}
    else:
        read = {"countries": notes_parse.parse_residence_note(text)}
    for c in (read.get("countries") or ([read["doc_country"]] if read.get("doc_country") else [])):
        if c and c.lower() in text.lower():
            marks.append({"text": c, "role": "country"})
    return {"kind": "note", "id": note["note_id"], "channel": note.get("channel"), "date": note.get("created_at"),
            "email": note.get("requester_email"), "text": text, "marks": marks, "read": read}


def record_json(rid, data):
    if rid in data.customers:
        c = data.customers[rid]
        return {"kind": "customer", "id": rid, "fields": {k: c.get(k) for k in CUS_FIELDS if c.get(k) not in (None, "")}}
    if rid in data.kyc_checks:
        k = data.kyc_checks[rid]
        return {"kind": "kyc", "id": rid, "fields": {f: k.get(f) for f in KYC_FIELDS if k.get(f) not in (None, "")}}
    if rid in data.notes:
        return note_json(data.notes[rid])
    if rid in data.search_results:
        r = data.search_results[rid]
        return {"kind": "search", "id": rid, "fields": {"query": r.get("query"), "title": r.get("title"),
                                                         "snippet": r.get("snippet"), "source": r.get("source")}}
    return None


# --- build -------------------------------------------------------------------------------

def practice_score(rows_by_hit, labels):
    if not labels:
        return None
    right = sum(1 for l in labels if rows_by_hit.get(l["hit_id"], {}).get("decision") == l["decision"])
    unsafe = sum(1 for l in labels if l["decision"] != "DIFFERENT_ENTITY" and
                 rows_by_hit.get(l["hit_id"], {}).get("decision") == "DIFFERENT_ENTITY")
    return {"labels": len(labels), "right": right, "unsafe": unsafe}


def build(data_dir, output_path, queue_path, use_llm=False):
    data = load_data(data_dir)
    variants = Variants.load(data_dir)
    llm.configure(use_llm)            # same rule as system/run: on only with a key
    templates.configure(data.notes.values())
    out_rows = {r["hit_id"]: r for r in read_jsonl(output_path)}
    queue = {r["hit_id"]: r for r in read_jsonl(queue_path)}
    alerts = {a["alert_id"]: a for a in data.alerts}

    hits, needed = [], set()
    for alert in data.alerts:
        resolution = customer.resolve(alert, data)
        persons = resolution.persons
        sc = screened_details(alert)
        for hit_row in data.hits_for_alert(alert):
            hid = hit_row["hit_id"]
            row = out_rows.get(hid)
            if row is None:
                continue
            hp = hit_mod.build_hit(hit_row, data)
            entry = {
                "id": hid, "alert": alert["alert_id"], "screenedAt": alert.get("screened_at"),
                "decision": row["decision"], "code": row["reason_code"], "reason": row["reason"],
                "evidence": row.get("evidence") or [], "customerRecord": row.get("customer_record_id"),
                "screened": {k: sc.get(k) for k in ("name", "entity_type", "dob", "country", "city")},
                "link": {k: alert.get(k) for k in ("account_ref", "login_handle", "email") if alert.get(k)},
                "path": list(resolution.path or []),
                "hitName": hit_row.get("name"),
                "persons": [person_json(p, data) for p in persons],
                "facts": [facts_for(p, hp, alert, variants) for p in persons] if persons else [],
                "hit": hit_json(hit_row, hp),
                "search": search_rows(hit_row, data),
                "queue": queue.get(hid),
            }
            hits.append(entry)
            needed.update(entry["evidence"])
            for p in entry["persons"]:
                needed.update(p["records"])
                for key in ("verifiedName", "verifiedDob"):
                    if p.get(key):
                        needed.add(p[key]["source"])
                for key in ("declaredNames", "declaredDobs", "countries"):
                    needed.update(f["source"] for f in p[key])
            needed.update(d["source"] for d in entry["hit"]["dobs"])
            needed.update(s["id"] for s in entry["search"])
            for rows in entry["facts"]:
                for r in rows:
                    needed.update(r["evidence"])

    records = {}
    for rid in sorted(needed):
        rec = record_json(rid, data)
        if rec is not None:
            records[rid] = rec

    counts = Counter(h["decision"] for h in hits)
    return {
        "meta": {"data": os.path.basename(os.path.abspath(data_dir)), "output": os.path.basename(output_path),
                 "built": time.strftime("%Y-%m-%d %H:%M"), "hits": len(hits), "alerts": len(alerts),
                 "counts": dict(counts), "practice": practice_score(out_rows, data.practice_labels),
                 "queueRows": len(queue)},
        "hits": sorted(hits, key=lambda h: h["id"]),
        "records": records,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=os.path.join(ROOT, "dev"))
    ap.add_argument("--output", default=os.path.join(ROOT, "output", "dev.jsonl"))
    ap.add_argument("--queue", default=None, help="review_queue.jsonl (default: next to --output)")
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "review_ui.html"))
    ap.add_argument("--no-llm", action="store_true", help="never call the LLM (match a --no-llm run)")
    args = ap.parse_args(argv)
    runner._load_dotenv()
    queue = args.queue or os.path.join(os.path.dirname(os.path.abspath(args.output)), "review_queue.jsonl")
    started = time.time()
    payload = build(args.data, args.output, queue, use_llm=not args.no_llm)
    payload["meta"]["llm"] = "on (xAI)" if llm.enabled() else "off"
    with open(TEMPLATE, encoding="utf-8") as fh:
        html = fh.read()
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = html.replace("/*__DATA__*/null", blob)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    size = os.path.getsize(args.out) / 1e6
    print(f"wrote {args.out}: {payload['meta']['hits']} hits, {len(payload['records'])} records, "
          f"{size:.1f} MB in {time.time() - started:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
