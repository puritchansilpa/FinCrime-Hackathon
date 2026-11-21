# Conversion notes

Rebuilt from `Screening Dev Set - browse.xlsx` by `tools/xlsx_to_jsonl.py`.
Replace this folder with the data room's real JSON Lines files if they become available.

## Row counts

- `alerts.jsonl`: 440
- `hits.jsonl`: 819
- `customers.jsonl`: 72265
- `accounts.jsonl`: 86659
- `onboarding.jsonl`: 72265
- `kyc_checks.jsonl`: 54488
- `notes.jsonl`: 31895
- `search_results.jsonl`: 16882
- `practice_labels.jsonl`: 50

## Cells cut at 32,000 characters in the workbook

- `hits.jsonl` H-33106C: `profile_notes`
- `hits.jsonl` H-E7BFE8: `profile_notes`

## Format guesses

- List fields are kept as `; `-joined strings, as in the workbook.
- `name_variants.json` structure (`name_variants`, `company_legal_forms`) is a guess.
- Policy section headings were turned into Markdown headings.
