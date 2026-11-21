"""Normalizers shared by both workstreams: dates, countries, name parts.  [Workstream B]

Python 3.9 standard library only.
"""

import calendar
import re
import unicodedata
from typing import Iterable, List, Optional, Sequence

from .countries import NOT_COUNTRIES, ROWS
from .models import PartialDate

# ---------------------------------------------------------------------------
# Text folding
# ---------------------------------------------------------------------------

_SPECIAL = str.maketrans({
    "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "Th", "ß": "ss", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe", "ı": "i",
    "’": "'", "‘": "'", "`": "'", "´": "'",
})


def fold(s: str) -> str:
    """Strip accents and special letters: 'Raković' -> 'Rakovic'. Case is kept."""
    s = s.translate(_SPECIAL)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def split_list(value) -> List[str]:
    """List fields: a JSON array (the data room format) or a '; '-joined string (the browse
    workbook). Array items are kept whole; objects become their 'country' (else their values)."""
    if value is None:
        return []
    if isinstance(value, dict):
        for key in ("country", "country_name", "value", "name"):
            if value.get(key):
                return [str(value[key]).strip()]
        return [", ".join(str(v).strip() for v in value.values() if v not in (None, ""))]
    if isinstance(value, (list, tuple)):
        items = []
        for v in value:
            if isinstance(v, (dict, list, tuple)):
                items.extend(split_list(v))
            elif v is not None and str(v).strip():
                items.append(str(v).strip())
        return items
    return [p.strip() for p in str(value).split(";") if p.strip()]


def screened_details(alert: dict) -> dict:
    """The customer as screened. Data room alerts nest it under 'customer'
    ({name, entity_type, dob, country, city}); the browse workbook had flat columns."""
    c = alert.get("customer")
    if isinstance(c, dict):
        return {"name": c.get("name"), "entity_type": c.get("entity_type"), "dob": c.get("dob"),
                "country": c.get("country"), "city": c.get("city")}
    return {"name": alert.get("customer_name"), "entity_type": alert.get("entity_type"),
            "dob": alert.get("dob"), "country": alert.get("country"), "city": alert.get("city")}


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MON = r"(?P<mon>[A-Za-z]{3,9})\.?"
_ORD = r"(?:st|nd|rd|th)?"

_DATE_PATTERNS = [
    re.compile(r"^(?P<y>\d{4})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})$"),         # 1976-06-17, 2016/7/8
    re.compile(r"^(?P<y>\d{4})[-/.](?P<m>\d{1,2})$"),                            # 1976-06
    re.compile(r"^(?P<y>\d{4})$"),                                               # 1976
    re.compile(r"^(?P<a>\d{1,2})[/.\-](?P<b>\d{1,2})[/.\-](?P<y>\d{4})$"),       # 17/06/1976 (day-first)
    re.compile(r"^(?P<d>\d{1,2})" + _ORD + r"\s+(?:of\s+)?" + _MON + r",?\s+(?P<y>\d{4})$"),  # 17 June 1976
    re.compile(r"^" + _MON + r"\s+(?P<d>\d{1,2})" + _ORD + r",?\s+(?P<y>\d{4})$"),            # June 17, 1976
    re.compile(r"^" + _MON + r",?\s+(?P<y>\d{4})$"),                                          # June 1976
    re.compile(r"^(?P<m>\d{1,2})[/.\-](?P<y>\d{4})$"),                                        # 06/1976
]


def _valid(y: Optional[int], m: Optional[int], d: Optional[int]) -> Optional[PartialDate]:
    if y is None or not (1000 <= y <= 2100):
        return None
    if m is not None and not (1 <= m <= 12):
        return None
    if d is not None:
        if m is None or not (1 <= d <= calendar.monthrange(y, m)[1]):
            return None
    return PartialDate(y, m, d)


def parse_date(s) -> Optional[PartialDate]:
    """Parse one date as written; unknown parts stay None. Returns None if unparseable.

    Slash dates are day-first (verified on dev: first part > 12 in 6,348 cases, second never),
    unless the second part cannot be a month, in which case it is read month-first.
    """
    if s is None:
        return None
    if isinstance(s, PartialDate):
        return s
    text = re.sub(r"\s+", " ", str(s).strip())
    if not text:
        return None
    for pat in _DATE_PATTERNS:
        m = pat.match(text)
        if not m:
            continue
        g = m.groupdict()
        y = int(g["y"])
        if "a" in g and g.get("a") is not None:            # numeric d/m/y
            a, b = int(g["a"]), int(g["b"])
            day, month = (a, b) if b <= 12 else (b, a)
            return _valid(y, month, day)
        month = None
        if g.get("mon"):
            month = MONTHS.get(g["mon"].lower().rstrip("."))
            if month is None:
                continue
        elif g.get("m"):
            month = int(g["m"])
        day = int(g["d"]) if g.get("d") else None
        return _valid(y, month, day)
    return None


def parse_date_list(value) -> List[PartialDate]:
    """Parse a list field of dates ('1989; 1988' or a JSON array). Unparseable items are skipped."""
    out = []
    for item in split_list(value):
        d = parse_date(item)
        if d is not None and d not in out:
            out.append(d)
    return out


def dates_compatible(a: Optional[PartialDate], b: Optional[PartialDate]) -> bool:
    """True when every part both dates give is equal (a birth year alone fits a full date)."""
    if a is None or b is None or a.year is None or b.year is None:
        return False
    if a.year != b.year:
        return False
    if a.month is not None and b.month is not None and a.month != b.month:
        return False
    if a.day is not None and b.day is not None and a.day != b.day:
        return False
    return True


def age_at(birth: PartialDate, on: PartialDate) -> Optional[int]:
    """Largest possible age of someone born on `birth` at date `on` (None if unknown)."""
    if birth is None or on is None or birth.year is None or on.year is None:
        return None
    age = on.year - birth.year
    if birth.month is not None and on.month is not None:
        if (on.month, on.day or 31) < (birth.month, birth.day or 1):
            age -= 1
    return age


# ---------------------------------------------------------------------------
# Countries
# ---------------------------------------------------------------------------

def _ckey(s: str) -> str:
    s = fold(s).lower().replace("&", " and ")
    s = s.replace(".", "")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    return s


_BY_NAME = {}     # folded name/alias/demonym -> canonical
_BY_CODE = {}     # ISO2 / ISO3 (lowercase) -> canonical
for _canon, _iso2, _iso3, _aliases, _demonyms in ROWS:
    for _n in [_canon] + _aliases + _demonyms:
        _BY_NAME.setdefault(_ckey(_n), _canon)
    for _c in (_iso2, _iso3):
        if _c:
            _BY_CODE.setdefault(_c.lower(), _canon)

CANONICAL_COUNTRIES = sorted({r[0] for r in ROWS})


def to_country(s) -> Optional[str]:
    """Canonical country for one field value, or None.

    Handles names, ISO2/ISO3 codes, demonyms ('Nigerian'), tags ('Spain [Residency]')
    and full places ('Jaén, Jaén, Spain' -> last part). 'International'/'Europe' -> None.
    """
    if s is None:
        return None
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", str(s))
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return None
    last = parts[-1]
    key = _ckey(last)
    if not key or key in NOT_COUNTRIES:
        return None
    if key in _BY_NAME:
        return _BY_NAME[key]
    raw = re.sub(r"[^A-Za-z]", "", last)
    if len(raw) in (2, 3) and raw.lower() in _BY_CODE and raw.lower() not in NOT_COUNTRIES:
        return _BY_CODE[raw.lower()]
    return None


def to_countries(value) -> List[str]:
    """Canonical countries of a list field ('Iraq; United States' or a JSON array)."""
    out = []
    for item in split_list(value):
        c = to_country(item)
        if c and c not in out:
            out.append(c)
    return out


# Phrases consumed in free text but not countries (or not the country they look like).
_TEXT_BLOCKERS = {
    "new jersey": "United States", "new mexico": "United States", "new south wales": "Australia",
    "indian ocean": None, "south american": None, "latin american": None, "north american": None,
    "central american": None, "native american": None, "african american": None,
    "south america": None, "latin america": None, "north america": None, "central america": None,
}
_TEXT_UPPER = {"UK": "United Kingdom", "UAE": "United Arab Emirates", "USA": "United States",
               "U.S.": "United States", "U.S.A.": "United States", "DPRK": "North Korea",
               "DRC": "Democratic Republic of the Congo"}

_text_terms = {}
for _canon, _iso2, _iso3, _aliases, _demonyms in ROWS:
    for _n in [_canon] + _aliases + _demonyms:
        k = _ckey(_n)
        if len(k) >= 4 and not _n.isupper():
            _text_terms.setdefault(k, _canon)
for _k, _v in _TEXT_BLOCKERS.items():
    _text_terms[_k] = _v
_TEXT_RE = re.compile(
    r"(?<![a-z])(" + "|".join(re.escape(k) for k in sorted(_text_terms, key=len, reverse=True)) + r")(?![a-z])"
)
_UPPER_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(re.escape(k) for k in sorted(_TEXT_UPPER, key=len, reverse=True)) + r")(?![A-Za-z])"
)


def _text_key(text: str) -> str:
    s = fold(text).lower().replace("&", " and ")
    return " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9']+", " ", s)).strip() + " "


def find_countries(text: str, ignore_names: Sequence[str] = ()) -> List[str]:
    """Countries mentioned in free text, in order of first mention, deduplicated.

    Scans names, aliases and demonyms ('Nigerian passport'). ISO codes are not scanned
    (too ambiguous in prose) except a few unambiguous upper-case ones (UK, UAE, USA, U.S.).
    `ignore_names`: person/company names to blank out first, so 'Jordan Smith' or
    'Chad Brown' is not read as a country.
    """
    if not text:
        return []
    key_text = _text_key(text)
    upper_text = fold(text)
    for nm in ignore_names or ():
        if nm:
            k = _text_key(nm).strip()
            if k:
                key_text = key_text.replace(" " + k + " ", " " + "_" * len(k) + " ")
            for tok in k.split():
                key_text = key_text.replace(" " + tok + " ", " " + "_" * len(tok) + " ")
            upper_text = upper_text.replace(fold(nm), " ")
    hits = [(m.start(), _text_terms[m.group(1)]) for m in _TEXT_RE.finditer(key_text)]
    hits += [(m.start(), _TEXT_UPPER[m.group(1)]) for m in _UPPER_RE.finditer(upper_text)]
    found = []
    for _, canon in sorted(hits, key=lambda x: x[0]):
        if canon and canon not in found:
            found.append(canon)
    return found


# ---------------------------------------------------------------------------
# Name parts (POLICY.md principle 8)
# ---------------------------------------------------------------------------

PLACEHOLDERS = {"na", "n/a", "test", "unknown", "unk", "none", "null", "nil", "tbd", "tba",
                "dummy", "sample", "noname", "fnu", "lnu", "xxx", "xx", "xxxx"}
_BRACKETS = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}")


def name_parts(s, is_company: bool = False, legal_forms: Iterable[str] = ()) -> List[str]:
    """Comparable name parts: lower-case, no accents, punctuation or bracketed text.

    Single letters (initials), placeholders (NA, TEST, UNKNOWN, XXX, digits…) and, for
    companies, legal forms (Ltd, GmbH, SA…) are dropped. Each distinct part counts once.
    """
    if not s:
        return []
    text = _BRACKETS.sub(" ", str(s))
    text = fold(text).lower()
    text = re.sub(r"(?<![a-z])n\s*/\s*a(?![a-z])", " ", text)    # N/A
    text = re.sub(r"'", "", text)                                   # O'Brien -> obrien
    text = re.sub(r"[\W_]+", " ", text)
    legal = {fold(f).lower().replace(".", "") for f in legal_forms} if is_company else set()
    parts = []
    for tok in text.split():
        if len(tok) < 2 or any(ch.isdigit() for ch in tok):
            continue
        if tok in PLACEHOLDERS or re.fullmatch(r"x{2,}", tok):
            continue
        if tok in legal:
            continue
        if tok not in parts:
            parts.append(tok)
    return parts


def search_query(name: str) -> str:
    """Search-results key for a name: its lowercase words in alphabetical order.

    Verified on dev: accent-folded letter words, single letters dropped, sorted —
    matches the `query` of all 702 individual hits.
    """
    words = [w for w in re.findall(r"[a-z]+", fold(name or "").lower()) if len(w) > 1]
    return " ".join(sorted(words))
