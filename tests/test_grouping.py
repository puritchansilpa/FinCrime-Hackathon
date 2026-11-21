import contextlib
import io
import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from screening.customer import approved_checks, resolve
from screening.load import load_data


def cust(rid, name, dob, phone):
    return {"record_id": rid, "entity_type": "Individual", "full_name": name, "dob": dob,
            "nationality": "Nigeria", "residence_country": "NG", "email": f"{rid.lower()}@x.example",
            "phone": phone}


CUSTOMERS = [
    cust("CUS-80", "Sam Ade", "1980-05-05", "+234 1"),
    cust("CUS-81", "Sam Ade", "05/05/1980", "+234 1"),        # same phone + same full DOB -> same
    cust("CUS-82", "Tola Ade", "1982-01-01", "+234 1"),       # same phone, other DOB -> family
    cust("CUS-83", "Sam Ade", "1980", "+234 1"),              # same phone, DOB not full -> not linked
    cust("CUS-84", "Sam Adeyemi", "1990-01-01", "+234 9"),    # same document as CUS-81 -> same
    cust("CUS-85", "Sam Ade", "1970-01-01", "+234 7"),        # same document, but REJECTED -> not linked
    cust("CUS-86", "Sam Ade", "1980-07-07", "+234 5"),        # a different person with the same name
]
ACCOUNTS = [{"account_id": f"ACC-{n}", "customer_id": f"CUS-{n}", "login_handle": f"u{n}",
             "phone": c["phone"]} for n, c in zip(range(80, 87), CUSTOMERS)]
ONBOARDING = [{"account_id": f"ACC-{n}", "customer_id": f"CUS-{n}", "kyc_applicant_id": f"APP-{n}"}
              for n in range(80, 87)]
KYC = [
    {"check_id": "KYC-81", "applicant_id": "APP-81", "document_number": "D1", "result": "approved",
     "checked_at": "2024-01-01"},
    {"check_id": "KYC-84", "applicant_id": "APP-84", "document_number": "d1 ", "result": "Approved",
     "checked_at": "2024-02-01"},
    {"check_id": "KYC-85", "applicant_id": "APP-85", "document_number": "D1", "result": "rejected",
     "checked_at": "2024-03-01"},
    {"check_id": "KYC-80a", "applicant_id": "APP-80", "document_number": "X", "result": "expired",
     "checked_at": "2025-01-01"},
]


def alert(aid, name, dob=None, **links):
    row = {"alert_id": aid, "customer_name": name, "entity_type": "Individual", "dob": dob,
           "country": None, "city": None, "hit_ids": []}
    row.update(links)
    return row


class GroupingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        for name, rows in (("customers", CUSTOMERS), ("accounts", ACCOUNTS),
                           ("onboarding", ONBOARDING), ("kyc_checks", KYC)):
            with open(os.path.join(cls.tmp.name, name + ".jsonl"), "w", encoding="utf-8") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in rows)
        with contextlib.redirect_stderr(io.StringIO()):
            cls.data = load_data(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def persons(self, res):
        return [p.record_ids for p in res.persons]

    def test_phone_dob_and_document_links_chain(self):
        res = resolve(alert("G1", "Sam Ade", account_ref="ACC-80"), self.data)
        self.assertEqual(self.persons(res), [["CUS-80", "CUS-81", "CUS-84"]])
        self.assertIn("one person: CUS-80, CUS-81, CUS-84", " ".join(res.path))

    def test_family_and_partial_dob_and_rejected_checks_do_not_link(self):
        for start in ("ACC-82", "ACC-83", "ACC-85"):
            res = resolve(alert("G2", "x", account_ref=start), self.data)
            self.assertEqual(len(self.persons(res)), 1)
            self.assertEqual(len(self.persons(res)[0]), 1, start)

    def test_search_finds_two_people(self):
        res = resolve(alert("G3", "Sam Ade", "1980"), self.data)
        # 80+81 are one person (84 joins by document); 86 is someone else; 83 lacks a full DOB
        # but fits the search on its own, so it is a third person.
        self.assertEqual(self.persons(res), [["CUS-80", "CUS-81", "CUS-84"], ["CUS-83"], ["CUS-86"]])
        self.assertIn("3 different people fit", res.path[-1])

    def test_person_has_facts_from_every_record(self):
        res = resolve(alert("G4", "Sam Ade", account_ref="ACC-80"), self.data)
        sources = {f.source_id for f in res.persons[0].declared_names}
        self.assertEqual(sources, {"CUS-80", "CUS-81", "CUS-84"})

    def test_approved_checks_only(self):
        self.assertEqual([c["check_id"] for c in approved_checks("CUS-80", self.data)], [])
        self.assertEqual([c["check_id"] for c in approved_checks("CUS-84", self.data)], ["KYC-84"])


if __name__ == "__main__":
    unittest.main()
