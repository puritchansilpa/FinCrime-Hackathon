# Adversarial set

128 hits (126 alerts) in `adversarial/`. Every id starts with `ADV-`. Each case carries the records it needs. Answers follow `dev/POLICY.md`. Cases that turn on a point the policy leaves open are marked `ambiguous_policy: true`.

`practice_labels.jsonl` uses the practice-label fields (`decision`, `reason_codes`, `customer_record_ids`, `evidence`, `reference_reason`, `path`) plus `category`, `weakness`, what a naive implementation would output, `module` when a miss has a home, and the policy note when there is one.

The comparison baseline is the merged pipeline on `main` (commit `7ddca7b`; current `main` at `07ab92f` has the same decision path with the LLM off). This branch changes that code, only for the misses below. `python3 adversarial/build_dataset.py` rewrites the JSONL.

## Run

```
python3 adversarial/run.py
```

Validates the files and runs `system/run adversarial <output>`. Stdlib only. `--keep` leaves predictions at `adversarial/output/predictions.jsonl`.

## Counts

Decisions: 79 `SAME_ENTITY`, 27 `REVIEW`, 22 `DIFFERENT_ENTITY`.

The third batch (ADV-H-109 through ADV-H-128) is empty fields, bad dates and country names, and cultural names. By theme: empty fields 5 (4 `SAME_ENTITY`, 1 `REVIEW`), bad input 7 (4 `SAME_ENTITY`, 2 `REVIEW`, 1 `DIFFERENT_ENTITY`), cultural names 8 (6 `SAME_ENTITY`, 2 `DIFFERENT_ENTITY`).

## Current pipeline on this branch

`python3 adversarial/run.py`: accuracy 128/128, wrong `DIFFERENT_ENTITY` 0.

Practice labels: 50/50, 0 unsafe clearances. Five runs of `dev` are byte-identical. `output/dev.jsonl` and `output/review_queue.jsonl` on this branch are regenerated from that pipeline.

Two further fixes, on top of the phone, document, note and profile fixes:

- ADV-H-110. `policy.py` ignores a hit name with no real parts (`N/A`, `NA`, `TEST`, `UNKNOWN`, `XXX`, blank). A placeholder is missing, so it cannot be `NAME_MISMATCH_VERIFIED`. A real alias beside a placeholder can still mismatch.
- ADV-H-117. `normalize.py` already rejects a day the month does not have. `fallbacks.py` `_mk` now does the same (`calendar.monthrange`), so 31 Feb, 30 Feb, 31 Apr, month 13, year 0000 and 29 Feb 1900 stay unknown, and 29 Feb 2000 still parses. An unknown date cannot contradict.

Sweep of the same class. Changed only what could become a contradiction:

- `fallbacks.py` `to_country` read uppercase `NA` as Namibia before the placeholder list. `normalize.py` already returns nothing for `NA`, `N/A` and `UNKNOWN`. The fallback now does too, so a placeholder country cannot produce a location clear. No dev customer or hit uses these values.
- Empty `dobs` entries and unparseable dates are already dropped by `parse_date_list`. They never become a date.
- `1900-01-01` is left as a real date. ADV-H-118 is `DIFFERENT_ENTITY` `DOB_MISMATCH`, and `POLICY.md` does not call that date a placeholder. `1970-01-01` is left as a real date for the same reason.

Dev decisions versus `7ddca7b` (and versus current `main`, same decision path): 16 changed, 10 `REVIEW` to `DIFFERENT_ENTITY` and 6 `REVIEW` to `SAME_ENTITY`, each from an explicit "was born" sentence. The placeholder-name and impossible-date fixes change no further dev decision. H-0442F5 is `DIFFERENT_ENTITY` `DOB_MISMATCH`: the profile says the subject was born in 1973, and the verified date is 1981-06-10 from NOTE-407861 (CUS-929768).

The category table is `main` at `7ddca7b`, before any of these fixes.

| Category | Hits | Misses | Wrong clear |
|---|---|---|---|
| phone_dob_merge | 11 | 5 | 5 |
| document_merge | 8 | 5 | 5 |
| kyc_note | 8 | 6 | 6 |
| residence_note | 8 | 7 | 5 |
| explicit_dob | 8 | 6 | 1 |
| search_result | 9 | 4 | 0 |
| deceased | 11 | 4 | 0 |
| countries | 4 | 0 | 0 |
| ambiguous_customer | 4 | 0 | 0 |
| partial_dob | 4 | 0 | 0 |
| dob_boundary | 3 | 0 | 0 |
| multi_hit | 3 | 0 | 0 |
| kyc_status | 2 | 0 | 0 |
| verified_vs_declared | 2 | 0 | 0 |
| report_wording | 2 | 0 | 0 |
| temporal_company | 2 | 0 | 0 |
| temporal_person | 2 | 0 | 0 |
| entity_type | 2 | 0 | 0 |
| name_variant | 2 | 0 | 0 |
| name_shape | 2 | 0 | 0 |
| family | 1 | 0 | 0 |
| location_exception | 1 | 0 | 0 |
| not_a_country | 1 | 0 | 0 |
| profile_age | 1 | 0 | 0 |
| profile_scope | 1 | 0 | 0 |
| day_first | 1 | 0 | 0 |
| legal_form | 1 | 0 | 0 |
| placeholder | 1 | 0 | 0 |
| alias | 1 | 0 | 0 |
| name_edit | 1 | 0 | 0 |
| customer_link | 1 | 0 | 0 |

The second batch (ADV-H-59 through ADV-H-108) varies the seven misses: phone punctuation, trunk `0`, `00` prefix and extensions; document dashes, spaces, case and leading zeros; approved notes that mention an old or expired document; "raised in", "national of", "grew up in", "moved from", "originally from"; "born on", "b.", "DOB:" and "aged 45 in 2019"; listing phrases only in the search title; death dates only in the profile. Alongside those are controls a sloppy fix would get wrong: same phone or document with a different date of birth, a near-miss number, a rejected check, a relative's country or death, an age that belongs to the father, a namesake title, and a death on or after the screening date.

## After the fixes on this branch

On the first 108 hits the fixes score 108/108 with 0 wrong `DIFFERENT_ENTITY`. Practice labels stay 50/50 with 0 unsafe clearances. Against `7ddca7b`, 16 dev decisions changed: 10 `REVIEW` to `DIFFERENT_ENTITY` and 6 `REVIEW` to `SAME_ENTITY`, each from an explicit "was born" sentence about the listed person. Four more hits stayed `DIFFERENT_ENTITY` and only changed reason code, to `DOB_MISMATCH`.

The numbers below are `main` at `7ddca7b`, before those fixes.

## What main does

`python3 adversarial/run.py` on `7ddca7b`:

- decision accuracy 71/108
- wrong `DIFFERENT_ENTITY`: 22
- reason code correct on all 71 right decisions
- customer id 108/108 (any record of the person on the label counts)
- decision cost 1357

### Workstream A, customer side

`load.py` `phone_key`, used by `customer.py`. Digit strings that still differ are not joined, so the older check clears:

- ADV-H-03 `+49` versus `0049`
- ADV-H-62 national `0` versus `+44`
- ADV-H-63 `00` prefix versus `+33`
- ADV-H-64 extension `x99`
- ADV-H-65 extension `ext. 205`

Spaces, dashes and brackets (ADV-H-59, 60, 61) already share a digit string and pass. ADV-H-66, 67 and 68 must not merge (different full date, year-only date, one-digit-apart number).

`load.py` `norm_key`, used by `customer.py`. Internal spaces, dashes and leading zeros survive:

- ADV-H-04 space
- ADV-H-69 dash
- ADV-H-71 double space
- ADV-H-72 dash and space
- ADV-H-73 leading zeros

Case-only ADV-H-70 passes. ADV-H-74 (one digit apart) and ADV-H-75 (same number only on a rejected check) must not merge.

`notes_parse.py`, approved text that also says expired, rejected, or out of date. The note is dropped and the declared date of birth clears:

- ADV-H-07, ADV-H-76, ADV-H-77, ADV-H-79, ADV-H-82 expired or out of date
- ADV-H-78 previous check rejected, this one approved

ADV-H-80 is a check that really did expire: the clear is correct. ADV-H-81 is a clean approval and passes.

`notes_parse.py`, countries in free text. These phrases are missed, so France against the hit's country clears:

- ADV-H-10 grew up in
- ADV-H-83 raised in
- ADV-H-84 national of
- ADV-H-85 grew up in
- ADV-H-89 originally from

ADV-H-86 "moved from" is read and passes. ADV-H-87 and ADV-H-88 are the over-read: a sister who lives in Pakistan, and a brother who moved from Pakistan. The correct decision is `DIFFERENT_ENTITY`; the pipeline says `REVIEW`.

### Workstream B, hit side

`hit.py`. Birth sentences other than "aged N" are not read (`REVIEW` instead of `SAME_ENTITY`, except 95, which should clear):

- ADV-H-19, ADV-H-90 born on
- ADV-H-91 b.
- ADV-H-92 DOB:
- ADV-H-95 born on a date that contradicts the customer, so the correct decision is `DIFFERENT_ENTITY` and the pipeline says `REVIEW`

ADV-H-93 "aged 45 in 2019" passes. ADV-H-96 keeps a contradicting "born on" in the second paragraph, and the correct decision stays `REVIEW`. ADV-H-94 uses the father's age and wrongly clears (`DOB_MISMATCH`); that one is `ambiguous_policy`.

`hit.py`. The listing phrase is required in the snippet, so a phrase only in the title never supplies the age (`REVIEW` instead of `SAME_ENTITY`):

- ADV-H-22, ADV-H-97 PEP
- ADV-H-98 sanctions
- ADV-H-99 country named only in the title

ADV-H-100 has the phrase in the snippet and passes. ADV-H-101 (title phrase, country not the hit's) and ADV-H-102 (wrong listing kind) stay `REVIEW`.

`hit.py`. A date of death only in the profile notes is ignored, so the pipeline confirms (`SAME_ENTITY` instead of `DECEASED`). All four are `ambiguous_policy`, because the policy does not say the date must be in `deceased_date`:

- ADV-H-54 died on
- ADV-H-103 died on
- ADV-H-104 passed away
- ADV-H-105 date of death:

ADV-H-106 (after screening), ADV-H-107 (the father's death) and ADV-H-108 (on the screening date) stay `SAME_ENTITY`.
