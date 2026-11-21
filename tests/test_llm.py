"""LLM client tests. No network: llm._post is replaced by a fake."""
import json
import os
import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest import mock

import _paths  # noqa: F401
from screening import llm
from screening.models import PartialDate


def reply(obj):
    return {"choices": [{"message": {"content": json.dumps(obj)}}]}


class LlmTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False)
        self.env.start()
        os.environ.pop("LLM_CACHE_FILE", None)
        llm._state["cache"].clear()
        llm.configure(True)
        self.sent = []

    def tearDown(self):
        llm.configure(False)
        llm._state["cache"].clear()
        self.env.stop()

    def fake(self, answer):
        def post(payload, timeout):
            self.sent.append(payload)
            return reply(answer)
        return mock.patch.object(llm, "_post", side_effect=post)

    def test_off_without_flag_or_key(self):
        llm.configure(False)
        self.assertFalse(llm.enabled())
        llm.configure(True)
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            self.assertFalse(llm.enabled())
            self.assertIsNone(llm.chat_json("s", "u", {}))

    def test_request_is_pinned_and_deterministic(self):
        with self.fake({"countries": []}):
            llm.extract_residence_countries("lived in Peru 2010")
        p = self.sent[0]
        self.assertEqual(p["temperature"], 0)
        self.assertEqual(p["seed"], llm.SEED)
        self.assertEqual(p["model"], llm.DEFAULT_MODEL)
        self.assertEqual(p["provider"], {"order": [llm.DEFAULT_PROVIDER], "allow_fallbacks": False})
        self.assertEqual(p["response_format"]["type"], "json_schema")

    def test_kyc_values_must_appear_in_the_note(self):
        text = "Checked 2024-01-05: ZARA KHAN, D.O.B. 3rd of May 1990, Pakistani ID, status ok."
        answer = {"name": "ZARA KHAN", "date_of_birth": "3rd of May 1990",
                  "document_country": "Pakistani", "check_date": "2024-01-05", "result": "approved"}
        with self.fake(answer):
            got = llm.extract_kyc_note(text, "2024-01-05")
        self.assertEqual(got["name"], "ZARA KHAN")
        self.assertEqual(got["dob"], PartialDate(1990, 5, 3))
        self.assertEqual(got["doc_country"], "Pakistan")
        self.assertEqual(got["result"], "approved")

    def test_hallucinated_values_are_dropped(self):
        text = "Checked 2024-01-05: ZARA KHAN, DOB 1990-05-03, status ok."
        answer = {"name": "ZARA AHMED KHAN", "date_of_birth": "1991-05-03", "document_country": "India",
                  "check_date": None, "result": "maybe"}
        with self.fake(answer):
            self.assertIsNone(llm.extract_kyc_note(text, "2024-01-05"))  # no name, no dob survive

    def test_residence_countries_validated(self):
        with self.fake({"countries": ["Peru", "Chile"]}):
            got = llm.extract_residence_countries("Spent 2010-2014 working in Peru.")
        self.assertEqual(got, ["Peru"])

    def test_answers_are_cached(self):
        with self.fake({"countries": ["Peru"]}):
            llm.extract_residence_countries("Peru 2010")
            llm.extract_residence_countries("Peru 2010")
        self.assertEqual(len(self.sent), 1)

    def test_failures_mean_unknown(self):
        def boom(payload, timeout):
            raise OSError("network down")
        with mock.patch.object(llm, "_post", side_effect=boom), mock.patch.object(llm.time, "sleep"), \
                redirect_stderr(StringIO()):
            self.assertIsNone(llm.extract_kyc_note("ZARA KHAN DOB 1990", None))
            self.assertEqual(llm.extract_residence_countries("Peru 2010"), [])

    def test_non_json_reply_is_unknown(self):
        def junk(payload, timeout):
            return {"choices": [{"message": {"content": "I cannot help with that."}}]}
        with mock.patch.object(llm, "_post", side_effect=junk), mock.patch.object(llm.time, "sleep"):
            self.assertIsNone(llm.chat_json("s", "u", {"type": "object"}))


if __name__ == "__main__":
    unittest.main()
