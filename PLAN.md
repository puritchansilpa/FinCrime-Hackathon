# PLAN: "Same Person or Not?" screening system

> **For the reader (human or LLM):** this is the agreed build plan for our hackathon entry.
> - **Read first:**
>   - `CHALLENGE.md`: the task, deliverable and scoring.
>   - `dev/POLICY.md`: the SOP, which is the rulebook.
>   - `dev/practice_labels.jsonl`: 50 answered hits, each with the path through the files.
> - **Don't change** the decisions in "Decisions already made" without discussing them first.
> - **The work is split between two people,** Workstream A (customer side) and Workstream B (hit side and decisions). See **section 6**. Work only in the files your workstream owns. Change `system/screening/models.py` (the shared contract) only after agreeing with the other workstream.

## 1. The task in one paragraph

A bank's name screening raises **alerts**. Each alert has one or more **hits**, which are watchlist profiles that might be the customer. For every hit we output `DIFFERENT_ENTITY` (cleared), `SAME_ENTITY` or `REVIEW`. Each output also has a reason code from `POLICY.md`, the IDs of the records that decided it, the resolved customer record, and a 2–4 sentence reason. Identity only: how serious the listing is doesn't matter.

**Deliverable:**
- `system/run <data folder> <output file>`.
- **Python 3 standard library only** (Node or shell are also allowed).
- LLM calls allowed **only through OpenRouter**, with the key in `OPENROUTER_API_KEY`.
- **Under 30 minutes per run.**
- `output/dev.jsonl`.
- `system/README.md`.
- A public GitHub repo. **Never commit `dev/` or the API key.**

**Output, one JSON line per hit:**
```json
{"hit_id": "H-…", "alert_id": "A-…", "decision": "DIFFERENT_ENTITY|SAME_ENTITY|REVIEW",
 "reason_code": "DOB_MISMATCH", "customer_record_id": "CUS-…|AMBIGUOUS|null",
 "reason": "2–4 sentences with this hit's own facts", "evidence": ["KYC-…", "NOTE-…"]}
```

**Scoring:**
- The system is run 5 times on about 550 unseen hits. These have new customers and **differently worded free text**.
- **Cost of each decision** (row = right answer, column = what we said):

  | Right answer | We said DE | We said SAME | We said REVIEW |
  |---|---|---|---|
  | DE | 0 | 3 | 3 |
  | SAME | **60** | 0 | 2 |
  | REVIEW | **60** | 2 | 0 |

- **So clear a hit only when about 95% sure.** Choosing between SAME and REVIEW breaks even at 50%.
- **Weights:**
  - Unseen set: 80%.
  - Dev set: 10%.
  - Reproducibility: 10% (same decision and reason code in all 5 runs).
- Within the unseen and dev parts, decisions are 75% and reasons 25%.
- **Reasons are graded on:**
  - the right code
  - minimal evidence IDs (cite what decided it, not everything)
  - the right customer ID
  - real facts in the reason text

## 2. Current repo state

- **The repo follows the official data room kit layout**, so the kit README's commands run as written:

  ```
  dev/                  official data room files (JSONL, POLICY.md, name_variants.json)
  system/run            our entry point: system/run <data folder> <output file>
  system/screening/     our code (Python 3 standard library only)
  output/dev.jsonl      our predictions on dev
  validate.py           the organisers' checker and scorer (unchanged)
  output.schema.json    the output line schema (unchanged)
  POLICY.md             the SOP (same as dev/POLICY.md)
  OFFICIAL_README.md    the official brief (the kit's README.md)
  tests/                unit tests
  ```
- **Data format facts** (verified against the official files):
  - Alerts nest the screened details: `customer: {name, entity_type, dob, country, city}`. Read them with `normalize.screened_details(alert)`.
  - Hit list fields are JSON arrays.
  - `name_variants.json` is `{description, groups, company_legal_forms}`.
  - Practice labels use lists for `reason_codes`, `customer_record_ids`, `evidence` and `path`.
- `validate.py` accepts evidence items that are record IDs, URLs, or hit fields as `H-XXXXXX#field`.
- `dev/` and the brief (`Screening — Brief v3 (same person or not).docx`) are **committed while the repo is private**. `.gitignore` excludes `*.xlsx`, `.env`, Office lock files and the pasted `/screening/` kit copy.
- **System status:** the pipeline runs end to end.
  - **Placeholder customer lookup:** `customer.py` is A's file and will be replaced. It only follows links, but it already reads KYC and residence notes.
  - **Performance:** 819 hits in about 1 second; the output is byte-identical across runs.
  - **`validate.py --score`:** 0 problems, 40/50 decisions, **0 unsafe clearances**, decision score 74.1.
  - **The 10 misses are all alerts with no link** (A3: customer search).

## 3. Decisions already made

1. **The decision core is deterministic Python rules.** `POLICY.md` is a precise algorithm, and the practice labels' `reference_reason` text is templated, so the answers came from a rule engine. Rules also give full reproducibility.
2. **Hybrid, not classic RAG.** No embeddings or vector store, because:
   - every link is an exact key or an SOP-defined fuzzy rule
   - only the standard library is allowed, and indexes must be rebuilt each run on new customers
   - the 9 KB policy fits in one prompt
   - classic RAG adds run-to-run variance
3. **The LLM only reads text, never decides.** Code retrieves the exact records. Regex extracts first, and the LLM is a fallback extractor on that same text. Code checks that the value appears in the text; otherwise the fact is unknown.
4. **Optional LLM clearance veto.** It may only downgrade DE→REVIEW, never create DE or SAME. It is kept only if it doesn't hurt the dev score or the 5-run stability.
5. **LLM features are off by default** (`--llm` flag). They run at temperature 0, with a pinned model and provider and a JSON schema. On failure the fact is unknown, which leans toward REVIEW.
6. **When in doubt, REVIEW.** Parser uncertainty must never produce a clearance. Unknown stays unknown: a missing field is not a mismatch.

```
code: exact retrieval → code: regex extract → [LLM extract on same text if regex fails] → code: validate
      → code: SOP rules decide → [optional LLM clearance veto: DE→REVIEW only] → code: templated reason
```

## 4. Data facts (verified in `dev/`)

- **Alerts:**
  - 440 alerts and 819 hits; 395 are individuals and 45 companies.
  - Links: 170 `account_ref`, 70 `login_handle`, 54 `email`, and **146 with no link**, which need a search across 72k customers.
- **Joint accounts:** 52 accounts have more than one holder. The screened name and DOB pick between them.
- **Date formats:** ISO, `DD/MM/YYYY`, `17 June 1976`, `June 17, 1976`, `1976`, `1976-06`.
  - Slash dates are **day-first**: the first number is above 12 in 6,348 cases and the second never is.
  - Hit `dobs` is a `; `-joined mix of years and full dates.
- **Countries:**
  - Customers use names, ISO2 codes (`GB`, `NG`) and demonyms (`Nigerian`, `British`).
  - Hits use `countries`, `nationality`, `citizenship`, the last part of each `addresses` entry, and `place_of_birth`.
  - "International" and "Europe" are not countries.
- **KYC checks:** 49.6k approved, 2.5k rejected, 2.4k expired. Providers include "Companies registry lookup", used for companies.
- **Notes:**
  - The `kyc` channel (22.6k) holds verification sentences in **many phrasings**, carrying name, DOB, document country, provider and date. For example: "SULEIMAN YAHAYA, DOB 1956-08-08, was verified by Persona on 2025-07-05 via a Nigerian passport."
  - The phone and email channels include residence history, for example: "worked and lived in Pakistan from 2013 to 2015". The rest is noise.
- **Ages in hit profile notes** (first paragraph) are worded several ways: "aged 46", "38-year-old", "at the age of 43", "was 42 years old", "reached the age of 23". An age at a date gives two birth years.
- **Dated reports:** `According to <source>; <Month DD, YYYY>: …`. Some have double spaces, and some give a month-only date ("June 2016"). Whether month-only counts is still open; check against the labels.
- **Search results:**
  - The query is the hit name's lowercase words in alphabetical order.
  - Each snippet gives an age, a month and year, a **listing phrase** and a country.
  - A result is about the hit only if its listing phrase matches the hit's primary (or first) category **and** its country is tied to the hit.
- **Practice labels:**
  - 28 DE, 12 SAME, 10 REVIEW.
  - None use `DECEASED`, `ENTITY_TYPE_MISMATCH` or `AMBIGUOUS_CUSTOMER_RECORD`. These are rare in dev but present in the unseen set, so build unit tests for them from the SOP text.
  - `reason_codes` can list several accepted codes, and `customer_record_ids` can list several records of one person.
- **Resolution steps seen in the label `path` column:**
  - `account_ref → accounts → customer`
  - joint holders, picked by the screened name and DOB
  - `login_handle → accounts → customer`
  - `email → customers`
  - for unlinked alerts: name, date of birth, country and city → customers
  - same phone + DOB, or same document number on approved checks → one person
  - `customer → accounts → onboarding → latest approved check`
  - `customer email → notes`
  - `search results for the hit's name → SR (same role and country)`

## 5. Architecture (`system/`, Python 3 standard library)

The `[A]` and `[B]` tags show which workstream owns each file.

```
system/run                    [A] sh: exec python3 -m screening "$1" "$2"  (PYTHONPATH=system)
system/screening/
  models.py      [A+B] shared dataclasses: the contract between workstreams (section 6.1)
  load.py        [A] JSONL → records; accept lists or "; "-joined strings; build indexes
  normalize.py   [B] dates (partial-aware), countries (names/ISO2/demonyms gazetteer), name tokens
  names.py       [B] part matching + name agreement (SOP principle 8)
  notes_parse.py [A] kyc-note extractor (name, dob, doc country, provider, date, result) + residence-note extractor
  customer.py    [A] alert → candidate records → persons (union-find) → Person with fact→evidence-ID
  hit.py         [B] HitProfile: names/aliases, type, DOB candidates + source, earliest dated report, death date, countries
  policy.py      [B] decide(person, hit) → Decision; combine() across several persons
  explain.py     [B] templated 2–4 sentence reason using this hit's own facts
  llm.py         [A] (off by default) OpenRouter client via urllib + note-extraction fallback
  __main__.py    [A] run all hits in sorted order, write JSONL
tools/score.py   [A] own scorer: cost matrix, decision score, reason-field checks, per-hit diff with label `path`
tests/           [A] test_load, test_customer, test_notes · [B] test_normalize, test_names, test_hit, test_policy
```

### Key logic

**1. Customer resolution (SOP principles 2–4)**
- **Follow the link:**
  - `account_ref` → accounts.customer_id
  - `login_handle` → accounts → customer
  - `email` → customers.email
- **Multiple candidates:** if a link gives several, filter them with the screened details.
- **No link:** search a name-token index. Then keep records where:
  - the name agrees (full, preferred or login name)
  - the DOB is equal in every part both give
  - the country is the residence or nationality
  - the city appears in the record's city or address
- **Never use another customer's records.**
- **Group records into persons** (union-find) when they share:
  - the same phone **and** the same full DOB, or
  - the same document number on *approved* checks.

  Links chain transitively.
- **Profile:** the latest *approved* check comes from the KYC table **or** a kyc note, and gives the verified legal name, DOB and document country. Countries come from all records, the document, and residence notes.
- **Every fact carries its source record ID,** so the evidence can be cited.

**2. Hit facts (principle 5)**
- **DOB candidates** come from:
  - the `dobs` field
  - an age-at-date sentence in the first paragraph of the profile notes, giving two years
  - otherwise, relevant search results, each giving two years
- **Companies:** only `dobs` counts, as the incorporation date.
- **Time facts:** the earliest dated report, and the date of death.

**3. Policy (principles 6–7)**
- **Contradictions are checked in a fixed priority:** type → deceased → temporal (younger than 16 at the earliest report, or incorporated after it) → DOB → name (verified name only) → location.
- **Location exception:** a location mismatch is blocked when name and DOB agree; the hit becomes REVIEW.
- **Confirmation:**
  - Person: name + DOB agree.
  - Company: name + country agree.
  - Country also agreeing gives `NAME_DOB_LOCATION_MATCH`.
- **Otherwise:** `REVIEW INSUFFICIENT_DATA`.
- **Several persons fit:** decide the hit for each. If all agree, use that decision; otherwise `REVIEW AMBIGUOUS_CUSTOMER_RECORD`. In both cases `customer_record_id` is `AMBIGUOUS`.

**4. Evidence and reason**
- Cite only the IDs behind the deciding facts, as in the labels (for example `KYC-DE8245` alone for a DOB mismatch).
- The reason is a template filled with the actual dates, countries and names, in the style of the labels' `reference_reason`.

**5. Determinism**
- Sorted iteration everywhere and sorted evidence lists.
- No randomness and no dependence on set order.
- LLM settings pinned (see section 3).

## 6. Workstreams

The pipeline splits at one seam:
- **Workstream A** works out *who the customer is*.
- **Workstream B** works out *who the listed person is* and decides.

They meet in `models.py`. A produces `Person` objects, and B consumes them.

```
                 Workstream A (customer side)                    Workstream B (hit side + decision)
alerts ─► load ─► resolve(alert) ─► [Person, ...] ──┐   hits ─► build_hit(hit) ─► HitProfile
                    │  notes_parse, union-find      │                 │ normalize, names, search results
                    ▼                               ▼                 ▼
               Resolution.path              decide(person, hit_profile, alert) ─► Decision
                                                     combine([Decision, ...]) ─► output line (A writes it)
```

### 6.1 Shared contract: `system/screening/models.py` (agree at kickoff, then freeze)

```python
from dataclasses import dataclass, field
from typing import Optional, Any

@dataclass(frozen=True)
class PartialDate:            # unknown parts stay None ("unknown stays unknown")
    year: Optional[int]
    month: Optional[int] = None
    day: Optional[int] = None

@dataclass(frozen=True)
class Fact:                   # every fact remembers where it came from, for evidence
    value: Any                # str name | PartialDate | canonical country name | frozenset of years
    source_id: str            # exact record ID: "CUS-…", "KYC-…", "NOTE-…", "SR-…", "H-…"
    origin: str = ""          # e.g. "verified_kyc", "verified_note", "record", "residence_note", "dobs", "profile_age", "search"

@dataclass
class Person:                 # one real person/company = a cluster of customer records  [built by A]
    record_ids: list          # sorted CUS-… IDs
    entity_type: str          # "Individual" | "Company"
    verified_name: Optional[Fact] = None   # latest APPROVED check (KYC table or kyc note)
    verified_dob: Optional[Fact] = None    # same check; for companies = incorporation date
    declared_names: list = field(default_factory=list)  # full/preferred/login names on the records
    declared_dobs: list = field(default_factory=list)   # dob on the records
    countries: list = field(default_factory=list)       # residence, nationality, doc country, residence notes

@dataclass
class Resolution:             # [built by A]
    alert_id: str
    persons: list             # [] = no customer found, [p] = resolved, [p, q, …] = ambiguous
    path: list                # human-readable trace, like the labels' `path` column

@dataclass
class HitProfile:             # [built by B]
    hit_id: str
    alert_id: str
    entity_type: str
    names: list               # Facts: name + every alias, source_id = hit_id
    dob_candidates: list      # Facts with PartialDate or frozenset-of-years values
    dob_origin: Optional[str] # "dobs" | "profile_age" | "search" | None
    earliest_report: Optional[Fact] = None   # PartialDate of the earliest "According to …; <date>:" line
    death_date: Optional[Fact] = None
    countries: list = field(default_factory=list)

@dataclass
class Decision:               # [built by B]
    hit_id: str
    alert_id: str
    decision: str             # DIFFERENT_ENTITY | SAME_ENTITY | REVIEW
    reason_code: str
    customer_record_id: Optional[str]   # CUS-… | "AMBIGUOUS" | None
    reason: str
    evidence: list            # sorted IDs that decided it
```

**Function signatures each side provides:**

| Owner | Function | Notes |
|---|---|---|
| A | `load.load_data(folder) -> Data` | `Data` holds the raw rows and indexes (by account, login, email, applicant, phone, name token, search query) |
| A | `customer.resolve(alert, data) -> Resolution` | |
| A | `notes_parse.parse_kyc_note(text) -> dict \| None` | Keys: name, dob, doc_country, provider, checked_at, result |
| A | `notes_parse.parse_residence_note(text) -> list[str]` | Returns countries |
| B ✅ | `normalize.parse_date(s) -> PartialDate \| None` | ISO, day-first `DD/MM/YYYY`, `17 June 1976`, `June 17, 1976`, `1976`, `1976-06`, `2016/7/8` |
| B ✅ | `normalize.parse_date_list(v)`, `normalize.dates_compatible(a, b)`, `normalize.age_at(birth, on)` | List fields; "every part both give is equal" (use it for screened DOB vs record DOB) |
| B ✅ | `normalize.to_country(s) -> str \| None`, `normalize.to_countries(v)` | Names, ISO2/ISO3, demonyms, `[Residency]` tags, last part of a place. `International`/`Europe` → None |
| B ✅ | `normalize.find_countries(text, ignore_names=()) -> list[str]` | **A: use this in the note parsers** ("Nigerian passport", "lived in the Netherlands"). Pass the person's name in `ignore_names` |
| B ✅ | `normalize.name_parts(s, is_company, legal_forms)`, `normalize.split_list(v)` | `split_list` accepts a JSON array or a `; `-joined string |
| B ✅ | `names.Variants.load(data_folder)`, `names.names_agree(a, b, variants, is_company)` | **A: load `Variants` once and use `names_agree` for the no-link customer search** |
| B ✅ | `hit.build_hit(hit_row, data) -> HitProfile` | Needs `data.search_by_query` (dict: the raw `query` field → result rows), or that dict passed directly |
| B ✅ | `policy.decide(person \| None, hp, alert, variants) -> Decision` | |
| B ✅ | `policy.combine(decisions, hp, persons) -> Decision` | |
| B ✅ | `policy.decide_alert_hit(persons, hp, alert, variants) -> Decision` | **What `__main__` should call** for each hit: handles no person, one person, and several people |

**What B expects in each `Person` (A builds it):**
- `verified_name` / `verified_dob`: from the **most recent approved** check, whether that is a KYC-table row or a kyc-channel note. `source_id` is the `KYC-…` or `NOTE-…` ID.
- `declared_names`: the record's full, preferred and login names (`source_id` = `CUS-…`).
- `declared_dobs`: the record's dates of birth.
- `countries`: one `Fact` per (country, source), from:
  - residence and nationality on every record (`CUS-…`)
  - the approved check's document country (`KYC-…`/`NOTE-…`)
  - countries the residence notes say the person lived in (`NOTE-…`)

  The policy cites these `source_id`s as evidence, so they must be exact.

**B status:** B1–B6 are done (71 unit tests in `tests/`). With an oracle customer built from each label's `customer_record_ids`, B scores 48/48 decisions, 48/48 reason codes, 0 unsafe clearances, and evidence precision and recall of 1.00. The 2 ambiguous labels need A's resolver.

**Kickoff (both, about 30 minutes):**
1. Agree on and commit `models.py`.
2. Commit **stub** versions of every function above. Stubs return `None`, empty lists, or a REVIEW decision.
3. After that, each side works independently. A uses B's stubs (and real `parse_date`/`to_country` once B ships them, which is B's first task). B tests with hand-built `Person` objects until A's resolver lands.

### 6.2 Workstream A: customer side ("who is the customer?")

**Owns:** `system/run`, `__main__.py`, `load.py`, `customer.py`, `notes_parse.py`, `llm.py`, `tools/score.py`, tests for these.

1. **A1. Scaffold and scorer (first):**
   - `system/run` and `__main__.py`: loop over alerts and hits in sorted order and write JSONL.
   - `load.py`: accept list or `; `-joined fields; build the indexes.
   - `tools/score.py`: cost matrix, decision score, unsafe clearances, then reason-code, customer-ID and evidence checks, and a per-hit diff showing the label `path`.
   - **Done when** an all-REVIEW run scores 0 and `system/run dev output/dev.jsonl` works end to end.
2. **A2. Link resolution:**
   - `account_ref` → accounts (including joint holders, filtered by the screened name and DOB).
   - `login_handle` → accounts → customer.
   - `email` → customers.
3. **A3. Search for unlinked alerts (146 alerts):**
   - Search the name-token index.
   - Keep records where the name agrees (using B's `names_agree`, stubbed at first as exact-token overlap), the DOB is equal in every part both give, the country is residence or nationality, and the city is in the record's city or address.
4. **A4. Group records into persons:**
   - Union-find on phone plus the same full DOB, or the same document number on *approved* checks. Links chain transitively.
   - Several distinct persons go into `Resolution.persons`. Never mix in another customer's records.
5. **A5. Note parsers:**
   - `parse_kyc_note` covers the many verification phrasings. Measure it over all 22.6k kyc notes; target over 99% parsed, and list the failures.
   - `parse_residence_note` covers "worked and lived in X from … to …" and its variants.
   - Write paraphrase tests.
6. **A6. Build the `Person`:**
   - The verified name, DOB and document country come from the **most recent approved** check, from the KYC table *or* a kyc note. Ignore rejected and expired checks.
   - Countries come from every record, the document, and residence notes.
   - Every value is a `Fact` with its source ID.
   - **Done when** our `customer_record_id` matches the label's `customer_record_ids` (or `AMBIGUOUS`) for 50 of 50.
7. **A7. LLM client and note fallback (behind `--llm`):**
   - OpenRouter client in `llm.py`, using urllib, temperature 0, a pinned model and provider, a JSON schema, and a timeout.
   - Fallback for kyc and residence notes the regex can't parse. Check that the returned values appear in the text.
8. **A8. Final checks and submission:**
   - 5 runs give byte-identical output, and timing is recorded.
   - Write `output/dev.jsonl`.
   - Write the `system/README.md` sections on customer resolution, evidence and determinism.

### 6.3 Workstream B: hit side and decision ("who is the listed person, and is it the customer?")

**Owns:** `normalize.py`, `names.py`, `hit.py`, `policy.py`, `explain.py`, tests for these.

1. **B1. Normalizers (first, because A needs them):**
   - `parse_date`: ISO, `DD/MM/YYYY` (day-first), `17 June 1976`, `June 17, 1976`, `1976`, `1976-06`, and provider formats in hit profiles.
   - `to_country`: a gazetteer of names, ISO2 codes and demonyms. Territories count as their own country. Drop "International" and "Europe".
   - `name_parts`: casefold, strip accents, drop anything in brackets, drop punctuation, drop single letters (initials), drop placeholders (NA, N/A, TEST, UNKNOWN, XXX, NONE, digits), drop company legal forms, and count each distinct part once.
2. **B2. Name agreement (`names.py`, SOP principle 8):** two parts match when any of these holds:
   - they are identical
   - they are in the same variant group (watch out: `joseph` is in two groups)
   - they are the same parts written together or apart (Abdulsalam = Abdul Salam, counting as one part)
   - they are within the edit limit: 1 edit for 4–6 letters, 2 for longer, measured on the shorter part; parts under 4 letters must be identical; a swap counts as 2 edits

   Names agree when at least two parts match, or every part of the shorter name matches. Write a unit test for every clause.
3. **B3. Hit facts (`hit.py`):**
   - **Names:** the name plus all aliases.
   - **DOB candidates:**
     - from `dobs`
     - else from an age-at-date sentence in the first paragraph of the profile notes, giving two years ("aged 46", "38-year-old", "at the age of 43", "was 42 years old")
     - else from search results whose listing phrase matches the primary (or first) category and whose country is tied to the hit
   - **Companies:** only `dobs` counts.
   - **Time facts:** the earliest dated report (`According to …; <date>:`; tolerate double spaces; decide whether month-only dates count by checking the labels) and the death date.
   - **Countries:** countries, nationality, citizenship, the last part of each address, place_of_birth.
4. **B4. Policy (`policy.py`):**
   - **Contradictions, in order:** type → deceased → temporal (younger than 16 at the earliest report, or incorporated after it) → DOB (every candidate contradicted) → name (verified name only) → location.
   - **Location exception:** blocked when name and DOB agree; that hit becomes REVIEW.
   - **Confirmation:** a person on name + DOB (adding country gives `NAME_DOB_LOCATION_MATCH`); a company on name + country.
   - **Otherwise** `INSUFFICIENT_DATA`.
   - **Single-part names:** an individual customer whose names have fewer than two real parts can be neither confirmed nor cleared on name.
   - **`combine()`:** if all persons give the same decision, use it; otherwise `REVIEW AMBIGUOUS_CUSTOMER_RECORD`. With several persons, `customer_record_id = "AMBIGUOUS"`.
   - **No person found:** decide from the alert's screened details only; `customer_record_id = None`.
5. **B5. Explain and evidence (`explain.py`):**
   - Template reasons in the style of the labels' `reference_reason`, using the hit's own dates, countries and names.
   - Evidence is the minimal set of deciding IDs, sorted.
6. **B6. Rare-case tests:** `DECEASED`, `ENTITY_TYPE_MISMATCH`, `TEMPORAL_IMPOSSIBILITY` for companies, `AMBIGUOUS_CUSTOMER_RECORD`, and the location exception. Build them from the SOP text, because the dev labels have none of these.
7. **B7. Hit-side LLM pieces (behind `--llm`, using A's `llm.py` client):**
   - Fallback for age sentences and search snippets the regex misses.
   - The **clearance veto**, which may only change DE→REVIEW.
   - Measure each piece's effect on the score and on 5-run stability before keeping it.
8. **B8. README:** write the `system/README.md` sections on hit facts, decision rules, LLM prompts, and three worked cases (a mismatch, a match, a review).

### 6.4 Sync points

| When | What | Done when |
|---|---|---|
| Kickoff | `models.py` and stubs committed | `system/run dev out.jsonl` runs, all REVIEW |
| After B1 | B ships the real `parse_date`, `to_country`, `name_parts` | A's note parser and resolver use them |
| After A6 + B4 | **First full integration** on the 50 labels | `tools/score.py` runs on real decisions |
| Integration loop | Go through the per-hit diffs together. Each diff is either a resolution bug (A) or a facts/rules bug (B); the label `path` shows which | 50/50 decisions, **0 unsafe clearances** |
| After A7 + B7 | Decide on the LLM pieces from measurements | Each kept piece improves the score and stays reproducible |
| Final | 5-run determinism check, `output/dev.jsonl`, README merged | Ready to submit |

### 6.5 Git rules

- Each workstream uses its own branch (`ws-a-customer`, `ws-b-hit-policy`) and merges small PRs into `main` often.
- Edit only the files your workstream owns. Change `models.py` only by agreement, in its own small PR.
- `dev/` and the brief are committed **only while the repo is private**. The brief forbids publishing the dev data. Before going public, submit from a fresh repo containing only `system/` and `output/`, or purge `dev/` from history (`git filter-repo --path dev --invert-paths`).
- Never commit `.env` or the API key.
- `dev/` holds the official data room files. Don't edit them, and don't edit `validate.py` either.

## 7. Open questions and risks

- **Wording drift in the unseen set** for notes and age sentences. Mitigations: broad regex, paraphrase tests, the LLM fallback.
- **Over-clearing.** Any doubt must lead to REVIEW, never DE.
- **Unclear rule points:**
  - month-only dated reports
  - overlapping variant groups (`joseph` is in two groups)
  - whether a verified name can come from a kyc note (the SOP says yes for approved checks recorded in notes)
- **The unseen set may differ in shape** (arrays or `; `-joined strings, nested or flat alert details). The loader and `split_list` / `screened_details` accept both.
- **Still missing:** an OpenRouter key, needed only if we try the optional LLM layer.

## 8. Verification (the official pipeline)

```sh
python3 -m unittest discover -s tests                                                  # unit tests
system/run dev output/dev.jsonl                                                        # predictions (~1 s)
python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl   # official check + score
```

- `validate.py` must report **0 problems** and **0 unsafe clearances**.
- **Determinism:** run `system/run` 5 times and `cmp` the outputs; they must be byte-identical. `system/run` sets `PYTHONHASHSEED=0`, and every loop runs in sorted order.
