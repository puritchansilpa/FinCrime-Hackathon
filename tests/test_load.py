import os
import tempfile
import unittest

import _paths  # noqa: F401
from fixtures import write_folder
from screening.load import as_list, load_data, name_tokens, phone_key


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

    def test_phone_key_is_digits_only(self):
        self.assertEqual(phone_key("+351 912 000 111"), phone_key("+351912000111"))


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
        self.assertEqual([c["record_id"] for c in d.customers_by_phone["351912000111"]], ["CUS-1", "CUS-2"])
        self.assertEqual([c["record_id"] for c in d.customers_by_name_token["silva"]], ["CUS-1", "CUS-2"])
        self.assertEqual([k["check_id"] for k in d.kyc_by_applicant["APP-1"]], ["KYC-1", "KYC-2"])
        self.assertEqual([n["note_id"] for n in d.notes_by_email["ana.silva@x.example"]], ["NOTE-1"])
        self.assertEqual([r["result_id"] for r in d.search_by_query["ana silva"]], ["SR-1"])
        self.assertEqual(d.accounts_by_login["anas2"][0]["customer_id"], "CUS-1")
        self.assertEqual(d.name_variants, {"name_variants": [["muhammad", "mohammed"]]})
        self.assertTrue(d.policy_text.startswith("# Policy"))

    def test_missing_files_load_empty(self):
        with tempfile.TemporaryDirectory() as empty:
            d = load_data(empty)
        self.assertEqual(d.alerts, [])
        self.assertEqual(d.hits, {})


if __name__ == "__main__":
    unittest.main()
