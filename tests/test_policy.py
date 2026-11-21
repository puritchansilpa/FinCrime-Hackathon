"""Policy rules from POLICY.md principles 6-7, including cases the dev labels never show
(DECEASED, ENTITY_TYPE_MISMATCH, company TEMPORAL, AMBIGUOUS_CUSTOMER_RECORD)."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "system"))

from screening.models import (  # noqa: E402
    AMBIGUOUS, AMBIGUOUS_CUSTOMER_RECORD, COMPANY, DECEASED, DIFFERENT, DOB_MISMATCH,
    ENTITY_TYPE_MISMATCH, INDIVIDUAL, INSUFFICIENT_DATA, LOCATION_MISMATCH, NAME_DOB_LOCATION_MATCH,
    NAME_DOB_MATCH, NAME_LOCATION_MATCH, NAME_MISMATCH_VERIFIED, REVIEW, SAME, TEMPORAL_IMPOSSIBILITY,
    Fact, HitProfile, PartialDate as D, Person,
)
from screening.names import Variants  # noqa: E402
from screening.policy import decide, decide_alert_hit, dob_agrees, dob_contradicts  # noqa: E402

V = Variants(groups=[["muhammad", "mohammed", "mohamed"]])
ALERT = {"alert_id": "A-1", "screened_at": "2026-11-06", "customer_name": "Maria Lopez"}


def person(rid="CUS-1", kind=INDIVIDUAL, vname="Maria Lopez", vdob=D(1980, 5, 1),
           countries=("Spain",), declared=(), src="KYC-1"):
    return Person(
        record_ids=[rid], entity_type=kind,
        verified_name=Fact(vname, src, "verified_kyc") if vname else None,
        verified_dob=Fact(vdob, src, "verified_kyc") if vdob else None,
        declared_names=[Fact(n, rid, "record") for n in declared],
        countries=[Fact(c, rid, "record") for c in countries],
    )


def hit(names=("Maria Lopez",), kind=INDIVIDUAL, dobs=(), countries=("Spain",), report=None, death=None):
    cands = []
    for d in dobs:
        if isinstance(d, frozenset):
            cands.append(Fact(d, "H-1", "profile_age"))
        else:
            cands.append(Fact(d, "H-1", "dobs"))
    return HitProfile(
        hit_id="H-1", alert_id="A-1", entity_type=kind,
        names=[Fact(n, "H-1", "name" if i == 0 else "alias") for i, n in enumerate(names)],
        dob_candidates=cands, dob_origin="dobs" if cands else None,
        earliest_report=Fact(report, "H-1", "report") if report else None,
        death_date=Fact(death, "H-1", "deceased_date") if death else None,
        countries=[Fact(c, "H-1", "hit_country") for c in countries],
    )


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


class TestDateRules(unittest.TestCase):
    def test_agree(self):
        self.assertTrue(dob_agrees(D(1968, 3, 5), frozenset({1967, 1968})))
        self.assertTrue(dob_agrees(D(1968, 2, 17), D(1968, 2)))
        self.assertTrue(dob_agrees(D(1968), D(1968, 2, 17)))          # year alone agrees with a full date
        self.assertFalse(dob_agrees(D(1968, 3, 5), D(1968, 4)))

    def test_contradict(self):
        self.assertTrue(dob_contradicts(D(1979, 11, 8), frozenset({1976, 1977})))
        self.assertFalse(dob_contradicts(D(1978, 1, 1), frozenset({1976, 1977})))  # within 1 year
        self.assertTrue(dob_contradicts(D(1965, 3, 28), D(1962, 9, 10)))
        self.assertFalse(dob_contradicts(D(1963, 3, 28), D(1962, 9, 10)))         # 1 year, months not compared
        self.assertTrue(dob_contradicts(D(1962, 3, 28), D(1962, 9, 10)))          # same year, months differ
        self.assertTrue(dob_contradicts(D(1962, 9, 28), D(1962, 9, 10)))          # same month, days differ
        self.assertFalse(dob_contradicts(D(1962), D(1962, 9, 10)))


class TestClear(unittest.TestCase):
    def test_entity_type_mismatch(self):
        d = decide(person(kind=COMPANY, vname="Lopez Holdings SL"), hit(names=("Lopez Holdings",)), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (DIFFERENT, ENTITY_TYPE_MISMATCH))

    def test_deceased_before_screening(self):
        d = decide(person(), hit(death=D(2022, 3)), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (DIFFERENT, DECEASED))

    def test_death_after_screening_does_not_clear(self):
        d = decide(person(), hit(death=D(2026, 11, 20)), ALERT, V)
        self.assertNotEqual(d.reason_code, DECEASED)

    def test_death_in_screening_month_without_day_does_not_clear(self):
        d = decide(person(), hit(death=D(2026, 11)), ALERT, V)
        self.assertNotEqual(d.reason_code, DECEASED)

    def test_temporal_person_too_young(self):
        d = decide(person(vdob=D(2007)), hit(report=D(2020, 1, 8)), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (DIFFERENT, TEMPORAL_IMPOSSIBILITY))
        self.assertIn("at most 13", d.reason)

    def test_temporal_person_16_is_old_enough(self):
        d = decide(person(vdob=D(2004, 1, 1)), hit(report=D(2020, 1, 8)), ALERT, V)
        self.assertNotEqual(d.reason_code, TEMPORAL_IMPOSSIBILITY)

    def test_temporal_company_incorporated_after_report(self):
        p = person(kind=COMPANY, vname="Lopez Holdings SL", vdob=D(2021, 6, 1))
        d = decide(p, hit(names=("Lopez Holdings",), kind=COMPANY, report=D(2019, 5, 1)), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (DIFFERENT, TEMPORAL_IMPOSSIBILITY))

    def test_temporal_company_same_year_unknown_month_does_not_clear(self):
        p = person(kind=COMPANY, vname="Lopez Holdings SL", vdob=D(2019))
        d = decide(p, hit(names=("Lopez Holdings",), kind=COMPANY, report=D(2019, 5, 1)), ALERT, V)
        self.assertNotEqual(d.reason_code, TEMPORAL_IMPOSSIBILITY)

    def test_placeholder_hit_name_cannot_clear(self):
        """N/A, TEST, UNKNOWN and blanks are missing names, not a mismatch (ADV-H-110)."""
        for name in ("N/A", "NA", "TEST", "UNKNOWN", "XXX", "   ", ""):
            d = decide(person(), hit(names=(name,), dobs=(D(1980, 5, 1),)), ALERT, V)
            self.assertEqual(d.decision, REVIEW, name)
            self.assertNotEqual(d.reason_code, NAME_MISMATCH_VERIFIED, name)
        # a real alias still can; a placeholder alias beside it does not block that
        d = decide(person(), hit(names=("N/A", "Someone Else"), dobs=(D(1980, 5, 1),)), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (DIFFERENT, NAME_MISMATCH_VERIFIED))

    def test_dob_mismatch_cites_dob_source(self):
        d = decide(person(vdob=D(1995, 12, 17)), hit(dobs=[frozenset({1986, 1987})]), ALERT, V)
        self.assertEqual((d.decision, d.reason_code, d.evidence), (DIFFERENT, DOB_MISMATCH, ["KYC-1"]))

    def test_one_agreeing_date_prevents_dob_mismatch(self):
        d = decide(person(vdob=D(1965, 3, 28)), hit(dobs=[D(1962, 9, 10), D(1965)]), ALERT, V)
        self.assertNotEqual(d.reason_code, DOB_MISMATCH)
        self.assertEqual(d.decision, SAME)

    def test_location_mismatch(self):
        d = decide(person(vdob=None, countries=("Australia",)), hit(countries=("United States",)), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (DIFFERENT, LOCATION_MISMATCH))

    def test_location_does_not_clear_when_name_and_dob_agree(self):
        d = decide(person(countries=("Australia",)), hit(dobs=[D(1980)], countries=("United States",)), ALERT, V)
        self.assertEqual(d.decision, REVIEW)

    def test_verified_name_mismatch_even_if_record_name_agrees(self):
        p = person(vname="Sarah Johnson", vdob=None, declared=("James Johnson",))
        d = decide(p, hit(names=("Johnson, James Jacob",)), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (DIFFERENT, NAME_MISMATCH_VERIFIED))

    def test_declared_name_mismatch_alone_does_not_clear(self):
        p = person(vname=None, vdob=None, declared=("Sarah Johnson",))
        d = decide(p, hit(names=("Johnson, James Jacob",)), {**ALERT, "customer_name": "Sarah Johnson"}, V)
        self.assertEqual(d.decision, REVIEW)

    def test_unknown_stays_unknown(self):
        d = decide(person(vdob=None, countries=()), hit(), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (REVIEW, INSUFFICIENT_DATA))


class TestConfirm(unittest.TestCase):
    def test_person_name_dob_location(self):
        d = decide(person(), hit(dobs=[frozenset({1979, 1980})]), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (SAME, NAME_DOB_LOCATION_MATCH))

    def test_person_name_dob_without_countries(self):
        d = decide(person(countries=()), hit(dobs=[D(1980, 5)], countries=()), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (SAME, NAME_DOB_MATCH))

    def test_company_name_location(self):
        p = person(kind=COMPANY, vname="Pescanova SA", vdob=None)
        d = decide(p, hit(names=("Pescanova, Sociedad Anónima",), kind=COMPANY), ALERT, V)
        self.assertEqual((d.decision, d.reason_code), (SAME, NAME_LOCATION_MATCH))

    def test_single_part_name_is_neither_confirmed_nor_cleared(self):
        d = decide(person(vname="Madonna"), hit(names=("Madonna Ciccone",), dobs=[D(1980)]), ALERT, V)
        self.assertEqual(d.decision, REVIEW)
        d = decide(person(vname="Madonna"), hit(names=("Peter Brown",)), ALERT, V)
        self.assertEqual(d.decision, REVIEW)

    def test_name_variants(self):
        p = person(vname="Mohammed Nadeem Ghani", vdob=D(1968, 2, 17))
        d = decide(p, hit(names=("Muhammad Nadeem Ghani",), dobs=[D(1968, 2)]), ALERT, V)
        self.assertEqual(d.decision, SAME)


class TestSeveralPeople(unittest.TestCase):
    def test_different_decisions_are_ambiguous(self):
        a = person(rid="CUS-1", vdob=D(1980, 5, 1))
        b = person(rid="CUS-2", vdob=D(1950, 1, 1), src="KYC-2")
        d = decide_alert_hit([a, b], hit(dobs=[D(1980)]), ALERT, V)
        self.assertEqual((d.decision, d.reason_code, d.customer_record_id),
                         (REVIEW, AMBIGUOUS_CUSTOMER_RECORD, AMBIGUOUS))

    def test_same_decision_is_given_with_ambiguous_id(self):
        a = person(rid="CUS-1", vdob=D(1995, 1, 1))
        b = person(rid="CUS-2", vdob=D(1999, 1, 1), src="KYC-2")
        d = decide_alert_hit([a, b], hit(dobs=[D(1960)]), ALERT, V)
        self.assertEqual((d.decision, d.customer_record_id), (DIFFERENT, AMBIGUOUS))
        self.assertEqual(d.evidence, ["KYC-1", "KYC-2"])

    def test_no_customer_found_is_review(self):
        # screened details alone never clear: even a clear country difference goes to review
        d = decide_alert_hit([], hit(countries=("Japan",)), {**ALERT, "customer": {"country": "Spain"}}, V)
        self.assertEqual((d.decision, d.reason_code, d.customer_record_id), (REVIEW, INSUFFICIENT_DATA, None))


class TestReasons(unittest.TestCase):
    def test_two_to_four_sentences(self):
        cases = [
            decide(person(), hit(death=D(2022, 3)), ALERT, V),
            decide(person(vdob=D(1995, 12, 17)), hit(dobs=[frozenset({1986, 1987})]), ALERT, V),
            decide(person(), hit(dobs=[frozenset({1979, 1980})]), ALERT, V),
            decide(person(vdob=None, countries=()), hit(), ALERT, V),
            decide_alert_hit([person(rid="CUS-1"), person(rid="CUS-2", vdob=D(1950, 1, 1))],
                             hit(dobs=[D(1980)]), ALERT, V),
        ]
        for d in cases:
            n = len(sentences(d.reason))
            self.assertTrue(2 <= n <= 4, f"{d.reason_code}: {n} sentences: {d.reason}")


if __name__ == "__main__":
    unittest.main()
