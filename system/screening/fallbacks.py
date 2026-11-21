"""[Workstream A] Temporary stand-ins for Workstream B's normalisers and name matcher.

Customer resolution (A2-A6) needs dates, countries and name agreement before B's
normalize.py / names.py land. These follow POLICY.md exactly, but they are A's private
fallbacks: customer.py always calls B's function first and only uses these when B's
returns nothing. Once B ships B1/B2, B can adopt or replace any of this; then this
module can be deleted.
"""
import re
import unicodedata
from functools import lru_cache

from .models import PartialDate

# --- dates -------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})
_MONTHS["sept"] = 9


def _mk(y, mo=None, d=None):
    if not 1000 <= y <= 2999:
        return None
    if mo is not None and not 1 <= mo <= 12:
        return None
    if d is not None and not 1 <= d <= 31:
        return None
    return PartialDate(y, mo, d)


def parse_date(s):
    """ISO, DD/MM/YYYY (day-first), '17 June 1976', 'June 17, 1976', 'June 1976', '1976', '1976-06'.

    Returns None when the text is not a single date we can read: unknown stays unknown.
    """
    if not s:
        return None
    t = str(s).strip().casefold().replace(",", " ").replace(".", " ").strip()
    t = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", t)
    t = re.sub(r"\s+", " ", t)
    m = re.fullmatch(r"(\d{4})(?:[-/](\d{1,2})(?:[-/](\d{1,2}))?)?(?:t[\d:]+z?)?", t)
    if m:
        y, mo, d = m.groups()
        return _mk(int(y), mo and int(mo), d and int(d))
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", t)
    if m:  # slash dates in this data are day-first
        return _mk(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    parts = t.split()
    if not parts or len(parts) > 3:
        return None
    month = [_MONTHS[p] for p in parts if p in _MONTHS]
    nums = [p for p in parts if p.isdigit()]
    if len(month) != 1 or len(month) + len(nums) != len(parts):
        return None
    years = [int(p) for p in nums if len(p) == 4]
    days = [int(p) for p in nums if len(p) <= 2]
    if len(years) != 1 or len(days) > 1:
        return None
    return _mk(years[0], month[0], days[0] if days else None)


def full_date(d) -> bool:
    return d is not None and d.year is not None and d.month is not None and d.day is not None


# --- countries ---------------------------------------------------------------------

# ISO 3166 alpha-2 -> canonical name (territories count as their own country).
_ISO2 = """AD Andorra|AE United Arab Emirates|AF Afghanistan|AG Antigua and Barbuda|AI Anguilla|AL Albania|
AM Armenia|AO Angola|AR Argentina|AS American Samoa|AT Austria|AU Australia|AW Aruba|AZ Azerbaijan|
BA Bosnia and Herzegovina|BB Barbados|BD Bangladesh|BE Belgium|BF Burkina Faso|BG Bulgaria|BH Bahrain|
BI Burundi|BJ Benin|BM Bermuda|BN Brunei|BO Bolivia|BR Brazil|BS Bahamas|BT Bhutan|BW Botswana|
BY Belarus|BZ Belize|CA Canada|CD Democratic Republic of the Congo|CF Central African Republic|
CG Republic of the Congo|CH Switzerland|CI Cote d'Ivoire|CL Chile|CM Cameroon|CN China|CO Colombia|
CR Costa Rica|CU Cuba|CV Cape Verde|CW Curacao|CY Cyprus|CZ Czech Republic|DE Germany|DJ Djibouti|
DK Denmark|DM Dominica|DO Dominican Republic|DZ Algeria|EC Ecuador|EE Estonia|EG Egypt|ER Eritrea|
ES Spain|ET Ethiopia|FI Finland|FJ Fiji|FO Faroe Islands|FR France|GA Gabon|GB United Kingdom|
GD Grenada|GE Georgia|GG Guernsey|GH Ghana|GI Gibraltar|GL Greenland|GM Gambia|GN Guinea|
GQ Equatorial Guinea|GR Greece|GT Guatemala|GU Guam|GW Guinea-Bissau|GY Guyana|HK Hong Kong|
HN Honduras|HR Croatia|HT Haiti|HU Hungary|ID Indonesia|IE Ireland|IL Israel|IM Isle of Man|IN India|
IQ Iraq|IR Iran|IS Iceland|IT Italy|JE Jersey|JM Jamaica|JO Jordan|JP Japan|KE Kenya|KG Kyrgyzstan|
KH Cambodia|KM Comoros|KN Saint Kitts and Nevis|KP North Korea|KR South Korea|KW Kuwait|
KY Cayman Islands|KZ Kazakhstan|LA Laos|LB Lebanon|LC Saint Lucia|LI Liechtenstein|LK Sri Lanka|
LR Liberia|LS Lesotho|LT Lithuania|LU Luxembourg|LV Latvia|LY Libya|MA Morocco|MC Monaco|MD Moldova|
ME Montenegro|MG Madagascar|MK North Macedonia|ML Mali|MM Myanmar|MN Mongolia|MO Macao|
MP Northern Mariana Islands|MR Mauritania|MT Malta|MU Mauritius|MV Maldives|MW Malawi|MX Mexico|
MY Malaysia|MZ Mozambique|NA Namibia|NC New Caledonia|NE Niger|NG Nigeria|NI Nicaragua|NL Netherlands|
NO Norway|NP Nepal|NZ New Zealand|OM Oman|PA Panama|PE Peru|PF French Polynesia|PG Papua New Guinea|
PH Philippines|PK Pakistan|PL Poland|PR Puerto Rico|PS Palestine|PT Portugal|PW Palau|PY Paraguay|
QA Qatar|RO Romania|RS Serbia|RU Russia|RW Rwanda|SA Saudi Arabia|SB Solomon Islands|SC Seychelles|
SD Sudan|SE Sweden|SG Singapore|SI Slovenia|SK Slovakia|SL Sierra Leone|SM San Marino|SN Senegal|
SO Somalia|SR Suriname|SS South Sudan|SV El Salvador|SX Sint Maarten|SY Syria|SZ Eswatini|
TC Turks and Caicos Islands|TD Chad|TG Togo|TH Thailand|TJ Tajikistan|TL Timor-Leste|TM Turkmenistan|
TN Tunisia|TO Tonga|TR Turkey|TT Trinidad and Tobago|TW Taiwan|TZ Tanzania|UA Ukraine|UG Uganda|
US United States|UY Uruguay|UZ Uzbekistan|VA Vatican City|VC Saint Vincent and the Grenadines|
VE Venezuela|VG British Virgin Islands|VI US Virgin Islands|VN Vietnam|VU Vanuatu|WS Samoa|XK Kosovo|
YE Yemen|ZA South Africa|ZM Zambia|ZW Zimbabwe"""

# Other spellings and demonyms -> canonical name.
_ALIASES = {
    "United States": "USA, U.S., U.S.A., United States of America, America, American",
    "United Kingdom": "UK, U.K., Great Britain, Britain, British, England, English, Scotland, Scottish, "
                      "Wales, Welsh, Northern Ireland",
    "Netherlands": "The Netherlands, Holland, Dutch",
    "Russia": "Russian Federation, Russian",
    "South Korea": "Korea, Republic of Korea, Korea Republic of, South Korean",
    "North Korea": "DPRK, Democratic People's Republic of Korea, North Korean",
    "Cote d'Ivoire": "Ivory Coast, Ivorian",
    "Czech Republic": "Czechia, Czech",
    "Palestine": "Palestina, State of Palestine, Palestinian Territories, Palestinian",
    "Macao": "Macau, Macao Special Administrative Region of China, Macanese",
    "Hong Kong": "Hong Kong SAR, Hong Kong Special Administrative Region of China",
    "Iran": "Islamic Republic of Iran, Iranian",
    "Syria": "Syrian Arab Republic, Syrian",
    "Vietnam": "Viet Nam, Vietnamese",
    "Laos": "Lao People's Democratic Republic, Lao, Laotian",
    "Moldova": "Republic of Moldova, Moldovan",
    "Tanzania": "United Republic of Tanzania, Tanzanian",
    "Bolivia": "Plurinational State of Bolivia, Bolivian",
    "Venezuela": "Bolivarian Republic of Venezuela, Venezuelan",
    "Turkey": "Turkiye, Republic of Turkiye, Turkish",
    "North Macedonia": "Macedonia, Macedonian",
    "Eswatini": "Swaziland",
    "Myanmar": "Burma, Burmese",
    "Cape Verde": "Cabo Verde",
    "Timor-Leste": "East Timor",
    "Democratic Republic of the Congo": "DR Congo, DRC, Congo-Kinshasa",
    "Republic of the Congo": "Congo, Congo-Brazzaville",
    "United Arab Emirates": "UAE, Emirati",
    "Vatican City": "Holy See",
    "US Virgin Islands": "United States Virgin Islands",
    "Afghanistan": "Afghan", "Albania": "Albanian", "Algeria": "Algerian", "Argentina": "Argentine, Argentinian",
    "Armenia": "Armenian", "Australia": "Australian", "Austria": "Austrian", "Azerbaijan": "Azerbaijani",
    "Bahrain": "Bahraini", "Bangladesh": "Bangladeshi", "Belarus": "Belarusian", "Belgium": "Belgian",
    "Bosnia and Herzegovina": "Bosnian", "Brazil": "Brazilian", "Bulgaria": "Bulgarian",
    "Cameroon": "Cameroonian", "Canada": "Canadian", "Chile": "Chilean", "China": "Chinese, PRC, "
    "People's Republic of China", "Colombia": "Colombian", "Costa Rica": "Costa Rican", "Croatia": "Croatian",
    "Cuba": "Cuban", "Cyprus": "Cypriot", "Denmark": "Danish", "Dominican Republic": "Dominican",
    "Ecuador": "Ecuadorian", "Egypt": "Egyptian", "Eritrea": "Eritrean", "Estonia": "Estonian",
    "Ethiopia": "Ethiopian", "Finland": "Finnish", "France": "French", "Georgia": "Georgian",
    "Germany": "German", "Ghana": "Ghanaian", "Greece": "Greek", "Guatemala": "Guatemalan",
    "Haiti": "Haitian", "Honduras": "Honduran", "Hungary": "Hungarian", "Iceland": "Icelandic",
    "India": "Indian", "Indonesia": "Indonesian", "Iraq": "Iraqi", "Ireland": "Irish, Republic of Ireland",
    "Israel": "Israeli", "Italy": "Italian", "Jamaica": "Jamaican", "Japan": "Japanese",
    "Jordan": "Jordanian", "Kazakhstan": "Kazakh", "Kenya": "Kenyan", "Kosovo": "Kosovar, Kosovan",
    "Kuwait": "Kuwaiti", "Latvia": "Latvian", "Lebanon": "Lebanese", "Libya": "Libyan",
    "Lithuania": "Lithuanian", "Luxembourg": "Luxembourgish", "Malaysia": "Malaysian", "Malta": "Maltese",
    "Mexico": "Mexican", "Montenegro": "Montenegrin", "Morocco": "Moroccan", "Nepal": "Nepalese, Nepali",
    "New Zealand": "New Zealander", "Nicaragua": "Nicaraguan", "Nigeria": "Nigerian",
    "Norway": "Norwegian", "Oman": "Omani", "Pakistan": "Pakistani", "Panama": "Panamanian",
    "Paraguay": "Paraguayan", "Peru": "Peruvian", "Philippines": "Filipino, Philippine",
    "Poland": "Polish", "Portugal": "Portuguese", "Puerto Rico": "Puerto Rican", "Qatar": "Qatari",
    "Romania": "Romanian", "Saudi Arabia": "Saudi, Saudi Arabian", "Serbia": "Serbian",
    "Sierra Leone": "Sierra Leonean", "Singapore": "Singaporean", "Slovakia": "Slovak",
    "Slovenia": "Slovenian", "Somalia": "Somali", "South Africa": "South African", "Spain": "Spanish",
    "Sri Lanka": "Sri Lankan", "Sudan": "Sudanese", "Sweden": "Swedish", "Switzerland": "Swiss",
    "Taiwan": "Taiwanese", "Thailand": "Thai", "Trinidad and Tobago": "Trinidadian",
    "Tunisia": "Tunisian", "Uganda": "Ugandan", "Ukraine": "Ukrainian", "Uruguay": "Uruguayan",
    "Uzbekistan": "Uzbek", "Yemen": "Yemeni", "Zambia": "Zambian", "Zimbabwe": "Zimbabwean",
}

NOT_COUNTRIES = {"international", "europe", "global", "worldwide", "unknown", "n a", "na", "none",
                 "africa", "asia", "middle east", "latin america", "eu", "european union"}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()
    s = s.replace("'", "").replace("’", "")
    return re.sub(r"[^0-9a-z]+", " ", s).strip()


def _build_countries():
    table, iso = {}, {}
    for entry in _ISO2.replace("\n", "").split("|"):
        code, name = entry.strip().split(" ", 1)
        iso[code] = name
        table[_fold(name)] = name
    for name, aliases in _ALIASES.items():
        table[_fold(name)] = name
        for a in aliases.split(","):
            if a.strip():
                table[_fold(a)] = name
    return table, iso


_COUNTRY_TABLE, _ISO_TABLE = _build_countries()


@lru_cache(maxsize=4096)
def to_country(s):
    """A country name, ISO2 code or demonym -> canonical country name, else None.

    Takes the last comma part ("Faisalabad, Punjab, Pakistan" -> Pakistan) and drops
    bracketed tags ("Canada [PEP]" -> Canada). "International", "Europe" -> None.
    """
    if not s:
        return None
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", str(s)).strip()
    if not text:
        return None
    if re.fullmatch(r"[A-Z]{2}", text) and text in _ISO_TABLE:   # codes are upper case
        return _ISO_TABLE[text]
    if re.fullmatch(r"[A-Za-z]{2}", text):
        return None
    for candidate in (text, text.split(",")[-1]):
        key = _fold(candidate)
        if key in NOT_COUNTRIES:
            return None
        if key in _COUNTRY_TABLE:
            return _COUNTRY_TABLE[key]
    return None


_TEXT_CODES = {"UK", "US", "USA", "UAE", "U.S.", "U.K.", "U.S.A.", "DRC", "DPRK", "PRC"}
_MAX_COUNTRY_WORDS = max(len(k.split()) for k in _COUNTRY_TABLE)


def find_countries(text, skip_spans=()) -> list:
    """Countries named in free text, as (canonical name, start, end), in text order.

    Only capitalised names/demonyms ("Germany", "the United States", "a Nigerian passport")
    and a few unambiguous codes (UK, US, UAE) count, so ordinary words such as "to" or
    "at" never become Tonga or Austria. Longest match wins; spans in skip_spans
    (e.g. the person's name) are ignored.
    """
    if not text:
        return []
    words = [(m.group(0), m.start(), m.end())
             for m in re.finditer(r"[^\W\d_][\w'’.]*[\w.]|[^\W\d_]", str(text))]  # hyphens split
    found, i = [], 0
    while i < len(words):
        hit = None
        for n in range(min(_MAX_COUNTRY_WORDS, len(words) - i), 0, -1):
            chunk = words[i:i + n]
            start, end = chunk[0][1], chunk[-1][2]
            if any(s < end and start < e for s, e in skip_spans):
                continue
            phrase = " ".join(w for w, _, _ in chunk).rstrip(".")
            first = chunk[0][0]
            if n == 1 and phrase.upper() == phrase and len(phrase.replace(".", "")) <= 4:
                if first.rstrip(".") + ("." if first.endswith(".") else "") in _TEXT_CODES or phrase in _TEXT_CODES:
                    hit = (to_country(phrase.replace(".", "")) or _COUNTRY_TABLE.get(_fold(phrase)), start, end, n)
                    if hit[0]:
                        break
                    hit = None
                continue
            if not first[0].isupper():
                continue
            key = _fold(phrase)
            if key in _COUNTRY_TABLE and key not in NOT_COUNTRIES:
                hit = (_COUNTRY_TABLE[key], start, end, n)
                break
        if hit:
            found.append(hit[:3])
            i += hit[3]
        else:
            i += 1
    return found


# --- names (POLICY.md principle 8) --------------------------------------------------

PLACEHOLDERS = {"na", "n a", "test", "unknown", "xxx", "none", "null", "nil", "tbd", "tba", "dummy",
                "unk", "nn", "noname", "fnu", "lnu"}

_config = {"groups": {}, "legal_forms": frozenset()}


def configure(name_variants: dict) -> None:
    """Load name_variants.json: variant groups and company legal forms."""
    groups, members = {}, {}
    for i, group in enumerate((name_variants or {}).get("name_variants") or []):
        folded = {_fold(v) for v in group if v}
        for v in folded:
            groups.setdefault(v, set()).add(i)
            members.setdefault(v, set()).update(folded)
    _config["groups"] = {k: frozenset(v) for k, v in groups.items()}
    _config["members"] = {k: frozenset(v) for k, v in members.items()}
    _config["legal_forms"] = frozenset(_fold(f) for f in (name_variants or {}).get("company_legal_forms") or [])
    _parts_cached.cache_clear()
    _part_match.cache_clear()


def variant_spellings(part: str) -> frozenset:
    """Every spelling listed together with this part in name_variants.json."""
    return _config.get("members", {}).get(part, frozenset())


def name_parts(s, is_company: bool = False) -> list:
    """Distinct real name parts in order: no brackets, punctuation, initials, placeholders,
    digits or (for companies) legal forms."""
    return list(_parts_cached(str(s) if s else "", bool(is_company)))


@lru_cache(maxsize=65536)
def _parts_cached(s: str, is_company: bool) -> tuple:
    if not s:
        return ()
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}", " ", s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()
    s = re.sub(r"['’`]", "", s)          # O'Connor -> oconnor
    s = re.sub(r"\bn/a\b", " ", s)
    out = []
    for tok in re.split(r"[^0-9a-z]+", s):
        if len(tok) < 2 or tok in PLACEHOLDERS or tok.isdigit():
            continue
        if re.fullmatch(r"x{3,}", tok):
            continue
        if is_company and tok in _config["legal_forms"]:
            continue
        if tok not in out:
            out.append(tok)
    return tuple(out)


def _edits(a: str, b: str, limit: int) -> int:
    """Levenshtein distance, stopping early once it exceeds limit."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


@lru_cache(maxsize=262144)
def _part_match(a: str, b: str) -> bool:
    if a == b:
        return True
    ga, gb = _config["groups"].get(a), _config["groups"].get(b)
    if ga and gb and ga & gb:
        return True
    shorter = min(len(a), len(b))
    if shorter < 4:
        return False
    return _edits(a, b, 1 if shorter <= 6 else 2) <= (1 if shorter <= 6 else 2)


def _units(parts):
    """Single parts, plus adjacent pairs written together (Abdul Salam -> abdulsalam)."""
    units = [(p, frozenset([i])) for i, p in enumerate(parts)]
    units += [(parts[i] + parts[i + 1], frozenset([i, i + 1])) for i in range(len(parts) - 1)]
    return units


def _best_matching(pa, pb):
    """Max number of matched units (disjoint on both sides), then max coverage of each side."""
    ua, ub = _units(pa), _units(pb)
    pairs = [(sa, sb) for (a, sa) in ua for (b, sb) in ub if _part_match(a, b)]
    best = (0, frozenset(), frozenset())

    def search(k, used_a, used_b, count):
        nonlocal best
        if (count, len(used_a) + len(used_b)) > (best[0], len(best[1]) + len(best[2])):
            best = (count, used_a, used_b)
        for idx in range(k, len(pairs)):
            sa, sb = pairs[idx]
            if used_a & sa or used_b & sb:
                continue
            search(idx + 1, used_a | sa, used_b | sb, count + 1)

    search(0, frozenset(), frozenset(), 0)
    return best


def names_agree(a, b, is_company: bool = False) -> bool:
    """POLICY.md principle 8: at least two parts match, or every part of the shorter name matches."""
    pa, pb = name_parts(a, is_company), name_parts(b, is_company)
    if not pa or not pb:
        return False
    count, cov_a, cov_b = _best_matching(pa, pb)
    if count == 0:
        return False
    if count >= 2:
        return True
    if len(pa) < len(pb):
        return len(cov_a) == len(pa)
    if len(pb) < len(pa):
        return len(cov_b) == len(pb)
    return len(cov_a) == len(pa) or len(cov_b) == len(pb)


def real_part_count(s, is_company: bool = False) -> int:
    return len(name_parts(s, is_company))


def fold_text(s) -> str:
    """Accent-free, lowercase, punctuation-free text for substring checks (cities, addresses)."""
    return _fold(s) if s else ""
