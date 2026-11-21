"""Template learner tests (HANDOFF P3). No network: llm.chat_json is replaced by a fake."""
import os
import unittest
from unittest import mock

import _paths  # noqa: F401
from screening import llm, notes_parse, templates
from screening.models import PartialDate

A = "Onfido verified KWAME MENSAH on 2024-01-09, DOB 1976-05-23, using a Ghanaian passport."
B = "Onfido verified LUCIA FERRARI on 2022-11-02, DOB 1965-02-28, using an Italian passport."
MIXED = "Onfido verified Lucia Ferrari on 2022-11-02, DOB 1965-02-28, using an Italian passport."
NOCUE = "Onfido checked Lucia Ferrari on 2022-11-02, DOB 1965-02-28, using an Italian passport."


def note(nid, text, created="2024-01-09"):
    return {"note_id": nid, "text": text, "created_at": created, "channel": "kyc"}


class MaskTests(unittest.TestCase):
    def test_paraphrase_with_other_values_has_same_shape(self):
        self.assertEqual(templates.mask(A)[0], templates.mask(B)[0])

    def test_mixed_case_name_has_same_shape_as_upper_case(self):
        shape, slots = templates.mask(MIXED)
        self.assertEqual(shape, templates.mask(B)[0])
        self.assertIn(("NAME", "Lucia Ferrari"), [(k, r) for k, r, _s, _e in slots])

    def test_slots_are_grouped_dates_names_countries(self):
        _shape, slots = templates.mask(A)
        self.assertEqual([k for k, *_ in slots], ["DATE", "DATE", "NAME", "COUNTRY"])
        self.assertEqual(slots[0][1], "2024-01-09")

    def test_dates_keep_their_cue_word(self):
        shape, _ = templates.mask(A)
        self.assertTrue(shape.startswith("on<DATE> dob<DATE> ;"), shape)

    def test_status_wording_is_part_of_the_shape(self):
        ok = templates.mask(A)[0]
        bad = templates.mask(A.replace("verified", "rejected"))[0]
        self.assertNotEqual(ok, bad)

    def test_year_inside_an_unread_date_is_not_a_year_slot(self):
        _shape, slots = templates.mask("Sumsub verified JANA NOVAK on 2024-01-09, born 03.05.1974.")
        self.assertNotIn("YEAR", [k for k, *_ in slots])
        _shape, slots = templates.mask("Sumsub verified JANA NOVAK on 2024-01-09, born 1974.")
        self.assertIn(("YEAR", "1974"), [(k, r) for k, r, _s, _e in slots])


class BootstrapTests(unittest.TestCase):
    def test_consistent_shape_becomes_a_template(self):
        out = templates.bootstrap([note("N1", A), note("N2", B, "2022-11-02")])
        tpl = out["templates"][templates.mask(A)[0]]
        self.assertEqual(tpl["roles"], ["check_date", "dob", "name", "doc_country"])
        self.assertEqual((tpl["example"], tpl["count"], tpl["result"]), ("N1", 2, "approved"))

    def test_shape_read_two_ways_is_skipped(self):
        one = "Persona verified JAVIER WEBER, who was born on April 4, 1956, on 2023-07-23 (Italy)."
        two = "Persona verified JAVIER WEBER on 2023-07-23, who was born on April 4, 1956 (Italy)."
        self.assertEqual(templates.mask(one)[0], templates.mask(two)[0])
        out = templates.bootstrap([note("N1", one, "2023-07-23"), note("N2", two, "2023-07-23")])
        self.assertEqual(out["templates"], {})
        self.assertEqual(out["skipped_shapes"], 1)

    def test_committed_templates_are_valid(self):
        known = templates._load_known()
        self.assertGreater(len(known), 50)
        for shape, tpl in known.items():
            kinds = shape.split(" | ")[0]
            self.assertIn("name", tpl["roles"], shape)
            self.assertIn("dob", tpl["roles"], shape)
            self.assertEqual(len(tpl["roles"]), len(set(r for r in tpl["roles"] if r != "other"))
                             + tpl["roles"].count("other"), kinds)


class ImproveTests(unittest.TestCase):
    def setUp(self):
        templates.configure([])
        roles = ["check_date", "dob", "name", "doc_country"]
        self.known = mock.patch.dict(templates._state, {"known": {
            templates.mask(A)[0]: {"roles": roles, "result": "approved", "source": "regex"},
            templates.mask(NOCUE)[0]: {"roles": roles, "result": None, "source": "regex"}}})
        self.known.start()

    def tearDown(self):
        self.known.stop()
        templates.configure([])

    def test_fully_read_note_is_untouched(self):
        p = notes_parse.parse_kyc_note(A, "2024-01-09")
        self.assertIs(templates.improve(p, A, "2024-01-09", "N1"), p)
        self.assertEqual(templates.stats()["triggered"], 0)

    def test_fills_a_mixed_case_name_the_regex_missed(self):
        p = notes_parse.parse_kyc_note(NOCUE, "2022-11-02")
        self.assertIsNone(p and p.get("name"))
        got = templates.improve(p, NOCUE, "2022-11-02", "N9")
        self.assertEqual(got["name"], "Lucia Ferrari")
        self.assertEqual(got["dob"], PartialDate(1965, 2, 28))
        self.assertEqual(got["doc_country"], "Italy")

    def test_disagreement_with_the_regex_gives_unknown(self):
        p = dict(notes_parse.parse_kyc_note(A, "2024-01-09"), name="SOMEONE ELSE", doc_country=None)
        got = templates.improve(p, A, "2024-01-09", "N1")
        self.assertIsNone(got["name"])
        self.assertEqual(got["doc_country"], "Ghana")

    def test_implausible_birth_date_is_dropped(self):
        text = NOCUE.replace("1965", "2015")
        got = templates.improve(None, text, "2022-11-02", "N9")
        self.assertEqual(got["name"], "Lucia Ferrari")
        self.assertIsNone(got["dob"])                     # 7 years old at the check

    def test_unknown_shape_without_llm_changes_nothing(self):
        text = "Lucia Ferrari / 1965-02-28 / Italian passport / Onfido / 2022-11-02"
        p = notes_parse.parse_kyc_note(text, "2022-11-02")
        self.assertEqual(templates.improve(p, text, "2022-11-02", "N9"), p)
        self.assertEqual(templates.stats()["no_template"], 1)


class LearnTests(unittest.TestCase):
    TEXT = "Lucia Ferrari / 1965-02-28 / Italian passport / Onfido / 2022-11-02"
    TEXT2 = "Pedro Alves / 1988-12-01 / Brazilian passport / Onfido / 2025-01-12"

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"XAI_API_KEY": "xai-test"})
        self.env.start()
        llm.configure(True)
        templates.configure([note("N2", self.TEXT2, "2025-01-12"), note("N1", self.TEXT, "2022-11-02")])
        self.known = mock.patch.dict(templates._state, {"known": {}})
        self.known.start()

    def tearDown(self):
        self.known.stop()
        llm.configure(False)
        templates.configure([])
        self.env.stop()

    def test_one_call_per_shape_on_the_lowest_note_id(self):
        answer = {"roles": ["dob", "check_date", "name", "doc_country"], "result": "approved"}
        with mock.patch.object(llm, "chat_json", return_value=answer) as fake:
            a = templates.improve(None, self.TEXT2, "2025-01-12", "N2")
            b = templates.improve(None, self.TEXT, "2022-11-02", "N1")
        self.assertEqual(fake.call_count, 1)
        self.assertIn("Lucia Ferrari", fake.call_args[0][1])       # N1 is the representative
        self.assertEqual((a["name"], a["dob"], a["doc_country"], a["result"]),
                         ("Pedro Alves", PartialDate(1988, 12, 1), "Brazil", "approved"))
        self.assertEqual(b["checked_at"], PartialDate(2022, 11, 2))
        self.assertEqual(templates.stats()["learned"], 1)

    def test_invalid_roles_are_refused_and_not_retried(self):
        answer = {"roles": ["name", "dob", "dob", "other"], "result": "approved"}
        with mock.patch.object(llm, "chat_json", return_value=answer) as fake:
            self.assertIsNone(templates.improve(None, self.TEXT2, "2025-01-12", "N2"))
            templates.improve(None, self.TEXT, "2022-11-02", "N1")
        self.assertEqual(fake.call_count, 1)
        self.assertEqual(templates.stats()["learn_failed"], 1)

    def test_llm_failure_gives_unknown(self):
        with mock.patch.object(llm, "chat_json", return_value=None):
            self.assertIsNone(templates.improve(None, self.TEXT2, "2025-01-12", "N2"))


if __name__ == "__main__":
    unittest.main()


class BenchTests(unittest.TestCase):
    """P4/P5: the bench file is complete, and the learner never makes a reading worse."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "bench.py")
        spec = importlib.util.spec_from_file_location("bench", path)
        cls.bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.bench)
        cls.cases = cls.bench.load_cases([cls.bench.DEFAULT_BENCH])

    def test_bench_has_100_labelled_cases(self):
        self.assertGreaterEqual(len(self.cases), 100)
        keys = {"name", "dob", "doc_country", "result", "countries"}
        for c in self.cases:
            self.assertEqual(set(c["expected"]), keys, c["case_id"])
        tags = {t for c in self.cases for t in c.get("tags", [])}
        for needed in ("mixed-case-name", "no-birth-cue", "city-not-country", "rejected", "expired",
                       "pending", "two-dates", "non-english-date"):
            self.assertIn(needed, tags)

    def test_learner_reads_more_and_never_turns_unknown_into_wrong(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XAI_API_KEY", None)
            a = self.bench.run_mode(self.cases, "a")
            b = self.bench.run_mode(self.cases, "b")
            self.bench.set_mode("a")
        right_a, _ = self.bench.table(self.cases, a)
        right_b, _ = self.bench.table(self.cases, b)
        self.assertGreaterEqual(right_b["right"], right_a["right"])
        self.assertEqual(self.bench.unknown_to_wrong(self.cases, a, b), [])
