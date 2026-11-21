"""Hit facts: who the listed person is (POLICY.md principle 5).  [Workstream B]

build_hit(hit_row, data) -> HitProfile
  names            name + every alias
  dob_candidates   `dobs` field, else an age-at-date sentence in the first paragraph of the
                   profile notes (two birth years), and only when neither gives one, relevant
                   web search results (same kind of listing, in a country tied to the hit)
  earliest_report  earliest "According to …; Month DD, YYYY: …" line
  death_date       `deceased_date` field
  countries        countries, nationality, citizenship, last part of each address, place_of_birth

For companies only the `dobs` field is an incorporation date.
"""

import re
from typing import Dict, List, Optional, Tuple

from .models import COMPANY, INDIVIDUAL, Fact, HitProfile, PartialDate
from .normalize import (
    MONTHS, find_countries, fold, is_unresolved_place, name_parts, parse_date, parse_date_list, search_query, split_list, to_countries, to_country,
)

# ---------------------------------------------------------------------------
# Entity type
# ---------------------------------------------------------------------------

_PERSON_WORDS = {"individual", "person", "natural person", "people"}
_COMPANY_WORDS = {"company", "organisation", "organization", "entity", "corporation", "business",
                  "legal entity", "firm"}


def entity_kind(value) -> Optional[str]:
    v = (value or "").strip().lower()
    if v in _PERSON_WORDS:
        return INDIVIDUAL
    if v in _COMPANY_WORDS:
        return COMPANY
    return None


# ---------------------------------------------------------------------------
# Listing phrases (POLICY.md principle 5; worded the same in the unseen set)
# ---------------------------------------------------------------------------

LISTING_PHRASES = {
    "sanctions": "a sanctioned individual",
    "pep": "a politically exposed person",
    "enforcement": "the subject of enforcement action",
    "adverse media": "named in adverse media",
    "soe": "a state-owned enterprise official",
}
OTHER_PHRASE = "named on a watchlist"


def listing_category(hit_row) -> Optional[str]:
    cat = (hit_row.get("primary_category") or "").strip()
    if not cat:
        cats = split_list(hit_row.get("categories"))
        cat = cats[0] if cats else ""
    return cat or None


def listing_phrase(hit_row) -> str:
    cat = (listing_category(hit_row) or "").lower()
    return LISTING_PHRASES.get(cat, OTHER_PHRASE)


def _phrase_core(phrase: str) -> str:
    """'a politically exposed person' -> 'politically exposed person' (articles may vary)."""
    return re.sub(r"^(a|an|the)\s+", "", phrase.strip().lower())


# ---------------------------------------------------------------------------
# Age at a date
# ---------------------------------------------------------------------------

_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
          "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
          "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}
_NUM = (r"(?P<n>\d{1,3}|(?:" + "|".join(_TENS) + r")(?:[- ](?:" + "|".join(k for k in _UNITS if _UNITS[k] < 10) +
        r"))?|" + "|".join(_UNITS) + r")")


def _num(s: str) -> Optional[int]:
    s = s.lower().strip()
    if s.isdigit():
        return int(s)
    parts = re.split(r"[- ]", s)
    total = 0
    for p in parts:
        if p in _TENS:
            total += _TENS[p]
        elif p in _UNITS:
            total += _UNITS[p]
        else:
            return None
    return total


_AGE_PATTERNS = [
    re.compile(r"\baged\s+" + _NUM + r"\b", re.I),                          # aged 46
    re.compile(r"\b" + _NUM + r"[- ]years?[- ]old\b", re.I),                # 38-year-old, 42 years old
    re.compile(r"\bage\s+of\s+" + _NUM + r"\b", re.I),                      # at the age of 43
    re.compile(r"\bat\s+age\s+" + _NUM + r"\b", re.I),                      # at age 31
    re.compile(r"\bage[d]?\s*[:=]\s*" + _NUM + r"\b", re.I),                # age: 45
    re.compile(r"\b(?:is|was|were)\s+" + _NUM +                                # he was 46. / who was 36 and
               r"(?![.,]\d|\s*%|\s*percent)(?=\s*(?:[,.;:)]|$|\s+(?:at|in|on|when|during|and|while|upon|by)\b))", re.I),
    re.compile(r"\bthen\s+(?:aged\s+)?" + _NUM + r"\b(?![.,]\d|\s*%)", re.I),     # …, then 42, …
    re.compile(r"(?<![\d,.]),\s*" + _NUM + r"\s*,(?!\d)"),                    # MARCOS COSTA, 21, a …
    re.compile(r"(?<=[A-Za-z] )\(\s*" + _NUM + r"\s*\)"),                      # John Smith (45)
]


_MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
_TEXT_DATE_PATTERNS = [
    re.compile(r"\b(?P<mon>" + _MONTH_NAMES + r")\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y>(?:19|20)\d{2})\b", re.I),
    re.compile(r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<mon>" + _MONTH_NAMES + r")\.?,?\s+(?P<y>(?:19|20)\d{2})\b", re.I),
    re.compile(r"\b(?P<mon>" + _MONTH_NAMES + r")\.?,?\s+(?:of\s+)?(?P<y>(?:19|20)\d{2})\b", re.I),
    re.compile(r"\b(?P<y>(?:19|20)\d{2})-(?P<m>\d{2})(?:-(?P<d>\d{2}))?\b"),
    re.compile(r"\b(?P<y>(?:19|20)\d{2})\b"),
]


def _date_from_match(m) -> Optional[PartialDate]:
    g = m.groupdict()
    month = MONTHS.get(g["mon"].lower()) if g.get("mon") else (int(g["m"]) if g.get("m") else None)
    if g.get("mon") and month is None:
        return None
    day = int(g["d"]) if g.get("d") else None
    return parse_date(f"{g['y']}-{month:02d}-{day:02d}" if month and day else
                      f"{g['y']}-{month:02d}" if month else g["y"])


def first_text_date(text: str) -> Optional[PartialDate]:
    """The most specific date mentioned in free text (month+year beats a bare year)."""
    for pat in _TEXT_DATE_PATTERNS:
        for m in pat.finditer(text):
            d = _date_from_match(m)
            if d:
                return d
    return None


_NUMERIC_DATE_AT_START = re.compile(r"\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})\b")


def date_at_start(text: str) -> Optional[PartialDate]:
    """A date that starts the text ('on 3 May 1974', 'in 1974', '03/05/1974'), else None.
    Used after 'born' so a later, unrelated date in the sentence is never read as a birth date."""
    t = re.sub(r"^\s*(?:on|in|the)\s+", "", text or "", flags=re.I)
    m = _NUMERIC_DATE_AT_START.match(t)
    if m:
        return parse_date(m.group(1))
    t = t.lstrip()
    for pat in _TEXT_DATE_PATTERNS:
        m = pat.match(t)
        if m:
            d = _date_from_match(m)
            if d:
                return d
    return None


_WORD_NUM_RE = re.compile(r"\b(?:(?:" + "|".join(_TENS) + r")(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|"
                          r"ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\b", re.I)


def snippet_age(text: str) -> Optional[int]:
    """A search snippet describes one person at one date: once the dates are removed, the
    only remaining small number is the age, however the sentence is worded."""
    cleaned = text
    for pat in _TEXT_DATE_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    nums = {int(n) for n in re.findall(r"(?<![\d.,])\b(\d{1,3})\b(?![.,]?\d)", cleaned)}
    nums = {n for n in nums if 10 <= n <= 110}
    if not nums:
        nums = {_num(m.group(0)) for m in _WORD_NUM_RE.finditer(cleaned)} - {None}
        nums = {n for n in nums if 10 <= n <= 110}
    return nums.pop() if len(nums) == 1 else None


def age_at_date(text: str, snippet: bool = False) -> Optional[Tuple[int, PartialDate]]:
    """(age, date) from a sentence like 'aged 45 in March 2019'; None if either is missing."""
    if not text:
        return None
    if snippet:
        when = first_text_date(text)
        age = snippet_age(text)
        return (age, when) if age is not None and when is not None and when.year else None
    best = None
    for pat in _AGE_PATTERNS:
        for m in pat.finditer(text):
            n = _num(m.group("n"))
            if n is not None and 10 <= n <= 110 and (best is None or m.start() < best[0]):
                best = (m.start(), n)
    if best is None:
        return None
    when = first_text_date(text)
    if when is None or when.year is None:
        return None
    return best[1], when


def birth_years(age: int, when: PartialDate) -> frozenset:
    """Someone aged 45 in March 2019 was born in 1973 or 1974."""
    return frozenset({when.year - age - 1, when.year - age})


def first_paragraph(notes: str) -> str:
    notes = (notes or "").strip()
    return re.split(r"\n\s*\n", notes, maxsplit=1)[0] if notes else ""


def _sentences(text: str) -> List[str]:
    """Split on sentence ends, but not on 'b.' or 'Dr.'."""
    protected = re.sub(r"\b([A-Za-z])\.\s+", lambda m: m.group(0).replace(" ", "\x00"), text or "")
    parts = re.split(r"(?<=[.!?])\s+|\n+", protected)
    return [part.replace("\x00", " ").strip() for part in parts if part.strip()]


# A sentence about a relative is not a fact about the listed person.
_RELATIVE = re.compile(
    r"\b(?:her|his|their)\s+(?:sister|brother|father|mother|husband|wife|son|daughter|"
    r"parent|parents|sibling|uncle|aunt|cousin|spouse)\b"
    r"|\b(?:sister|brother|father|mother)\b",
    re.I)
_EXPLICIT_DOB = re.compile(
    r"\b(?:born(?:\s+on)?|b\.)\s+([^.;\n]{0,48})|\bDOB\s*:\s*([^.;\n]{0,48})",
    re.I)
_DEATH = re.compile(
    r"\b(?:died|passed\s+away)\s+on\s+([^.;\n]{0,48})|\bdate\s+of\s+death\s*:\s*([^.;\n]{0,48})",
    re.I)


def _subject_sentences(text: str) -> List[str]:
    return [sentence for sentence in _sentences(text) if not _RELATIVE.search(sentence)]


def explicit_birth_dates(paragraph: str) -> List[PartialDate]:
    """Full birth dates stated in the first paragraph ('born on', 'b.', 'DOB:').

    A date in a sentence about a relative is not the listed person's.
    """
    out: List[PartialDate] = []
    for sentence in _subject_sentences(paragraph):
        for match in _EXPLICIT_DOB.finditer(sentence):
            chunk = next(group for group in match.groups() if group)
            # The date must follow the cue directly: in "Born in Kano, he was arrested in
            # March 2019" the 2019 is not a birth date.
            found = date_at_start(chunk)
            if found is not None and found.year is not None and found not in out:
                out.append(found)
    return out


def _about_listed_person(before: str, name_parts: List[str]) -> bool:
    """The words just before 'died' name the listed person ('Musa Bello died on …'), not a
    co-defendant or a witness, and not as a possessive ("Bello's co-defendant died …").
    A sentence that starts with 'He' or 'She' is about the profile's subject."""
    if re.fullmatch(r"\s*(?:he|she)(?:\s+\w+ly)?\s*", before, re.I):
        return True        # 'He died on …' / 'She reportedly died on …': the profile's subject
    tail = fold(before[-60:]).lower()
    for part in name_parts:
        i = tail.rfind(part)
        if i >= 0 and not re.match(r"\s*'s\b|’s\b", tail[i + len(part):]) and \
                not re.search(r"\b(?:co-?defendant|witness|victim|partner|associate|accomplice|son|daughter|"
                              r"wife|husband|brother|sister|father|mother)\b", tail[i + len(part):]):
            return True
    return False


def death_from_notes(notes: str, name_parts: Optional[List[str]] = None) -> Optional[PartialDate]:
    """A date of death the profile states in prose, for the listed person.

    'His father died on …' is not one, and neither is 'The co-defendant, John Smith, died
    on …': '<name> died on' counts only when the listed person's own name comes just before
    'died'. A 'Date of death:' line counts. A death on or after the screening date is
    still returned; the policy decides whether it is before screening.
    """
    for sentence in _subject_sentences(notes):
        match = _DEATH.search(sentence)
        if not match:
            continue
        if match.group(1) is not None and not _about_listed_person(sentence[:match.start()], name_parts or []):
            continue
        chunk = next(group for group in match.groups() if group)
        found = parse_date(chunk.strip(" ,")) or first_text_date(chunk)
        if found is not None and found.year is not None and found.day is not None:
            return found
    return None


# ---------------------------------------------------------------------------
# Dated reports
# ---------------------------------------------------------------------------

_REPORT_RE = re.compile(
    r"^\s*According to (?P<src>.+?);\s*(?P<date>(?:" + _MONTH_NAMES + r")\.?\s+\d{1,2},\s*\d{4})\s*:",
    re.I,
)


def dated_reports(notes: str) -> List[PartialDate]:
    """Dates of the lines 'According to …; September 10, 2025: …' (other wordings don't count)."""
    out = []
    for line in (notes or "").split("\n"):
        m = _REPORT_RE.match(line)
        if m:
            d = parse_date(re.sub(r"\s+", " ", m.group("date")).strip())
            if d and d.day is not None:
                out.append(d)
    return out


# ---------------------------------------------------------------------------
# Build the profile
# ---------------------------------------------------------------------------

_PLACE_FIELDS = ("countries", "nationality", "citizenship", "place_of_birth", "addresses")


def hit_countries(hit_row) -> List[str]:
    """Countries tied to the hit: countries, nationality, citizenship, place of birth, and each
    address (its last part, or a known city/region in it, e.g. 'London')."""
    out = []
    for key in _PLACE_FIELDS:
        for item in split_list(hit_row.get(key)):
            c = to_country(item)
            if c and c not in out:
                out.append(c)
    return out


def hit_unresolved_places(hit_row) -> List[str]:
    """Place values tied to the hit that name no country we can identify. While any exist,
    'every country tied to the hit' is not known, so location cannot clear the hit."""
    out = []
    for key in _PLACE_FIELDS:
        for item in split_list(hit_row.get(key)):
            if is_unresolved_place(item) and item not in out:
                out.append(item)
    return out


def _search_index(data) -> Dict[str, list]:
    if data is None:
        return {}
    if isinstance(data, dict):
        return data
    return getattr(data, "search_by_query", {}) or {}


def relevant_search_results(hit_row, countries: List[str], data) -> List[Tuple[dict, frozenset]]:
    """Search results about this hit: same kind of listing, in a country tied to the hit,
    and giving an age at a date. Returns (row, birth_years) sorted by result_id."""
    rows = _search_index(data).get(search_query(hit_row.get("name") or ""), [])
    phrase = _phrase_core(listing_phrase(hit_row))
    out = []
    for r in sorted(rows, key=lambda r: r.get("result_id") or ""):
        title = r.get("title") or ""
        snippet = r.get("snippet") or ""
        # The listing phrase and the country may sit in the title. The phrase
        # still has to be this hit's own kind of listing, and the country still
        # has to be one tied to the hit, so a namesake title is not used.
        blob = re.sub(r"\s+", " ", f"{title} {snippet}".lower())
        if phrase not in blob:
            continue
        # Blank the person's name so "Jordan Smith" is not the country Jordan.
        # Only a "Name - source" title is blanked wholesale; otherwise "in Spain"
        # later in the title would be wiped out with the name.
        ignore = [hit_row.get("name") or ""]
        if " - " in title:
            ignore.append(title.split(" - ")[0])
        mentioned = find_countries(f"{title} {snippet}", ignore_names=ignore)
        if not any(c in countries for c in mentioned):
            continue
        aa = age_at_date(snippet, snippet=True) or age_at_date(title, snippet=True)
        if aa is None:
            continue
        out.append((r, birth_years(*aa)))
    return out


def build_hit(hit_row: dict, data=None) -> HitProfile:
    hid = hit_row["hit_id"]
    kind = entity_kind(hit_row.get("entity_type"))
    names = [Fact(hit_row["name"], hid, "name")] if hit_row.get("name") else []
    for alias in split_list(hit_row.get("aliases")):
        if alias not in [f.value for f in names]:
            names.append(Fact(alias, hid, "alias"))

    countries = hit_countries(hit_row)

    cands: List[Fact] = [Fact(d, hid, "dobs") for d in parse_date_list(hit_row.get("dobs"))]
    origin = "dobs" if cands else None
    if kind != COMPANY:
        # SOP order: the dobs field, else a sentence in the first paragraph of the notes,
        # else (when neither gives one) relevant web search results.
        paragraph = "" if cands else first_paragraph(hit_row.get("profile_notes"))
        stated = explicit_birth_dates(paragraph) if paragraph else []
        if stated:
            cands.extend(Fact(d, hid, "profile_dob") for d in stated)
            origin = "profile_dob"
        else:
            subject = " ".join(_subject_sentences(paragraph)) if paragraph else ""
            aa = age_at_date(subject) if subject else None
            if aa is not None:
                cands.append(Fact(birth_years(*aa), hid, "profile_age"))
                origin = "profile_age"
        if not cands:
            for r, years in relevant_search_results(hit_row, countries, data):
                cands.append(Fact(years, r["result_id"], "search"))
            if cands:
                origin = "search"

    reports = dated_reports(hit_row.get("profile_notes"))
    earliest = min(reports, key=lambda d: (d.year, d.month, d.day)) if reports else None
    deaths = parse_date_list(hit_row.get("deceased_date"))
    own_parts = sorted({p for f in names for p in name_parts(f.value) if len(p) >= 3})
    death = deaths[0] if deaths else death_from_notes(hit_row.get("profile_notes"), own_parts)

    return HitProfile(
        hit_id=hid,
        alert_id=hit_row.get("alert_id"),
        entity_type=kind or (hit_row.get("entity_type") or ""),
        names=names,
        dob_candidates=cands,
        dob_origin=origin,
        earliest_report=Fact(earliest, hid, "report") if earliest else None,
        death_date=Fact(death, hid, "deceased_date") if death else None,
        countries=[Fact(c, hid, "hit_country") for c in countries],
        unresolved_places=hit_unresolved_places(hit_row),
    )
