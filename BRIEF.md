# FinCrime Hackathon — Sanctions Screening (plain-English brief)

## The question in one line

**For each watchlist "hit", is this listed person/company actually our customer — or just someone with a similar name?**

That's it. Not "is this risky?", not "should we keep them?" — **only identity**.

## Background

A payments company checks every customer's name against watchlists (sanctions, PEPs = politically exposed persons, enforcement actions, adverse media). When a name looks similar, the system raises an **alert**. Each alert contains one or more **hits** — watchlist profiles that *might* be the customer. Today an analyst decides each hit by hand. We build a system that does it.

| Number | What |
|---|---|
| 379 | dev alerts |
| 766 | hits to decide (this is our output — one decision per hit) |
| 71,865 | customer records |
| 50 | practice labels (answered examples, with the reasoning path) |
| ? | hidden test set — same format, we never see it |

## The output: one decision per hit

| Decision | Meaning |
|---|---|
| `DIFFERENT_ENTITY` | Evidence proves it's someone else → hit cleared |
| `SAME_ENTITY` | Evidence proves it's the customer → goes to compliance |
| `REVIEW` | Can't tell → a human looks |

Plus, per hit:
- **one reason code** (must belong to the decision — table below)
- **the record IDs** the decision rests on
- **the customer record ID** we resolved (or `null`)

> ⚠️ **The worst mistake is clearing a hit that really is the customer.** When unsure → `REVIEW`.
> An alert is only cleared if *every* hit in it is `DIFFERENT_ENTITY`.

## The pipeline we need to build

```
alert ──► 1. find the customer ──► 2. build their "true" profile
                                          │
hit   ──► 3. gather the hit's facts ──────┤
                                          ▼
                              4. compare (names, DOB, country, type, dates)
                                          ▼
                              5. apply SOP rules → decision + reason + evidence IDs
```

### Step 1 — Find the customer
Customer data is scattered across systems that **don't share one key**:

```
Alerts.account_ref  → Accounts → Customers
Alerts.login_handle → Customers
Alerts.email        → Customers
Accounts → Onboarding → KYC checks (by applicant ID)
Customers.email → Notes (support/onboarding notes)
```

- If the alert carries a link, follow it.
- If not, search for customers that fit what was screened (name, DOB…).
- **Never** borrow facts from another customer's records.
- If **several different people** fit and they'd lead to **different** decisions → `REVIEW` / `AMBIGUOUS_CUSTOMER_RECORD`.

**Same-person rule:** records sharing **phone AND full date of birth** = same person.
Shared phone *or* address alone ≠ same person (families share these).

### Step 2 — Trust the right source
**Most recent *approved* KYC check** wins for legal name, DOB and document country.
Rejected or expired checks = ignore. Self-declared data is weaker than verified.

### Step 3 — Gather the hit's facts
The hit's DOB might be in:
- its `dobs` field,
- buried in a sentence in the profile notes, or
- only in web search results — **most of which are about namesakes**, so be careful.

### Step 4 — Compare names properly
Normalise before comparing:
- ignore case, accents, punctuation, brackets
- name variants: Muhammad / Mohammed / Mohamed (see `name_variants.json`)
- parts joined or split ("Abdul Rahman" vs "Abdulrahman")
- small typos
- aliases and nicknames count
- placeholders (`NA`, `TEST`, `UNKNOWN`) are **not** name parts

### Step 5 — Apply the SOP (POLICY.md)

**Clear (DIFFERENT_ENTITY) only on a contradiction:**

| Contradiction | Rule | Reason code |
|---|---|---|
| Time | Customer was <16 at the earliest dated report, or company incorporated after it | `TEMPORAL_IMPOSSIBILITY` |
| Deceased | Hit's date of death is before the customer was screened | `DECEASED` |
| DOB | Birth year >1 year off from **every** year the hit gives, **or** same year with month (or day) differing | `DOB_MISMATCH` |
| Location | **Every** customer country ≠ **every** hit country (but if name + DOB agree → `REVIEW`, not clear) | `LOCATION_MISMATCH` |
| Name | Verified legal name matches **none** of the hit's names/aliases | `NAME_MISMATCH_VERIFIED` |
| Type | Person vs company | `ENTITY_TYPE_MISMATCH` |

**Confirm (SAME_ENTITY) only on agreement, with nothing contradicting:**

| Situation | Reason code |
|---|---|
| Person: name + DOB + country agree | `NAME_DOB_LOCATION_MATCH` |
| Person: name + DOB agree | `NAME_DOB_MATCH` |
| Company: name + country agree | `NAME_LOCATION_MATCH` |

**Otherwise REVIEW:**

| Situation | Reason code |
|---|---|
| No contradiction, not enough to confirm | `INSUFFICIENT_DATA` |
| Multiple customers fit, different outcomes | `AMBIGUOUS_CUSTOMER_RECORD` |

## The data (in the data room's `dev/` folder, JSON Lines)

| File / tab | Rows | Purpose |
|---|---|---|
| Alerts | 379 | customer as screened, link fields, `hit_ids` |
| Hits | 766 | watchlist profiles — **decide each one** |
| Customers | 71,865 | system of record |
| Accounts | 86,227 | account numbers / logins → customers |
| Onboarding | 71,865 | accounts → KYC applicant IDs |
| KYC checks | 53,977 | verified identity checks (status, date, name, DOB, doc country) |
| Notes | 31,675 | support/onboarding notes, keyed by customer email |
| Search results | 16,791 | web results by name — mostly namesakes |
| Practice labels | 50 | worked answers — use to test our logic |
| Policy | — | `POLICY.md` (SOP) + `name_variants.json` |

The JSONL files are the source of truth; the workbook is just a read-only browsing view.

## Suggested build order

1. Load all JSONL files; index them by their join keys.
2. Customer resolver (Step 1–2), test it on the 50 practice labels' paths.
3. Hit fact extractor (fields + regex over notes + careful use of search results).
4. Name matcher with normalisation + variants.
5. Rules engine in the exact priority of the SOP, defaulting to `REVIEW`.
6. Score against practice labels; inspect every miss — especially any wrong `DIFFERENT_ENTITY`.
7. Run on full dev set; write output file in the required format.

## Open questions to check once we have the data
- Exact output format / file name expected for submission.
- Field names in each JSONL file.
- How scoring weights the three decisions (wrong clears are likely penalised hardest).
