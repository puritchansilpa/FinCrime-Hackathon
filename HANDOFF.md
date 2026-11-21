# HANDOFF: Priority 1 (the stage-1 score)

> **For the reader (human or LLM):** this is the split of the next block of work between **Ben** (working with Claude) and **Poom**.
> - Read `PLAN.md` for the background and `OFFICIAL_README.md` for the official rules.
> - Work only in the files your group owns. The one shared change is listed under "Contract".
> - Don't merge into `main` without passing the merge gate at the bottom.

## Where we are

- **`main` works end to end** on the official data:
  - `validate.py` reports 0 problems, 50/50 practice decisions, **0 unsafe clearances**, decision score 100.0.
  - The output is byte-identical across 5 runs, at about 20 s per run.
  - 150 unit tests pass.
- **The LLM is xAI only.** The event provides an xAI key and the organisers confirmed they score with xAI.
  - Model: `grok-4.20-0309-non-reasoning`.
  - The key lives in a gitignored `.env`; load it with `set -a; . ./.env; set +a`.
  - The LLM stays opt-in with `--llm`. On dev it makes 0 calls, because the regex reads every note.
  - The xAI conversion is on branch `llm-harness` and goes into `main` first (step 0 below).
- **How we're scored:** stage 1 is fully automatic. The organisers run `system/run <unseen data> <out>` 5 times; there is no UI. A wrong clearance costs **60 points**, while a missed clearance or a wrong REVIEW costs 2–3. **Priority 1 is about the unseen set**: new customers, new hits and new wording.

## Why the work is split this way

Work that affects the same code or the same measurement goes to one person:
- **Ben:** the **watchlist (hit) side and the decision rules**.
- **Poom:** the **customer side, the notes and the LLM harness**.

The two meet at one point only: the `unresolved_places` field (see "Contract").

---

## Step 0: Ben, before anything else
1. Merge `llm-harness` (the xAI conversion, verified to give identical output) into `main`, and push.
2. Both people start their branches from that `main`.

## Contract change ✅ done (Ben, branch `fix-failopen`)

In `system/screening/models.py`, add to **both** `Person` and `HitProfile`:
```python
unresolved_places: List[str] = field(default_factory=list)   # country-ish values we could not map
```

**The rule (implemented in `policy.py` by Ben):** if **either** side has any `unresolved_places`, the location is *unknown*. The policy must then **not** give `LOCATION_MISMATCH`, and the hit falls through to the other checks or to REVIEW.

**Why:** today an unmappable place is silently dropped. A hit tied to `London` (unmapped) and Pakistan therefore looks Pakistan-only and gets wrongly cleared against a UK customer. We reproduced this.

**What doesn't count as unresolved:** `International`, `Europe` and empty values. These aren't countries, as the SOP says.

---

## Ben + Claude: watchlist side and rules

**Branch:** `fix-failopen`. **Files:** `hit.py`, `normalize.py`, `countries.py`, `policy.py`, `explain.py`, `models.py` (the contract only), and tests in `tests/test_hit.py`, `tests/test_normalize.py`, `tests/test_policy.py`.

| # | Task | Done when |
|---|---|---|
| B1 ✅ | **Places the system can't map.** Fill `HitProfile.unresolved_places` with every hit country value `to_country` can't map. Add the policy rule above. | A hit with `addresses: ["London", "Karachi, Pakistan"]` against a UK-only customer is **not** cleared |
| B2 ✅ | **City and region lookup in `normalize.to_country`.** Major cities and regions (London, Lagos, Karachi, Dubai, Mumbai, Toronto, …) map to their country. Also strip prefixes ("Kingdom of", "Islamic Republic of", "Republic of", "State of") and handle the inverted form ("Korea, Republic of"). | `to_country("London") == "United Kingdom"`, `to_country("Kingdom of Saudi Arabia") == "Saudi Arabia"`. **Poom's customer side gets this automatically**, because `customer.to_country` calls `normalize.to_country` first |
| B3 | **Non-age numbers in search snippets.** In `snippet_age`, prefer explicit age wording ("aged 45", "33-year-old", ", 45,") and use the structural fallback only when none is found. Ignore numbers followed by units (thousand, million, %, percent, years in prison or sentence, people, votes, times) or preceded by a currency (USD, $, €, £, PKR, NGN, EUR). | "…was fined 50 thousand" gives **no** age. All 16,882 dev snippets still give the same age as today |
| B4 | **Category spellings.** `listing_category` matches on keywords: sanction → Sanctions; pep or politically exposed → PEP; enforcement → Enforcement; adverse or media → Adverse Media; soe or state-owned/state owned → SOE; anything else → "named on a watchlist". | `Politically Exposed Person`, `Sanction`, `Adverse-Media` and `State Owned Enterprise` each get the right listing phrase |
| B5 | **Birth dates stated directly in profile notes:** "born in 1974", "(born 3 May 1974)", "turned 45 in March 2019", "45 years of age". These become hit DOB candidates. | The probe sentences give the right birth year(s) |
| B6 | **More date formats in `parse_date`:** `03-May-1974` and `May-1974`. `c. 1974` and `1974 (approx.)` stay **unknown** on purpose, because an approximate year must never contradict. | Unit tests |
| B7 | **Search-results lookup that tolerates other query formats.** `hit.py` builds its own index keyed by `search_query(row["query"])`, so capitals or unsorted words in the unseen set still match. | The same 62 dev hits find search results as today |

**Order:** contract, B1, B2, P1 and P2 are ✅ done on `fix-failopen`. Next: B3, B4, then B5–B7.

**Moved to Ben (all place handling in one person's hands):** P1 and P2 below are done by Ben, in Poom's files. The changes are small and self-contained:
- **`customer.py`, `_person_from_records`:** collects `unresolved_places` from unmapped record countries, the newest check's unmapped document country (a new `doc_country_raw` key in `verified_checks`), and residence notes that read as residence but name no known place.
- **`notes_parse.parse_residence_note`:** also adds `normalize.find_place_countries(text)`, so cities and regions count.

Tests are in `tests/test_places.py`. Dev output is unchanged, byte-identical, because dev has no unmapped places.

---

## Poom: customer side, notes and the LLM harness

**Branch:** `llm-harness-2`, from `main` after step 0. **Files:** `customer.py`, `notes_parse.py`, `fallbacks.py`, `load.py`, `llm.py`, a new `templates.py`, a new `templates.json`, a new `tools/bench.py`, new `tests/bench/*.jsonl`, and tests in `tests/test_customer.py`, `tests/test_notes.py`, `tests/test_llm.py`, plus a new `tests/test_templates.py`.

| # | Task | Done when |
|---|---|---|
| P1 ✅ (Ben) | **Places the system can't map, customer side** (needs the contract PR). Fill `Person.unresolved_places` with every residence, nationality, document-country or residence-note place that can't be mapped. | A customer whose record says `residence_country: "Lagos"` has it listed as unresolved, or mapped once B2 lands |
| P2 ✅ (Ben) | **The "called Lagos home" case in residence notes.** Switch `notes_parse` from `fallbacks.find_countries` to `normalize.find_countries`, which becomes city-aware with B2, or make `fallbacks` call it. When a residence note names a place that maps to no country, add the place to `unresolved_places`. | "The customer previously called Lagos home, from 2012 until 2019" gives Nigeria (after B2), never just an empty list |
| P3 | **Template learner** (`templates.py`; agreed design below). | Passes the **go/no-go** and the bench criteria |
| P4 | **Test bench cases** in `tests/bench/notes.jsonl`, in the agreed format below. At least 100 reworded KYC and residence notes, including: name in normal case with no cue word, DOB with no birth cue, a city but no country, rejected/expired/pending wording, two dates in either order, and a non-English-style date order. | The file exists, and every case has its `expected` facts filled in by hand |
| P5 | **Bench runner** (`tools/bench.py`). Runs the bench through (a) regex only, (b) regex + template learner, (c) regex + learner + LLM. Scores each fact as right, wrong or unknown, and runs (c) 5 times to check stability. | Prints a table per mode: fields right, wrong and unknown, plus whether the 5 runs were identical |

**Template learner design (agreed in the grilling session):**
1. **The regex goes first.** A note reaches the learner only when a trigger fires: a needed fact is missing (name, DOB or document country), the regex found two possible values, a place has no country, or the result is unclear. Only the resolved customer's notes count, never all 31,895.
2. **Mask the note into a shape:** names, dates, countries, providers and document types become `<NAME>`, `<DATE>` and so on, reusing the existing recognisers. Notes with the same shape share one template.
3. **Known shapes** go through their compiled regex. **New shapes** get **one** xAI call, on the note with the **lowest `note_id`** for that shape. The call returns a field mapping, which is checked, compiled into a regex, and applied to every note with that shape.
4. **Every LLM answer is checked:**
   - the value appears in the note text
   - it's plausible (the DOB is before the check date; the person was 16–110 at the check)
   - the country is in our country table
   - if the regex read the same fact differently, the fact becomes **unknown**

   A failed check gives **unknown, never a guess**.
5. **Storage:** dev templates are learned now and **committed in `system/screening/templates.json`**. New shapes in the unseen set are learned **in memory during the run**. Nothing is cached outside `system/` between runs.
6. **Go/no-go:** masking must collapse dev KYC notes to about **100 templates or fewer**. A quick test with a naive mask produced 14,234, because names in normal case slipped through, while the real phrasings look like roughly 60. If it can't get to about 100, keep the per-note fallback that already exists.
7. **Placement:** a two-line hook in `notes_parse` calls `templates.py` where the triggers fire. Dev output must stay **byte-identical**.

**Bench case format (agreed):**
```json
{"case_id": "kyc-017", "channel": "kyc", "created_at": "2024-05-01",
 "text": "Passport (Brazil) checked by Onfido on 2024-05-01: Ana Paula Lima, 03/05/1974.",
 "expected": {"name": "Ana Paula Lima", "dob": "1974-05-03", "doc_country": "Brazil",
              "result": "approved", "countries": []}}
```
**Pass criteria for turning the LLM on by default** (a joint decision once P3–P5 are done):
- it reads **more facts right** than regex alone
- it **never turns an unknown into a wrong value**
- all 5 runs are **identical**

Ben will add about 20 held-out cases that Poom hasn't seen, so the learner isn't only scored on cases written by the person who built it.

---

## Integration status (P3–P5 and the adversarial set merged into `main`)

**Merged:** `fix-failopen`, `Poom` (P3–P5) and `Poom_adversarial`, including Poom's latest 4 commits.

**Gate results:**
- 205 tests pass.
- `validate.py`: 50/50 practice decisions, 0 unsafe clearances.
- Adversarial set: 128/128, 0 wrong clearances.
- P5 bench: 0 wrong in every mode; with the LLM, 376 facts right, 0 unknown, 5 runs identical.
- `check_runs` (5 runs): identical.
- Template learner: 111 shapes, so the go/no-go passes.

**Changes made in Poom's files during integration** (pull before editing them):
- **`notes_parse.py`:**
  - country codes are never names ("NG", "U.S.")
  - a code next to a document word gives the document country ("passport (GB)")
  - a city gives the document country ("issued in Lagos")
  - dotted dates ("1979.08.30")
  - a trailing LTD/LLC is kept in the name
  - a holiday or trip is not residence
  - `extend_name` keeps name particles ("Maria Clara dos Santos")
  - `residence_without_place` (the unknown-place flag) skips relatives and trips
- **`llm.py`:** the check result comes from the note's wording, never the model. LLM names go through `extend_name`.
- **`templates.py`:** shapes the LLM learned take their result from the wording, and names go through `extend_name`.
- **`hit.py` (Ben):**
  - a birth date must directly follow "born / born on / b. / DOB:"
  - a death in the notes counts only for the listed person ("<name> died on", "He/She died on", "Date of death:")
- **`fallbacks.py` and `policy.py`:** Poom's own versions of the placeholder-name and impossible-date fixes were kept; mine were dropped.

**Dev output:** compared with Poom's regenerated `output/dev.jsonl`, one hit differs. H-2C6B2E's profile says "DOB: 6/20/1955" and is now read as a full date, so a customer born 1955-11-19 is cleared on DOB_MISMATCH instead of being matched on the year alone.

**LLM:** it now passes all three bench criteria. It stays opt-in (`--llm`) until we decide how the submission run is done: the organisers may only compare the output file we send.

## Sync points
1. **Step 0 (Ben):** `llm-harness` goes into `main`.
2. ✅ **Contract, B1, B2, P1, P2 (Ben):** `fix-failopen` goes into `main`. Poom works only on P3–P5 (template learner, bench cases, bench runner). When P3 hooks into `notes_parse`, pull `main` first: `parse_residence_note` changed.
3. **B3–B7 (Ben)** continue on a new branch.
4. **Both branches merged** through the gate.
5. **Bench results (both):** decide whether the LLM goes on by default.

## Merge gate (every merge into `main`)
```sh
python3 -m unittest discover -s tests                                                     # all pass
system/run dev output/dev.jsonl                                                           # 0 errors
python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl  # 0 problems, 0 unsafe
python3 tools/check_runs.py dev --runs 5                                                  # ALL RUNS IDENTICAL
```
Any change to dev decisions must be explained in the PR, with the hit IDs. A change from REVIEW to DIFFERENT_ENTITY needs a second pair of eyes.

## Later (not part of Priority 1)
- **README** (stage 2, read by the finalist judges):
  - **Poom:** customer side and the "production design" (resolve every customer ahead of time; cache hits).
  - **Ben:** hit side, policy, LLM harness, and three worked cases.
- **`review_queue.jsonl`:** `system/run` writes this second file. Check with the organisers against "writes one line per hit", or put it behind a flag (Poom).
- **Analyst review UI** for stage-2 UX: reads `output/dev.jsonl` and `review_queue.jsonl`, outside `system/run` (Poom, if time allows).
- **Submission** (Ben): a fresh public repo with only `system/` and `output/`, no `dev/` and no keys; then the final gate.
