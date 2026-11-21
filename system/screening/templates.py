"""[Workstream A] Template learner for kyc notes (HANDOFF P3).

The regex parser (notes_parse) reads each kyc note on its own. When it misses a fact or
finds two possible values, this module looks at the note's *shape* instead:

1. Mask the note. Names, dates, bare years and countries become slots; providers and
   document types become fixed words; success/failure wording becomes a short status code.
   The shape is the dates in order, each with the word just before it, then the names
   and countries (just their number when there is one), plus the status:
       "born<DATE> on<DATE> ; 1<NAME> ; 1<COUNTRY> | S"
   The 22,575 dev kyc notes collapse to a few hundred shapes (see templates.json).
2. A template maps each slot of a shape to a role: name, dob, check_date, doc_country or
   other, plus the result the status wording means.
3. Known shapes come from templates.json, learned from the dev notes by the regex itself
   (a shape is kept only when every dev note with that shape gives the same roles).
   A new shape seen during a run gets ONE LLM call (only with --llm), on the note with the
   lowest note_id that has that shape. The answer is checked and kept in memory for the
   rest of the run. Nothing is written outside system/.
4. Every value read through a template is checked: dates must parse, the person must be
   16-110 at the check (a company's date only has to be before it), the country must be in
   our country table, and a fact the regex read differently becomes unknown. A failed
   check gives unknown, never a guess.

The learner only runs when a trigger fires (see `needs_help`), so a note the regex reads
cleanly is never touched.
"""
import json
import os
import re
from typing import Optional

from . import fallbacks, llm, normalize, notes_parse

TEMPLATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates.json")
FIELDS = ("name", "dob", "doc_country", "result")
ROLES = {"NAME": ("name", "other"), "DATE": ("dob", "check_date", "other"),
         "YEAR": ("dob", "other"), "COUNTRY": ("doc_country", "other")}
_ALL_ROLES = ("name", "dob", "check_date", "doc_country", "other")
_RESULTS = ("approved", "rejected", "expired")

# a bare year, never part of a date the date finder could not read ("03.05.1974", "1974.05.03")
_YEAR_RE = re.compile(r"(?<![\d./\-])\b(?:18|19|20)\d{2}\b(?![-/.]\d)")
_WORD = re.compile(r"[^\W\d_]+")
_CAP_TOKEN = re.compile(r"[^\W\d_][^\W\d_'’.\-]*(?:['’.\-][^\W\d_]+)*")
_NEGATION = re.compile(r"\b(?:not|no|never|without|n't)\b", re.I)
_STATUS = (("E", notes_parse._EXPIRED), ("R", notes_parse._REJECTED),
           ("P", notes_parse._PENDING), ("S", notes_parse._SUCCESS), ("N", _NEGATION))
_MONTH_WORDS = {"jan", "january", "feb", "february", "mar", "march", "apr", "april", "may", "jun",
                "june", "jul", "july", "aug", "august", "sep", "sept", "september", "oct", "october",
                "nov", "november", "dec", "december"}
_COMPANY_CUE = re.compile(r"\b(?:incorporat\w*|registr\w*|compan\w*|ltd|llc|plc|gmbh)\b", re.I)

_state = {"known": None, "learned": {}, "corpus": [], "shape_index": None, "stats": None}


def _new_stats():
    return {"triggered": 0, "known": 0, "learned": 0, "learn_failed": 0, "no_template": 0, "filled": 0,
            "conflicts": 0}


_state["stats"] = _new_stats()


# --- masking ----------------------------------------------------------------------------

def _clean(text: str) -> str:
    # "NOVAK's" -> "NOVAK  " (same length, as notes_parse does, so offsets stay valid)
    return re.sub(r"(?<=[^\W\d_])['’]s\b", "  ", text or "")


def _name_runs(text, taken):
    """Runs of two or more capitalised words not already taken: name candidates in any case."""
    out = []
    toks = [(m.group(0), m.start(), m.end()) for m in _CAP_TOKEN.finditer(text)]
    run = []

    def flush():
        if len(run) >= 2:
            out.append((run[0][1], run[-1][2]))
        run.clear()

    for tok, s, e in toks:
        bare = tok.rstrip(".")
        ok = (tok[0].isupper() and bare.upper() not in notes_parse._ACRONYMS
              and bare.casefold() not in _MONTH_WORDS
              and not any(a < e and s < b for a, b in taken))
        # a run continues only over spaces (no comma, bracket or other word in between)
        if ok and run and not re.fullmatch(r"[ \t]+", text[run[-1][2]:s]):
            flush()
        if ok:
            run.append((tok, s, e))
        else:
            flush()
    flush()
    return out


def mask(text: str):
    """(shape, slots) for a note. slots = [(kind, raw, start, end)]: dates and years, then
    names, then countries, each group in text order (the order a template's roles use)."""
    text = _clean(text)
    fixed, slots = [], []

    def free(s, e):
        return not any(a < e and s < b for a, b, _ in fixed + [(x[2], x[3], x[0]) for x in slots])

    for rx, word in ((notes_parse._PROVIDER_RE, "provider"), (notes_parse._DOC_RE, "document")):
        for m in rx.finditer(text):
            if free(m.start(), m.end()):
                fixed.append((m.start(), m.end(), word))
    for raw, _d, s, e in notes_parse.find_dates(text):
        if free(s, e):
            slots.append(("DATE", raw, s, e))
    for m in _YEAR_RE.finditer(text):
        if free(m.start(), m.end()):
            slots.append(("YEAR", m.group(0), m.start(), m.end()))
    nm = notes_parse.find_name(text)
    if nm and free(nm[1], nm[2]):
        slots.append(("NAME", nm[0], nm[1], nm[2]))
    taken = [(a, b) for a, b, _ in fixed] + [(x[2], x[3]) for x in slots]
    for c, s, e in fallbacks.find_countries(text, skip_spans=taken):
        slots.append(("COUNTRY", text[s:e], s, e))
    taken = [(a, b) for a, b, _ in fixed] + [(x[2], x[3]) for x in slots]
    for s, e in _name_runs(text, taken):
        slots.append(("NAME", text[s:e], s, e))
    slots.sort(key=lambda x: x[2])

    # masked text: slots -> <KIND>, providers/documents -> fixed words
    pieces, pos = [], 0
    for s, e, label in sorted([(x[2], x[3], "<%s>" % x[0]) for x in slots] + fixed):
        pieces.append(text[pos:s])
        pieces.append(" %s " % label)
        pos = e
    pieces.append(text[pos:])
    masked = "".join(pieces)

    # Each slot with the word just before it. Dates and years keep their order and cue (that
    # is what tells a birth date from a check date); a name or country that is the only one
    # of its kind has one possible role, so only its count goes into the shape.
    cued, prev = [], None
    for tok in re.findall(r"<[A-Z]+>|[^\W\d_]+", masked):
        if tok.startswith("<"):
            cued.append((tok[1:-1], "%s%s" % (prev or "", tok)))
            prev = None
        else:
            prev = tok.casefold()
    parts = []
    for kinds in (("DATE", "YEAR"), ("NAME",), ("COUNTRY",)):
        mine = [c for k, c in cued if k in kinds]
        if kinds[0] == "DATE" or len(mine) > 1:
            parts.append(" ".join(mine) or "-")
        else:
            parts.append("%d<%s>" % (len(mine), kinds[0]))
    # status wording in text order: S success, R rejected, E expired, P pending, N negation
    marks = sorted((m.start(), code) for code, rx in _STATUS for m in rx.finditer(masked))
    status = []
    for _pos, code in marks:
        if not status or status[-1] != code:
            status.append(code)
    # slots in shape order (dates and years, then names, then countries), so a template's
    # roles line up with the slots of every note that has the same shape
    group = {"DATE": 0, "YEAR": 0, "NAME": 1, "COUNTRY": 2}
    slots.sort(key=lambda x: (group[x[0]], x[2]))
    return " ; ".join(parts) + " | " + "".join(status), slots


# --- templates --------------------------------------------------------------------------

def _load_known():
    if _state["known"] is None:
        try:
            with open(TEMPLATES_FILE, encoding="utf-8") as fh:
                _state["known"] = json.load(fh).get("templates", {})
        except (OSError, ValueError):
            _state["known"] = {}
    return _state["known"]


def configure(notes=()) -> None:
    """Start a run: forget learned shapes; `notes` (all note rows) picks representatives."""
    _state["learned"] = {}
    _state["corpus"] = [n for n in notes if str(n.get("channel") or "").casefold() == "kyc"]
    _state["shape_index"] = None
    _state["stats"] = _new_stats()


def stats() -> dict:
    return dict(_state["stats"])


def _representative(shape, fallback_note):
    """The kyc note with the lowest note_id that has this shape (order-independent)."""
    if _state["shape_index"] is None:
        index = {}
        for n in sorted(_state["corpus"], key=lambda n: n["note_id"]):
            index.setdefault(mask(n.get("text") or "")[0], n)
        _state["shape_index"] = index
    return _state["shape_index"].get(shape, fallback_note)


def valid_roles(roles, slots) -> bool:
    if not isinstance(roles, list) or len(roles) != len(slots):
        return False
    for role, slot in zip(roles, slots):
        if role not in ROLES[slot[0]]:
            return False
    used = [r for r in roles if r != "other"]
    return len(used) == len(set(used))


_LEARN_SYSTEM = (
    "You label the parts of one identity-verification note written by a bank's onboarding team. "
    "Each numbered slot is a piece of the note. Give each slot exactly one role: "
    "'name' = the verified person or company; 'dob' = their date of birth or incorporation; "
    "'check_date' = the date the check was done; 'doc_country' = the country that issued the "
    "identity document; 'other' = anything else. At most one slot per role. "
    "Also give the check result: 'approved', 'rejected', 'expired', or null if the note does "
    "not say clearly (pending, in progress, unclear). Never guess: use 'other' or null."
)
_LEARN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["roles", "result"],
    "properties": {
        "roles": {"type": "array", "items": {"type": "string", "enum": list(_ALL_ROLES)}},
        "result": {"type": ["string", "null"], "enum": list(_RESULTS) + [None]},
    },
}


def _learn(shape, note):
    """One LLM call for a new shape, on its representative note. Returns a template or None."""
    rep = _representative(shape, note)
    rep_shape, slots = mask(rep.get("text") or "")
    if rep_shape != shape or not slots:
        return None
    listing = "\n".join('%d. %s: "%s"' % (i + 1, kind, raw) for i, (kind, raw, _s, _e) in enumerate(slots))
    user = "Note:\n%s\n\nSlots:\n%s" % (rep.get("text") or "", listing)
    ans = llm.chat_json(_LEARN_SYSTEM, user, _LEARN_SCHEMA, "note_template")
    if not ans or not valid_roles(ans.get("roles"), slots):
        return None
    result = ans.get("result") if ans.get("result") in _RESULTS else None
    return {"roles": ans["roles"], "result": result, "example": rep["note_id"], "source": "llm"}


def template_for(shape, slots, note) -> Optional[dict]:
    known = _load_known().get(shape)
    if known is not None:
        _state["stats"]["known"] += 1
        return known if valid_roles(known.get("roles"), slots) else None
    if shape in _state["learned"]:
        return _state["learned"][shape]
    if not llm.enabled():
        _state["stats"]["no_template"] += 1
        return None
    tpl = _learn(shape, note)
    _state["stats"]["learned" if tpl else "learn_failed"] += 1
    _state["learned"][shape] = tpl      # a failed shape is not retried in this run
    return tpl


# --- reading a note through its template --------------------------------------------------

def _parse_date(s):
    return normalize.parse_date(s) or fallbacks.parse_date(s)


def _country(s):
    return normalize.to_country(s) or fallbacks.to_country(s)


def _years_between(a, b):
    return b.year - a.year - ((b.month or 0, b.day or 0) < (a.month or 0, a.day or 0))


def _plausible_dob(dob, check, company: bool) -> bool:
    if dob is None or dob.year is None:
        return False
    if check is None or check.year is None:
        return 1900 <= dob.year <= 2100
    if (dob.year, dob.month or 0, dob.day or 0) > (check.year, check.month or 13, check.day or 32):
        return False
    return company or 16 <= _years_between(dob, check) <= 110


def read_with_template(text, created_at, template, slots) -> dict:
    """Facts the template's roles give for this note, each checked; unchecked -> None."""
    by_role = {r: slot for r, slot in zip(template["roles"], slots) if r != "other"}
    name = by_role["name"][1].strip().rstrip(".,") if "name" in by_role else None
    check = _parse_date(by_role["check_date"][1]) if "check_date" in by_role else None
    check = check or _parse_date(created_at)
    dob = _parse_date(by_role["dob"][1]) if "dob" in by_role else None
    company = bool(_COMPANY_CUE.search(text or ""))
    if dob is not None and not _plausible_dob(dob, check, company):
        dob = None
    doc_country = _country(by_role["doc_country"][1]) if "doc_country" in by_role else None
    return {"name": name or None, "dob": dob, "dob_raw": by_role["dob"][1] if dob else None,
            "doc_country": doc_country, "checked_at": check, "result": template.get("result")}


def needs_help(parsed, slots) -> bool:
    """The trigger: a needed fact is missing, or the note has more candidates than roles."""
    if parsed is None:
        return True
    if any(parsed.get(f) is None for f in FIELDS):
        return True
    countries = {_country(raw) for kind, raw, _s, _e in slots if kind == "COUNTRY"}
    return len(countries) > 1 or sum(1 for x in slots if x[0] in ("DATE", "YEAR")) > 2


def _same(field, a, b) -> bool:
    if field == "name":
        return " ".join(str(a).split()).casefold() == " ".join(str(b).split()).casefold()
    return a == b


def improve(parsed, text, created_at=None, note_id=None) -> Optional[dict]:
    """The hook notes go through after the regex. Returns the (possibly filled) reading.

    A fact the regex read is kept unless the template reads it differently (then it becomes
    unknown); a fact the regex missed is filled from the template when it passes the checks.
    """
    if not text:
        return parsed
    # Cheap pre-check, so a note the regex read fully is never masked: all facts read and
    # at most two years in the text (the regex already returns no country when it saw two).
    if parsed is not None and all(parsed.get(f) is not None for f in FIELDS) \
            and len(_YEAR_RE.findall(text)) <= 2:
        return parsed
    shape, slots = mask(text)
    if not needs_help(parsed, slots):
        return parsed
    _state["stats"]["triggered"] += 1
    tpl = template_for(shape, slots, {"note_id": note_id or "", "text": text})
    if not tpl:
        return parsed
    got = read_with_template(text, created_at, tpl, slots)
    if parsed is None:
        if got["name"] is None and got["dob"] is None:
            return None
        base = {"name": None, "dob": None, "dob_raw": None, "doc_country": None,
                "doc_type": None, "provider": None, "checked_at": got["checked_at"], "result": None}
        m = notes_parse._PROVIDER_RE.search(text)
        d = notes_parse._DOC_RE.search(text)
        base["provider"] = m.group(0) if m else None
        base["doc_type"] = re.sub(r"\s+", " ", d.group(0).lower()) if d else None
    else:
        base = dict(parsed)
    changed = False
    for f in FIELDS:
        mine, theirs = base.get(f), got.get(f)
        if theirs is None:
            continue
        if mine is None:
            base[f] = theirs
            if f == "dob":
                base["dob_raw"] = got["dob_raw"]
            changed = True
        elif not _same(f, mine, theirs):
            base[f] = None            # the two readings disagree: unknown
            if f == "dob":
                base["dob_raw"] = None
            _state["stats"]["conflicts"] += 1
            changed = True
    if changed:
        _state["stats"]["filled"] += 1
        base["template"] = shape
    return base


# --- learning the committed templates from a data folder --------------------------------------

def bootstrap(notes) -> dict:
    """Templates for every shape whose notes the regex reads the same way.

    For each kyc note, the regex's reading is turned into slot roles. A shape becomes a
    template only if all of its notes give the same roles and result, and the regex read
    at least the name and the date of birth. Conflicting shapes are left out (unknown).
    """
    by_shape = {}
    for n in sorted(notes, key=lambda n: n["note_id"]):
        if str(n.get("channel") or "").casefold() != "kyc":
            continue
        text = n.get("text") or ""
        shape, slots = mask(text)
        p = notes_parse.parse_kyc_note(text, n.get("created_at"))
        roles = _roles_from_regex(p, slots)
        entry = by_shape.setdefault(shape, {"variants": {}, "example": n["note_id"], "count": 0})
        entry["count"] += 1
        key = json.dumps([roles, p.get("result") if p else None])
        entry["variants"][key] = entry["variants"].get(key, 0) + 1
    out, skipped = {}, 0
    for shape, entry in sorted(by_shape.items()):
        if len(entry["variants"]) != 1:
            skipped += 1
            continue
        roles, result = json.loads(next(iter(entry["variants"])))
        if roles is None or "name" not in roles or "dob" not in roles:
            skipped += 1
            continue
        out[shape] = {"roles": roles, "result": result, "example": entry["example"],
                      "count": entry["count"], "source": "regex"}
    return {"templates": out, "skipped_shapes": skipped}


def _roles_from_regex(p, slots):
    if not p:
        return None
    roles = []
    for kind, raw, _s, _e in slots:
        role = "other"
        if kind == "NAME" and p.get("name") and _same("name", raw.strip().rstrip(".,"), p["name"]):
            role = "name"
        elif kind in ("DATE", "YEAR") and p.get("dob_raw") and raw == p["dob_raw"]:
            role = "dob"
        elif kind == "DATE" and p.get("checked_at") and _parse_date(raw) == p["checked_at"]:
            role = "check_date"
        elif kind == "COUNTRY" and p.get("doc_country") and _country(raw) == p["doc_country"]:
            role = "doc_country"
        roles.append(role)
    used = [r for r in roles if r != "other"]
    return roles if len(used) == len(set(used)) else None


def main(argv=None) -> int:
    """python3 -m screening.templates <data folder>  -> rewrites templates.json"""
    import sys
    from .load import load_data
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python3 -m screening.templates <data folder>", file=sys.stderr)
        return 2
    data = load_data(args[0])
    result = bootstrap(data.notes.values())
    kyc = sum(1 for n in data.notes.values() if str(n.get("channel") or "").casefold() == "kyc")
    covered = sum(t["count"] for t in result["templates"].values())
    doc = {"about": "kyc note templates learned from the dev notes by the regex parser "
                    "(see templates.py). Regenerate: python3 -m screening.templates <data folder>",
           "kyc_notes": kyc, "notes_covered": covered, "skipped_shapes": result["skipped_shapes"],
           "templates": result["templates"]}
    with open(TEMPLATES_FILE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"{len(result['templates'])} templates cover {covered}/{kyc} kyc notes; "
          f"{result['skipped_shapes']} shapes skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
