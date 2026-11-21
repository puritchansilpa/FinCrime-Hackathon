"""A tiny hand-made data folder for tests (never real dev data)."""
import json
import os

ALERTS = [
    {"alert_id": "A-2", "screened_at": "2026-11-01", "customer_name": "Ana Silva", "entity_type": "Individual",
     "dob": "1980-01-02", "country": None, "city": None, "account_ref": "ACC-J", "login_handle": None,
     "email": None, "hit_count": 2, "hit_ids": "H-3; H-1"},
    {"alert_id": "A-1", "screened_at": "2026-11-02", "customer_name": "Bob Jones", "entity_type": "Individual",
     "dob": None, "country": "GB", "city": None, "account_ref": None, "login_handle": None,
     "email": None, "hit_count": 1,
     # real files may embed hits instead of listing IDs
     "hits": [{"hit_id": "H-2", "name": "Jones, Bob", "entity_type": "Individual", "dobs": ["1970", "1971"]}]},
]
HITS = [
    {"hit_id": "H-1", "alert_id": "A-2", "name": "Silva, Ana", "entity_type": "Individual",
     "dobs": "1980; 1981-01", "aliases": None},
    {"hit_id": "H-3", "alert_id": "A-2", "name": "Ana Sylva", "entity_type": "Individual", "dobs": None},
    {"hit_id": "H-9", "alert_id": "A-MISSING", "name": "Orphan", "entity_type": "Company"},
]
CUSTOMERS = [
    {"record_id": "CUS-2", "entity_type": "Individual", "full_name": "Ana Silva", "dob": "02/01/1980",
     "email": "Ana.Silva@x.example", "phone": "+351 912 000 111"},
    {"record_id": "CUS-1", "entity_type": "Individual", "full_name": "Ana Silva Costa", "dob": "1980-01-02",
     "email": "ana2@x.example", "phone": "+351912000111"},
]
ACCOUNTS = [
    {"account_id": "ACC-J", "customer_id": "CUS-2", "login_handle": "anas1", "phone": None},
    {"account_id": "ACC-J", "customer_id": "CUS-1", "login_handle": "anas2", "phone": None},
]
ONBOARDING = [{"account_id": "ACC-J", "customer_id": "CUS-2", "kyc_applicant_id": "APP-1"}]
KYC = [
    {"check_id": "KYC-2", "applicant_id": "APP-1", "verified_name": "Ana Silva", "verified_dob": "1980-01-02",
     "document_number": "P1", "document_country": "Portugal", "result": "approved", "checked_at": "2024-05-01"},
    {"check_id": "KYC-1", "applicant_id": "APP-1", "verified_name": "Ana Silva", "verified_dob": "1980-01-02",
     "document_number": "P1", "document_country": "Portugal", "result": "rejected", "checked_at": "2023-05-01"},
]
NOTES = [{"note_id": "NOTE-1", "requester_email": "ana.silva@x.example", "created_at": "2024-01-01",
          "channel": "kyc", "text": "Persona verified ANA SILVA."}]
SEARCH = [{"result_id": "SR-1", "query": "ana silva", "title": "t", "snippet": "s", "source": "x"}]
LABELS = [
    {"hit_id": "H-1", "alert_id": "A-2", "decision": "DIFFERENT_ENTITY", "reason_codes": "DOB_MISMATCH",
     "customer_record_ids": "CUS-2", "evidence": "KYC-2", "path": "p"},
    {"hit_id": "H-2", "alert_id": "A-1", "decision": "SAME_ENTITY",
     "reason_codes": "NAME_DOB_LOCATION_MATCH; NAME_DOB_MATCH",
     "customer_record_ids": "CUS-1; CUS-2", "evidence": "CUS-1; KYC-2", "path": "p"},
    {"hit_id": "H-3", "alert_id": "A-2", "decision": "REVIEW", "reason_codes": "INSUFFICIENT_DATA",
     "customer_record_ids": "AMBIGUOUS", "evidence": "", "path": "p"},
]


def write_folder(folder: str) -> str:
    files = {"alerts": ALERTS, "hits": HITS, "customers": CUSTOMERS, "accounts": ACCOUNTS,
             "onboarding": ONBOARDING, "kyc_checks": KYC, "notes": NOTES,
             "search_results": SEARCH, "practice_labels": LABELS}
    os.makedirs(folder, exist_ok=True)
    for name, rows in files.items():
        with open(os.path.join(folder, name + ".jsonl"), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    with open(os.path.join(folder, "name_variants.json"), "w", encoding="utf-8") as fh:
        json.dump([["muhammad", "mohammed"]], fh)  # bare-list form
    with open(os.path.join(folder, "POLICY.md"), "w", encoding="utf-8") as fh:
        fh.write("# Policy\n")
    return folder
