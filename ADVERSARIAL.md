# Adversarial set

58 hits (56 alerts) in `adversarial/`. Every id starts with `ADV-`, so the set cannot be mixed up with `dev/`. Each case carries the records it needs: nothing here points at a dev id. Answers follow `dev/POLICY.md`. Three cases turn on a point the policy leaves open; those are marked `ambiguous_policy: true`.

`practice_labels.jsonl` uses the practice-label fields (`decision`, `reason_codes`, `customer_record_ids`, `evidence`, `reference_reason`, `path`) plus, per hit: `category`, `weakness`, what a naive implementation would output, and the policy note when there is one. `reference_reason` is written in the same templated style as the dev labels.

There is no remote branch `Poom_2`. The system under test is the merged pipeline on `main` (commit `292c98d`: Workstream A customer resolution plus Workstream B hit facts and rules). This branch does not change that code.

## Run

```
python3 adversarial/run.py
```

That validates the files (every cited id exists, every label's reason code belongs to its decision) and runs `system/run adversarial <output>`. Stdlib only. Add `--keep` to leave the predictions at `adversarial/output/predictions.jsonl`.

`python3 adversarial/build_dataset.py` rewrites the JSONL from the case list and checks that resolution still sees the intended people.

## What is in it

| Category | Hits | What it presses |
|---|---|---|
| family | 1 | Shared phone, address and surname must not merge |
| phone_dob_merge | 1 | Same number written `+49…` and `0049…`, plus the same full date of birth, must merge |
| document_merge | 1 | Same document number with a space in it, on approved checks, must merge |
| kyc_status | 2 | Latest approved check, not a newer rejected or expired one |
| kyc_note | 1 | An approved note that mentions an old passport had expired |
| verified_vs_declared | 2 | Verified date of birth, or verified name, beats the record |
| residence_note | 1 | "Grew up in Pakistan" is a country tied to the customer |
| countries | 4 | Several countries on either side; document country; `GB` / `British` / `UK` |
| location_exception | 1 | Name and date of birth agree, countries do not: review, not a clear |
| not_a_country | 1 | Europe and International are not countries |
| profile_age | 1 | Age in the first paragraph gives two birth years |
| profile_scope | 1 | An age in the second paragraph does not count |
| explicit_dob | 1 | "Born on 12 March 1975" in the first paragraph is the date of birth |
| search_result | 3 | Namesake snippet ignored; listing plus country used; phrase only in the title |
| partial_dob | 4 | Year only, year-month, same-year month clash, one of several listed dates |
| dob_boundary | 3 | One year and one day apart; a year just outside an age pair; same month, different day |
| day_first | 1 | `05/06/1980` is 5 June |
| temporal_person | 2 | Turns 16 on the report date, and the day before |
| report_wording | 2 | Month-only line, and a sentence that is not "According to …; Month DD, YYYY:" |
| temporal_company | 2 | Incorporated on the report date, and the day after |
| legal_form | 1 | GmbH and Ltd are not name parts |
| entity_type | 2 | Person versus company, both directions |
| placeholder | 1 | Verified name `TEST UNKNOWN` cannot confirm or clear |
| alias | 1 | Single-part alias `Chen` agrees |
| name_variant | 2 | Yusuf/Joseph, Bob/Robert |
| name_edit | 1 | Smyth/Smith, one edit |
| name_shape | 2 | Abdulsalam / Abdul Salam; accents, brackets, honorific, swapped order |
| ambiguous_customer | 4 | Two people, same decision; two people, different decisions; shorter name pulls in a father; "York" inside "York Road" |
| multi_hit | 3 | One alert, three hits, only one is the customer |
| deceased | 5 | On the screening date, the day before, after, year-only, and a date only in prose |
| customer_link | 1 | Email link matches nobody |

Decisions: 32 `SAME_ENTITY`, 15 `REVIEW`, 11 `DIFFERENT_ENTITY`. On 42 of the hits that are not clears, the dangerous naive output is a wrong `DIFFERENT_ENTITY`.

## What the current pipeline does

`python3 adversarial/run.py` against this branch:

- decision accuracy 51/58
- wrong `DIFFERENT_ENTITY`: 4
- reason code matches on all 51 correct decisions
- customer id 58/58, counting any record of the person named on the label
- decision cost 247 (each wrong clear costs 60)

The four wrong clears:

| Hit | Gold | Pipeline | Why |
|---|---|---|---|
| ADV-H-03 | SAME_ENTITY | DIFFERENT_ENTITY `DOB_MISMATCH` | `+49 15123456789` and `004915123456789` are not joined, so the old check (Marcus Hale, 1970) is used instead of Bobby Nguyen |
| ADV-H-04 | SAME_ENTITY | DIFFERENT_ENTITY `DOB_MISMATCH` | `LQ 448219` and `LQ448219` are not the same document number, so Helen Kruger's check is used instead of Ines Navarro |
| ADV-H-07 | SAME_ENTITY | DIFFERENT_ENTITY `DOB_MISMATCH` | The approved note says the previous passport expired, the note is dropped, and the declared 1970 date of birth clears the hit |
| ADV-H-10 | REVIEW | DIFFERENT_ENTITY `LOCATION_MISMATCH` | "Grew up in Pakistan" is not read, so France against Pakistan clears |

Three more misses, none of them a wrong clear:

| Hit | Gold | Pipeline |
|---|---|---|
| ADV-H-19 | SAME_ENTITY | REVIEW. The first paragraph says "born on 12 March 1975". Only an "aged N" sentence is read. |
| ADV-H-22 | SAME_ENTITY | REVIEW. The listing phrase is in the result title, and only the snippet is checked. |
| ADV-H-54 | DIFFERENT_ENTITY `DECEASED` | SAME_ENTITY. The death date is in the profile notes, not `deceased_date`. Marked `ambiguous_policy`. |

The other two open cases are ADV-H-55 (does "York" in "York Road" count as the city?) and ADV-H-57 (an email link that matches nothing: search, or stop?). The pipeline's reading matches the label on both.
