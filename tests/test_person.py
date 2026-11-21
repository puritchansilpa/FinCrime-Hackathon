import contextlib
import io
import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from screening.customer import resolve
from screening.load import load_data
from screening.models import PartialDate

CUSTOMERS = [
    {"record_id": "CUS-1", "entity_type": "Individual", "full_name": "Tunde Bello", "preferred_name": "Tee",
     "dob": "1980-05-05", "nationality": "Nigerian", "residence_country": "GB",
     "email": "t1@x.example", "phone": "+234 1"},
    {"record_id": "CUS-2", "entity_type": "Individual", "full_name": "Babatunde Bello", "dob": "05/05/1980",
     "nationality": "Nigeria", "residence_country": "Nigeria", "email": "t2@x.example", "phone": "+234 1"},
    {"record_id": "CUS-3", "entity_type": "Individual", "full_name": "Ada Obi", "dob": "1990-01-01",
     "nationality": "Nigeria", "residence_country": "NG", "email": "ada@x.example", "phone": "+234 3"},
]
ACCOUNTS = [{"account_id": f"ACC-{i}", "customer_id": f"CUS-{i}", "login_handle": f"u{i}", "phone": None}
            for i in (1, 2, 3)]
ONBOARDING = [{"account_id": f"ACC-{i}", "customer_id": f"CUS-{i}", "kyc_applicant_id": f"APP-{i}"}
              for i in (1, 2, 3)]
KYC = [
    # CUS-1: an older approved check, and a NEWER rejected one that must be ignored
    {"check_id": "KYC-OLD", "applicant_id": "APP-1", "verified_name": "TUNDE BELLO",
     "verified_dob": "1980-05-05", "document_country": "United Kingdom", "result": "approved",
     "checked_at": "2022-01-01"},
    {"check_id": "KYC-REJ", "applicant_id": "APP-1", "verified_name": "SOMEONE ELSE",
     "verified_dob": "1999-09-09", "document_country": "France", "result": "rejected",
     "checked_at": "2025-01-01"},
    # CUS-3: only an expired check -> no verified facts
    {"check_id": "KYC-EXP", "applicant_id": "APP-3", "verified_name": "ADA OBI", "verified_dob": "1990-01-01",
     "document_country": "Nigeria", "result": "expired", "checked_at": "2024-01-01"},
]
NOTES = [
    # CUS-2 (same person as CUS-1): a NEWER approved check recorded only in a kyc note
    {"note_id": "NOTE-NEW", "requester_email": "t2@x.example", "created_at": "2024-06-01", "channel": "kyc",
     "text": "On 2024-06-01, Persona verified BABATUNDE OLUWASEUN BELLO (DOB 5 May 1980) using a Nigerian passport."},
    # residence history
    {"note_id": "NOTE-RES", "requester_email": "t1@x.example", "created_at": "2024-02-02", "channel": "phone",
     "text": "Customer lived and worked in Ghana from 2010 to 2014."},
    {"note_id": "NOTE-NOISE", "requester_email": "t1@x.example", "created_at": "2024-02-03", "channel": "app",
     "text": "Customer asked how long an international transfer takes."},
    # a failed check in a note is not evidence
    {"note_id": "NOTE-FAIL", "requester_email": "ada@x.example", "created_at": "2024-03-03", "channel": "kyc",
     "text": "Onfido could not verify ADA OBI (DOB 1990-01-01); the Nigeria passport was rejected on 2024-03-03."},
]


class PersonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        for name, rows in (("customers", CUSTOMERS), ("accounts", ACCOUNTS), ("onboarding", ONBOARDING),
                           ("kyc_checks", KYC), ("notes", NOTES)):
            with open(os.path.join(cls.tmp.name, name + ".jsonl"), "w", encoding="utf-8") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in rows)
        with contextlib.redirect_stderr(io.StringIO()):
            cls.data = load_data(cls.tmp.name)
        alert = {"alert_id": "A1", "customer_name": "Tunde Bello", "entity_type": "Individual",
                 "account_ref": "ACC-1", "hit_ids": []}
        cls.person = resolve(alert, cls.data).persons[0]

    def test_records_merge(self):
        self.assertEqual(self.person.record_ids, ["CUS-1", "CUS-2"])

    def test_newest_approved_check_wins_even_from_a_note(self):
        p = self.person
        self.assertEqual((p.verified_name.value, p.verified_name.source_id, p.verified_name.origin),
                         ("BABATUNDE OLUWASEUN BELLO", "NOTE-NEW", "verified_note"))
        self.assertEqual(p.verified_dob.value, PartialDate(1980, 5, 5))
        self.assertEqual(p.verified_dob.source_id, "NOTE-NEW")

    def test_countries_from_records_document_and_residence_notes(self):
        got = {(f.value, f.source_id, f.origin) for f in self.person.countries}
        self.assertEqual(got, {
            ("Nigeria", "CUS-1", "nationality"), ("United Kingdom", "CUS-1", "residence_country"),
            ("Nigeria", "CUS-2", "nationality"), ("Nigeria", "CUS-2", "residence_country"),
            ("Nigeria", "NOTE-NEW", "document_country"),
            ("Ghana", "NOTE-RES", "residence_note"),
        })
        self.assertNotIn("France", {f.value for f in self.person.countries})  # rejected check

    def test_declared_facts_keep_their_records(self):
        names = {(f.value, f.source_id) for f in self.person.declared_names}
        self.assertIn(("Tee", "CUS-1"), names)
        self.assertIn(("Babatunde Bello", "CUS-2"), names)

    def test_expired_and_failed_checks_give_no_verified_facts(self):
        alert = {"alert_id": "A2", "customer_name": "Ada Obi", "entity_type": "Individual",
                 "account_ref": "ACC-3", "hit_ids": []}
        p = resolve(alert, self.data).persons[0]
        self.assertIsNone(p.verified_name)
        self.assertIsNone(p.verified_dob)
        self.assertEqual({f.origin for f in p.countries}, {"nationality", "residence_country"})


if __name__ == "__main__":
    unittest.main()
