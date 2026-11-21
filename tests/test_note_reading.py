"""Note-reading fixes found on the P5 bench (tests/bench/notes.jsonl): each case below was
read wrongly by the regex, the template learner or the LLM before the fix."""
import os
import unittest
from unittest import mock

import _paths  # noqa: F401
from screening import llm, notes_parse
from screening.normalize import is_country_code


def read(text):
    r = notes_parse.parse_kyc_note(text)
    return {k: (v.iso() if hasattr(v, "iso") else v) for k, v in r.items()
            if k in ("name", "dob", "doc_country", "result")}


class TestCountryCodes(unittest.TestCase):
    def test_codes(self):
        for t in ("NG", "GB", "USA", "U.S.", "U.K."):
            self.assertTrue(is_country_code(t), t)
        for t in ("NA", "N/A", "OK", "Ng", "Lagos", "MARIA"):
            self.assertFalse(is_country_code(t), t)

    def test_code_is_not_a_name_but_gives_the_document_country(self):       # kyc-074, kyc-082
        r = read("Jumio OK - Kofi Asante - passport NG - DOB 1987-05-17 - 2025-02-08.")
        self.assertIsNone(r["name"])                    # unknown -> the learner / LLM may read it
        self.assertEqual(r["doc_country"], "Nigeria")
        r = read("Onfido verified Emily Johnson on February 9, 2023 (U.S. passport, DOB June 17, 1992).")
        self.assertEqual((r["name"], r["doc_country"]), ("Emily Johnson", "United States"))
        self.assertEqual(read("Onfido: passport (GB) for EMMA WILSON, DOB 1995-09-12, approved 2023-10-19.")
                         ["doc_country"], "United Kingdom")                    # kyc-073

    def test_a_name_that_contains_a_code_is_kept(self):
        self.assertEqual(read("Veriff verified KELVIN NG (DOB 1980-01-01) on 2024-01-01, passport from Singapore.")
                         ["name"], "KELVIN NG")


class TestDocumentCountryFromCity(unittest.TestCase):                       # kyc-023 to kyc-030
    def test_city_only(self):
        self.assertEqual(read("Onfido verified CHIOMA EZE on 2024-03-28 using a passport issued in Lagos; "
                              "DOB 1989-04-02.")["doc_country"], "Nigeria")
        self.assertEqual(read("Veriff verified the Dubai-issued residence permit of RASHID AL MANSOORI on "
                              "2024-12-03; date of birth 1978-06-19.")["doc_country"], "United Arab Emirates")


class TestOtherReading(unittest.TestCase):
    def test_dotted_date(self):                                              # kyc-062
        self.assertEqual(read("Veriff confirmed PIETER DE VRIES, DOB 1979.08.30, on 2025-03-21 using a "
                              "Dutch passport.")["dob"], "1979-08-30")

    def test_legal_form_kept(self):                                          # kyc-069
        self.assertEqual(read("Companies registry lookup on 2024-02-25 confirmed NORTHWIND TRADING LTD, "
                              "incorporated 2011-06-14 in the United Kingdom.")["name"], "NORTHWIND TRADING LTD")

    def test_holiday_is_not_residence(self):                                 # res-018
        self.assertEqual(notes_parse.parse_residence_note(
            "Card declined at a hotel in Spain; customer was on holiday there in 2025."), [])
        self.assertFalse(notes_parse.residence_without_place("Customer was on holiday in 2025."))
        self.assertEqual(notes_parse.parse_residence_note(
            "The customer lived in Spain from 2010 to 2015 and visited Peru in 2016."), ["Peru", "Spain"])

    def test_extend_name_keeps_particles(self):                              # kyc-014
        text = "Maria Clara dos Santos was successfully verified by Sumsub on October 25, 2024."
        self.assertEqual(notes_parse.extend_name("Maria Clara", text), "Maria Clara dos Santos")
        self.assertEqual(notes_parse.extend_name("Arjun Nair", "Jumio approved Arjun Nair on 2023-10-01."),
                         "Arjun Nair")


class TestLlmCannotDecideTheResult(unittest.TestCase):                      # kyc-044
    def test_result_comes_from_the_wording(self):
        text = "Onfido verification for TUNDE BAKARE (DOB 1984-01-15) is pending; Nigerian passport uploaded 2025-05-05."
        answer = {"name": "TUNDE BAKARE", "date_of_birth": "1984-01-15", "document_country": "Nigerian",
                  "check_date": None, "result": "expired"}
        with mock.patch.dict(os.environ, {"XAI_API_KEY": "xai-test"}), \
                mock.patch.object(llm, "chat_json", return_value=answer):
            llm.configure(True)
            try:
                got = llm.extract_kyc_note(text, "2025-05-05")
            finally:
                llm.configure(False)
        self.assertIsNone(got["result"])                 # pending, whatever the model says

    def test_llm_name_is_extended(self):
        text = "Maria Clara dos Santos was successfully verified by Sumsub on October 25, 2024; DOB 11 May 1983."
        answer = {"name": "Maria Clara", "date_of_birth": "11 May 1983", "document_country": None,
                  "check_date": None, "result": "approved"}
        with mock.patch.dict(os.environ, {"XAI_API_KEY": "xai-test"}), \
                mock.patch.object(llm, "chat_json", return_value=answer):
            llm.configure(True)
            try:
                got = llm.extract_kyc_note(text, "2024-10-25")
            finally:
                llm.configure(False)
        self.assertEqual(got["name"], "Maria Clara dos Santos")


if __name__ == "__main__":
    unittest.main()
