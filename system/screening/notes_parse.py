"""[Workstream A] Extract facts from support/onboarding notes (task A5).

The notes are free text and the unseen set words them differently, so nothing here
depends on one template. Instead each fact is found by what it looks like:

kyc notes ("Sumsub completed identity verification for NILS MARTIN, born December 13,
1977, using a national ID issued in Germany on 2023-02-19."):
  - name:     the run of upper-case words (names are written in capitals), else the
              words after a cue such as "for", "holder", "name";
  - dates:    every date in the text; the date of birth is the one tied to a birth cue
              ("DOB", "born", "date of birth"), else the one that is not the check date;
  - check date: the date after "on"/"as of", else the note's created_at;
  - country:  the country named outside the person's name;
  - result:   approved on success words, rejected/expired on failure words, else None.
residence notes ("worked and lived in Pakistan from 2013 to 2015"):
  - every country named in a note that also gives a year or a residence/work cue.

Every value returned is a substring-backed reading of the text: if a fact cannot be
read, it is None (unknown), never a guess.
"""
import re
from typing import Optional

from . import fallbacks, normalize

_MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
          r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
_DATE_RES = [
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),
    re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?(?:\s+of)?\s+" + _MONTH + r",?\s+\d{4}\b", re.I),
    re.compile(r"\b" + _MONTH + r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b", re.I),
    re.compile(r"\b" + _MONTH + r",?\s+\d{4}\b", re.I),
    re.compile(r"\b\d{4}-\d{1,2}\b(?!-)"),
]
_BIRTH_CUE = re.compile(r"\b(?:DOB|D\.O\.B\.?|born|birth|birthdate|date\s+of\s+birth|b\.)", re.I)
_BIRTH_YEAR = re.compile(r"\b(?:DOB|born|birth(?:\s*date)?|date\s+of\s+birth)\b[^0-9.;]{0,20}?\b((?:18|19|20)\d{2})\b"
                         r"(?![-/]\d)", re.I)
_CHECK_CUE = re.compile(r"\b(?:on|as\s+of|dated|at)\s*$", re.I)

_SUCCESS = re.compile(r"\b(?:approv\w*|verif\w*|confirm\w*|pass\w*|clear\w*|validat\w*|success\w*|"
                      r"complet\w*|match\w*|vetted|accepted|authenticat\w*|ok)\b", re.I)
_REJECTED = re.compile(r"\b(?:reject\w*|fail\w*|declin\w*|denied|refus\w*|unsuccessful\w*|could\s+not|"
                       r"couldn't|unable|not\s+(?:be\s+)?(?:verified|approved|confirmed|validated)|"
                       r"invalid|fraud\w*|mismatch\w*|does\s+not\s+match|did\s+not\s+match)\b", re.I)
_EXPIRED = re.compile(r"\b(?:expired|lapsed|out\s+of\s+date|no\s+longer\s+valid)\b", re.I)
_PENDING = re.compile(r"\b(?:pending|in\s+progress|awaiting|incomplete|on\s+hold|requested)\b", re.I)

_PROVIDERS = ["Companies registry lookup", "Persona", "Onfido", "Sumsub", "Jumio", "Veriff", "Trulioo",
              "IDnow", "Socure", "Mitek", "Shufti Pro", "Yoti", "Experian", "Equifax", "GBG",
              "LexisNexis", "Signicat", "iDenfy", "Ondato", "Incode"]
_PROVIDER_RE = re.compile("|".join(re.escape(p) for p in sorted(_PROVIDERS, key=len, reverse=True)), re.I)
_DOC_RE = re.compile(r"\b(passport|national\s+id(?:entity)?(?:\s+card)?|id\s+card|identity\s+card|"
                     r"driv(?:ing|er'?s)\s+licen[cs]e|residence\s+permit|certificate\s+of\s+incorporation|"
                     r"registry\s+extract|company\s+registration|trade\s+register\s+extract)\b", re.I)

# Upper-case words that are not names.
_ACRONYMS = {"DOB", "ID", "KYC", "AML", "UK", "US", "USA", "UAE", "EU", "OK", "N/A", "NA", "PEP",
             "IDV", "API", "OCR", "SSN", "TIN", "PRC", "DRC", "DPRK", "II", "III", "IV", "LLC", "LTD",
             "D.O.B", "D.O.B.", "QA"}
_NAME_TOKEN = r"(?:N/A|[^\W\d_][^\W\d_'’.\-]*(?:['’.\-][^\W\d_]+)*\.?|\d+)"
_UPPER_RUN = re.compile(_NAME_TOKEN + r"(?:[ \t]+" + _NAME_TOKEN + r")*")
_NAME_CUES = re.compile(r"\b(?:for|of|holder|name(?:\s+on\s+(?:the\s+)?document)?|shows|verified|"
                        r"confirmed|customer|applicant)\s*[:,]?\s+", re.I)


def parse_date(s):
    return normalize.parse_date(s) or fallbacks.parse_date(s)


def find_dates(text) -> list:
    """Every readable date in the text as (raw, PartialDate, start, end), in text order."""
    taken, out = [], []
    for rx in _DATE_RES:
        for m in rx.finditer(text):
            if any(s < m.end() and m.start() < e for s, e in taken):
                continue
            raw = re.sub(r"\s+of\s+", " ", m.group(0))
            d = parse_date(raw)
            if d is not None:
                taken.append((m.start(), m.end()))
                out.append((m.group(0), d, m.start(), m.end()))
    return sorted(out, key=lambda x: x[2])


def _is_upper_word(tok: str) -> bool:
    letters = [c for c in tok if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def find_name(text) -> Optional[tuple]:
    """(name, start, end): the longest run of capitalised words that is not an acronym.

    Placeholder tokens inside the run (N/A, 0000) are kept, as the note wrote them;
    the name matcher drops them later.
    """
    best = None
    for m in _UPPER_RUN.finditer(text):
        toks = m.group(0).split()
        # keep only the maximal stretches of upper-case / placeholder tokens
        run, start = [], None
        pos = m.start()
        spans = []
        for tok in toks:
            tstart = text.index(tok, pos)
            pos = tstart + len(tok)
            ok = _is_upper_word(tok) or tok == "N/A" or tok.isdigit()
            if ok:
                if start is None:
                    start = tstart
                run.append((tok, tstart, pos))
            else:
                if run:
                    spans.append(run)
                run, start = [], None
        if run:
            spans.append(run)
        for run in spans:
            # trim acronyms and placeholders from the ends
            while run and (run[0][0].rstrip(".,") in _ACRONYMS or run[0][0].isdigit() or run[0][0] == "N/A"):
                run = run[1:]
            while run and (run[-1][0].rstrip(".,") in _ACRONYMS or run[-1][0].isdigit() or run[-1][0] == "N/A"):
                run = run[:-1]
            real = [t for t, _, _ in run if _is_upper_word(t) and t.rstrip(".,") not in _ACRONYMS
                    and len(t.strip(".,")) >= 2]
            if not real:
                continue
            # a leading/trailing placeholder belongs to the name if it is next to it ("PAWEŁ N/A N/A")
            s, e = run[0][1], run[-1][2]
            while True:
                nxt = re.match(r"[ \t]+(N/A|\d{2,})(?![-/.\d])\b", text[e:])
                if not nxt:
                    break
                e += nxt.end()
            name = text[s:e].strip().rstrip(".,")
            score = (len(real), len(name))
            if best is None or score > best[0]:
                best = (score, name, s, s + len(name))
    if best:
        return best[1], best[2], best[3]
    # Mixed-case names: the words after a cue, up to punctuation or a lower-case word.
    for m in _NAME_CUES.finditer(text):
        tail = text[m.end():]
        n = re.match(r"((?:[A-Z][\w'’.\-]*)(?:\s+[A-Z][\w'’.\-]*){1,4})", tail)
        if n and not _PROVIDER_RE.fullmatch(n.group(1)) and not fallbacks.to_country(n.group(1)):
            return n.group(1), m.end(), m.end() + len(n.group(1))
    return None


def _result(text):
    if _EXPIRED.search(text):
        return "expired"
    if _REJECTED.search(text):
        return "rejected"
    if _PENDING.search(text) and not re.search(r"\b(?:approved|passed|verified|cleared)\b", text, re.I):
        return None
    if _SUCCESS.search(text):
        return "approved"
    return None


def parse_kyc_note(text: str, created_at: str = None) -> Optional[dict]:
    """Read an identity-check note.

    Returns {name, dob, dob_raw, doc_country, doc_type, provider, checked_at, result}
    (any value may be None when the text does not say), or None if the text does not
    look like an identity check at all (no date of birth and no name).
    """
    if not text:
        return None
    # "NOVAK's" -> "NOVAK  " (same length, so every offset stays valid)
    text = re.sub(r"(?<=[^\W\d_])['’]s\b", "  ", text)
    name_hit = find_name(text)
    name_span = [(name_hit[1], name_hit[2])] if name_hit else []
    dates = [d for d in find_dates(text) if not any(s < d[3] and d[2] < e for s, e in name_span)]
    created = parse_date(created_at) if created_at else None

    # the check date: after "on"/"as of", or equal to created_at
    check = None
    for item in dates:
        _raw, d, s, _e = item
        if created is not None and d == created:
            check = item
            break
        if check is None and _CHECK_CUE.search(text[max(0, s - 8):s]):
            check = item
    rest = [x for x in dates if x is not check]

    # the date of birth: the remaining date nearest to a birth cue, else the only remaining one
    dob = None
    cues = [m.end() for m in _BIRTH_CUE.finditer(text)] + [m.start() for m in _BIRTH_CUE.finditer(text)]
    if rest and cues:
        dob = min(rest, key=lambda x: min(min(abs(x[2] - c), abs(x[3] - c)) for c in cues))
    elif len(rest) == 1:
        dob = rest[0]
    if dob is None:
        # a bare birth year right after a birth cue: "born 1966", "DOB 1960", "a date of birth of 1974"
        m = _BIRTH_YEAR.search(text)
        if m and not any(s <= m.start(1) < e for _, _, s, e in dates):
            dob = (m.group(1), parse_date(m.group(1)), m.start(1), m.end(1))

    country_hits = fallbacks.find_countries(text, skip_spans=name_span)
    countries = sorted({c for c, _, _ in country_hits})
    provider = _PROVIDER_RE.search(text)
    doc = _DOC_RE.search(text)

    if dob is None and name_hit is None:
        return None
    return {
        "name": name_hit[0] if name_hit else None,
        "dob": dob[1] if dob else None,
        "dob_raw": dob[0] if dob else None,
        "doc_country": countries[0] if len(countries) == 1 else None,
        "doc_type": re.sub(r"\s+", " ", doc.group(0).lower()) if doc else None,
        "provider": provider.group(0) if provider else None,
        "checked_at": check[1] if check else created,
        "result": _result(text),
    }


_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_RESIDENCE_CUE = re.compile(r"\b(?:liv\w*|resid\w*|home|work\w*|employ\w*|jobs?|based|stay\w*|moved|"
                            r"relocat\w*|career|professional|personal|life|housing|established|ties)\b", re.I)


def parse_residence_note(text: str) -> list:
    """Countries the customer lived or worked in, e.g. 'worked and lived in Pakistan from 2013 to 2015'.

    Counts every country named in a note that also gives a year or a residence/work cue.
    (Erring towards more countries only makes a location clearance less likely.)
    """
    if not text or not (_YEAR.search(text) or _RESIDENCE_CUE.search(text)):
        return []
    return sorted({c for c, _, _ in fallbacks.find_countries(text)})
