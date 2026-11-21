import os
import tempfile
import unittest

import _paths  # noqa: F401
from fixtures import write_folder
from screening.load import as_list, document_key, load_data, name_tokens, phone_key


class HelperTests(unittest.TestCase):
    def test_as_list_accepts_strings_arrays_and_none(self):
        self.assertEqual(as_list("1996; 1997"), ["1996", "1997"])
        self.assertEqual(as_list(["1996", " ", None, "1997"]), ["1996", "1997"])
        self.assertEqual(as_list(None), [])
        self.assertEqual(as_list(""), [])
        self.assertEqual(as_list("single"), ["single"])

    def test_name_tokens_fold_case_and_accents(self):
        self.assertEqual(name_tokens("José  MÜLLER-Ortiz (Jr.)"), ["jose", "muller", "ortiz", "jr"])
        self.assertEqual(name_tokens(None), [])

    def test_phone_key_ignores_spacing_and_matches_the_same_number(self):
        self.assertEqual(phone_key("+351 912 000 111"), phone_key("+351912000111"))
        self.assertEqual(phone_key("+49 151 234 5678"), phone_key("+491512345678"))
        self.assertEqual(phone_key("+44-7700-900-321"), phone_key("+447700900321"))
        self.assertEqual(phone_key("+1 (202) 555-0198"), phone_key("+12025550198"))
        # international prefix, trunk 0, and an extension are the same subscriber
        self.assertEqual(phone_key("+44 7700 900621"), phone_key("07700 900621"))
        self.assertEqual(phone_key("+49 15123456789"), phone_key("004915123456789"))
        self.assertEqual(phone_key("+33 6 12 34 56 78"), phone_key("0033 6 12 34 56 78"))
        self.assertEqual(phone_key("+1 202 555 0164"), phone_key("+1 202 555 0164 x99"))
        self.assertEqual(phone_key("+1 202 555 0165"), phone_key("+1 202 555 0165 ext. 205"))
        # a different digit is a different number
        self.assertNotEqual(phone_key("+1 202 555 0168"), phone_key("+1 202 555 0169"))

    def test_document_key_ignores_case_space_dash_and_leading_zeros(self):
        self.assertEqual(document_key("WQ-770069"), document_key("WQ770069"))
        self.assertEqual(document_key("wq770070"), document_key("WQ770070"))
        self.assertEqual(document_key("WQ  770071"), document_key("WQ770071"))
        self.assertEqual(document_key("WQ-77 0072"), document_key("WQ770072"))
        self.assertEqual(document_key("000770073"), document_key("770073"))
        self.assertEqual(document_key("d1 "), document_key("D1"))
        self.assertNotEqual(document_key("WQ770074"), document_key("WQ770084"))
        self.assertEqual(document_key(None), "")
        self.assertEqual(document_key(""), "")


class LoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = load_data(write_folder(os.path.join(cls.tmp.name, "d")))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_alerts_sorted_and_hit_ids_are_lists(self):
        d = self.data
        self.assertEqual([a["alert_id"] for a in d.alerts], ["A-1", "A-2"])
        a2 = d.alerts[1]
        self.assertEqual(sorted(a2["hit_ids"]), ["H-1", "H-3"])
        self.assertEqual([h["hit_id"] for h in d.hits_for_alert(a2)], ["H-1", "H-3"])

    def test_embedded_hits_are_extracted(self):
        d = self.data
        self.assertIn("H-2", d.hits)
        self.assertEqual(d.hits["H-2"]["alert_id"], "A-1")
        self.assertEqual(d.alerts[0]["hit_ids"], ["H-2"])
        self.assertEqual(d.hits["H-2"]["dobs"], ["1970", "1971"])

    def test_hit_list_fields_split(self):
        self.assertEqual(self.data.hits["H-1"]["dobs"], ["1980", "1981-01"])
        self.assertEqual(self.data.hits["H-1"]["aliases"], [])

    def test_joint_account_keeps_every_holder(self):
        holders = [a["customer_id"] for a in self.data.accounts_by_id["acc-j"]]
        self.assertEqual(holders, ["CUS-1", "CUS-2"])

    def test_indexes(self):
        d = self.data
        self.assertEqual([c["record_id"] for c in d.customers_by_email["ana.silva@x.example"]], ["CUS-2"])
        self.assertEqual([c["record_id"] for c in d.customers_by_phone[phone_key("+351 912 000 111")]],
                         ["CUS-1", "CUS-2"])
        self.assertEqual([c["record_id"] for c in d.customers_by_name_token["silva"]], ["CUS-1", "CUS-2"])
        self.assertEqual([k["check_id"] for k in d.kyc_by_applicant["APP-1"]], ["KYC-1", "KYC-2"])
        self.assertEqual([n["note_id"] for n in d.notes_by_email["ana.silva@x.example"]], ["NOTE-1"])
        self.assertEqual([r["result_id"] for r in d.search_by_query["ana silva"]], ["SR-1"])
        self.assertEqual(d.accounts_by_login["anas2"][0]["customer_id"], "CUS-1")
        self.assertEqual(d.name_variants["name_variants"], [["muhammad", "mohammed"]])
        self.assertTrue(d.policy_text.startswith("# Policy"))

    def test_missing_files_load_empty(self):
        with tempfile.TemporaryDirectory() as empty:
            d = load_data(empty)
        self.assertEqual(d.alerts, [])
        self.assertEqual(d.hits, {})


class OfficialFormatTests(unittest.TestCase):
    """The data room's own shapes: nested screened customer, arrays, "groups" variants."""

    def test_nested_customer_arrays_and_groups(self):
        import json
        from screening import fallbacks
        from screening.customer import resolve
        with tempfile.TemporaryDirectory() as tmp:
            rows = {
                "alerts": [{"alert_id": "A-000001", "screened_at": "2026-11-01",
                            "customer": {"name": "Mohamed Nadeem", "entity_type": "Individual",
                                         "dob": "1990", "country": "Pakistan", "city": None},
                            "account_ref": None, "login_handle": None, "email": None,
                            "hit_ids": ["H-000001"]}],
                "hits": [{"hit_id": "H-000001", "alert_id": "A-000001", "name": "Nadeem, Muhammad",
                          "aliases": [], "dobs": ["1990"], "details": {"pep": "x"}, "countries": []}],
                "customers": [{"record_id": "CUS-000001", "entity_type": "Individual",
                               "full_name": "Mohammad Nadeem", "dob": "April 5, 1990",
                               "nationality": "Pakistani", "residence_country": "PK",
                               "email": "m@x.example", "phone": "+92 1"}],
                "practice_labels": [{"hit_id": "H-000001", "decision": "REVIEW",
                                     "reason_codes": ["INSUFFICIENT_DATA"],
                                     "customer_record_ids": ["CUS-000001"], "evidence": [],
                                     "path": ["a", "b"]}],
            }
            for name, rs in rows.items():
                with open(os.path.join(tmp, name + ".jsonl"), "w", encoding="utf-8") as fh:
                    fh.writelines(json.dumps(r) + "\n" for r in rs)
            with open(os.path.join(tmp, "name_variants.json"), "w", encoding="utf-8") as fh:
                json.dump({"description": "x", "groups": [["muhammad", "mohamed", "mohammad"]],
                           "company_legal_forms": ["gmbh"]}, fh)
            import contextlib
            import io
            with contextlib.redirect_stderr(io.StringIO()):
                d = load_data(tmp)
        alert = d.alerts[0]
        self.assertEqual((alert["customer_name"], alert["entity_type"], alert["dob"], alert["country"]),
                         ("Mohamed Nadeem", "Individual", "1990", "Pakistan"))
        self.assertEqual(d.name_variants["name_variants"], [["muhammad", "mohamed", "mohammad"]])
        self.assertTrue(fallbacks.names_agree("Mohamed Nadeem", "Mohammad Nadeem"))
        self.assertEqual(d.hits["H-000001"]["dobs"], ["1990"])
        self.assertEqual(d.hits["H-000001"]["details"], {"pep": "x"})   # dicts are left alone
        self.assertEqual(d.practice_labels[0]["reason_codes"], ["INSUFFICIENT_DATA"])
        # the search finds the customer only because the variant groups were read
        res = resolve(alert, d)
        self.assertEqual([p.record_ids for p in res.persons], [["CUS-000001"]])


if __name__ == "__main__":
    unittest.main()
