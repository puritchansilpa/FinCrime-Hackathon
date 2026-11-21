# Same person or not? Screening hit adjudication

For every watchlist hit, the system decides whether the listed profile is the bank's
customer: `DIFFERENT_ENTITY` (cleared), `SAME_ENTITY`, or `REVIEW`. Each decision comes
with a reason code from `POLICY.md`, the IDs of the records that decided it, the
resolved customer record, and a short reason in plain English.

```
system/run <data folder> <output file> [--llm]
```

For the development set: `system/run dev output/dev.jsonl` (the official data
room lives in `screening/`, which is git-ignored).

- Python 3 standard library only. No packages to install.
- Reads only the given folder and writes one JSON line per hit, sorted by `hit_id`.
- The LLM is **off** unless you pass `--llm` and set `OPENROUTER_API_KEY`.
- A dev run (819 hits, 72k customers) takes about 20 seconds; the limit is 30 minutes.

## Architecture

```
                 Workstream A: who is the customer?                 Workstream B: who is listed, and is it them?
alerts ─► load ─► resolve(alert) ───────────────► [Person, ...] ─┐   hits ─► build_hit(hit) ─► HitProfile
            │      1 follow the link / search                     │              │ dates, countries, names,
            │      2 group records into persons                   │              │ profile notes, search results
            │      3 verified facts (KYC table + kyc notes)       ▼              ▼
            │      4 countries (records, document, notes)    decide(person, hit_profile, alert) ─► Decision
            │                                                combine([Decision, ...]) ─► one output line
            └─► indexes: account, login, email, phone, name token, birth year, applicant, document, notes
```

| Module | Owner | Job |
|---|---|---|
| `load.py` | A | Reads the JSON Lines files in the official format (screened customer nested under `customer`, arrays, `groups` in `name_variants.json`), also accepts flat or `; `-joined variants and hits inside alerts, allows missing files, and builds every lookup index. |
| `customer.py` | A | Alert → customer records → persons → `Person` with sourced facts. |
| `notes_parse.py` | A | Reads identity checks and residence history out of free-text notes. |
| `fallbacks.py` | A | A's stand-ins for dates, countries and name matching, written to the SOP; used only where B's functions return nothing. |
| `llm.py` | A | Optional OpenRouter client; only reads notes the regex could not. |
| `__main__.py` | A | Runs every hit and writes the output. A hit that crashes becomes `REVIEW`, never a clearance. |
| `normalize.py`, `names.py`, `hit.py`, `policy.py`, `explain.py` | B | Hit facts, the SOP rules, reasons and evidence. |
| `models.py` | A+B | The shared contract (`Person`, `HitProfile`, `Decision`, `Fact`, ...). |

## Resolving the customer (Workstream A)

The customer's picture is spread over five systems that share no key: customer
records, accounts, onboarding, KYC checks and support notes. `customer.resolve(alert)`
rebuilds it in four steps. Each step is logged in `Resolution.path` in the same style as
the practice labels' `path`, so a wrong answer can be traced.

**1. Find the records the alert is about** (SOP principle 2)

- **The alert has a link.** Follow it: `account_ref` → accounts → customer,
  `login_handle` → accounts → customer, or `email` → customer. Matching ignores case
  and spaces. A single linked record is trusted.
- **The link leads to several records** (a joint account: 58 in dev). The screened
  details pick between them exactly as in a search (below). This drops a family member
  who shares only the surname and phone. If nobody fits, every holder is kept, so the
  rules can only clear the hit if every one of them is contradicted.
- **The alert has no link** (146 in dev). Search for records that fit what was screened:
  - a full, preferred or login name that agrees with the screened name under the SOP's
    name rules (variants, parts written together or apart, small edits);
  - a date of birth equal to the screened one in every part both give (a screened
    "1990" fits "1990-04-05");
  - the screened country as the record's residence or nationality (codes and demonyms
    count: `GB`, `British`, `United Kingdom`);
  - the screened city in the record's city or address;
  - the same entity type (person or company).

  Candidates come from a name-token index (with the name variants) **and** a
  birth-year index, so a name with a typo in every part is still found.
- Unknown is never a mismatch: a missing or unreadable screened detail rules nobody out.

**2. One person, one picture** (principle 3)

Records belong to the same person when they share a phone number **and** the same
full date of birth, or when their approved identity checks carry the same document
number. Links chain (union-find), and a linked record joins the person even if it did
not fit the alert itself. A shared phone with a different or partial date of birth
never links (families share phones), and rejected or expired checks never link.
If more than one person remains, each is passed to the rules separately, and the
decisions are combined into one, or into `REVIEW` / `AMBIGUOUS_CUSTOMER_RECORD`.

**3. Verified beats declared** (principle 4)

For each person, the **most recent approved** identity check gives the verified legal
name, date of birth (incorporation date for companies) and document country. The check
can be a row in the KYC table (customer → accounts/onboarding → applicant → checks) or
a sentence in a kyc note filed under the customer's email. Rejected, expired and
unreadable checks are not evidence. A field the newest check lacks comes from the next
newest approved check.

Notes are free text and the unseen set words them differently, so the note parser does
not use templates. It finds each fact by what it looks like:

| Fact | How it is read |
|---|---|
| Name | The run of capitalised words (names are written in capitals), else the words after "for", "holder", "name". |
| Date of birth | The date nearest a birth cue ("DOB", "born", "date of birth"), else the date that is not the check date, else a bare year after "born". |
| Check date | The date equal to the note's `created_at`, else the date after "on" / "as of". |
| Document country | The one country named outside the person's name. Two different countries means unknown. |
| Result | Approved on success words; rejected or expired on failure words; otherwise unknown, which is not evidence. |

On dev it reads all 22,575 kyc notes (`tools/check_notes.py dev`). Tests cover
paraphrases that are not in dev, including rejected and expired checks.

**4. Countries tied to the customer** (principle 6, location)

The residence and nationality on **every** record of the person, the verified document
country, and every country a support note says they lived or worked in ("worked and
lived in Pakistan from 2013 to 2015"). More countries only make a location clearance
less likely, so the residence reader leans towards including a country.

**Results on dev** (`tools/check_resolution.py dev`):

- 50/50 labelled alerts resolve to exactly the person(s) the label names, including
  the two `AMBIGUOUS` alerts.
- Every `KYC-…` / `NOTE-…` record a label cites is among our facts.
- All 294 linked alerts resolve; 146 searches find 1 person (119), 2 (17) or more (10).
- All 486 resolved persons have a verified name and date of birth.

## How evidence is represented

Every fact is a `Fact(value, source_id, origin)`:

- `value` is the normalised value: a name string, a `PartialDate`, or a canonical
  country name;
- `source_id` is the exact record ID it was read from, as written in the files
  (`CUS-…`, `KYC-…`, `NOTE-…`, `SR-…`, `H-…`);
- `origin` says what kind of fact it is (`verified_kyc`, `verified_note`,
  `nationality`, `residence_country`, `document_country`, `residence_note`, ...).

So when the rules clear a hit on date of birth, the evidence is just the source of the
two dates that decided it, for example `["KYC-DE8245"]`, not everything that was looked
at. Dates are `PartialDate(year, month, day)` with unknown parts left as `None`, so a
missing month is never treated as a mismatch.

## Staying the same from run to run

- No randomness. Alerts, hits, candidates, records, persons, checks and evidence are all
  processed in sorted order. Every index holds sorted lists, so nothing depends on
  file order or on Python's hash order.
- Ties have explicit tie-breakers (for example, two checks on the same day are ordered by
  source kind, then ID).
- The output is written sorted by `hit_id`, with a fixed field order and `\n` line endings.
- With `--llm`: temperature 0, a fixed seed, a pinned model and provider with fallbacks
  off, a JSON schema, and a cache so the same note always gives the same answer. An LLM
  failure means "unknown", which can only push a hit towards `REVIEW`.
- `tools/check_runs.py dev --runs 5` runs the system five times in separate processes and
  compares the outputs byte for byte. On dev, all five are identical.

## Model and prompts (only with `--llm`)

The LLM never decides a hit. It only reads a note the regex could not fully read:

- a kyc note missing its name, date of birth or result: it is asked for those fields,
  verbatim, as JSON;
- a note about living or working somewhere where no country was recognised: it is asked
  for the countries, verbatim.

Code then checks that every returned value appears in the note and parses; anything
else is dropped as unknown. On dev the regex reads every note, so the LLM is not called.

| Setting | Default |
|---|---|
| `OPENROUTER_MODEL` | `anthropic/claude-haiku-4.5` (check the slug on OpenRouter and pin it) |
| `OPENROUTER_PROVIDER` | `anthropic`, with fallbacks off |
| `LLM_TIMEOUT` | 30 seconds per request, 3 attempts |
| `LLM_CACHE_FILE` | unset; set it to keep answers on disk across runs |

## Time and cost of a run

| | Dev set |
|---|---|
| Hits | 819 |
| Time (no LLM) | about 20 s (loading about 9 s, resolving about 11 s) |
| LLM calls | 0 on dev (the regex reads every note) |

## Tools

| Command | What it checks |
|---|---|
| `python3 -m unittest discover tests` | Unit tests (no network) |
| `python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl` | The official format check and practice score |
| `python3 tools/score.py output/dev.jsonl dev/practice_labels.jsonl --data dev` | The brief's cost matrix, unsafe clearances, reason checks, per-hit diff with the label path |
| `python3 tools/check_resolution.py dev` | Customer resolution against the labels, plus an audit of every alert |
| `python3 tools/check_notes.py dev` | How much of every note the parsers can read |
| `python3 tools/check_runs.py dev --runs 5` | Byte-identical output across runs, and timing |

## Hit facts, decision rules and worked cases (Workstream B)

*To be written by Workstream B: how the hit's names, dates of birth (`dobs`, profile
age sentences, filtered search results), dated reports, death date and countries are
gathered; the order the SOP rules are applied; and three worked cases (a clear
mismatch, a match, and one left for review).*
