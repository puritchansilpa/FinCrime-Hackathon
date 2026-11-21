"""Review tasks annotate REVIEWs. They do not change decisions."""
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO

import _paths  # noqa: F401
from fixtures import write_folder
from screening.__main__ import run
from screening.models import Fact, HitProfile, PartialDate, Person
from screening.names import Variants
from screening.policy import decide
from screening.review_queue import build_task, expected_cost_saved, rank_queue

V = Variants()
ALERT = {"alert_id": "A-1", "screened_at": "2026-06-01", "customer_name": "Ana Silva"}


class _Res:
    def __init__(self, persons):
        self.persons = persons


def _hit_row(profile):
    dobs = []
    for cand in profile.dob_candidates:
        if isinstance(cand.value, PartialDate):
            dobs.append(cand.value.iso())
    return {
        "hit_id": profile.hit_id,
        "alert_id": profile.alert_id,
        "entity_type": profile.entity_type,
        "name": profile.names[0].value if profile.names else "",
        "dobs": dobs,
        "countries": [fact.value for fact in profile.countries],
    }


def _run_task(person, profile, alert=None):
    alert = ALERT if alert is None else alert
    official = decide(person, profile, alert, V)
    data = type("D", (), {"variants": V, "search_by_query": {}})()
    row = build_task(official, _Res([person] if person is not None else []), _hit_row(profile), alert, data)
    return official, row


class ReviewTests(unittest.TestCase):
    def test_unknown_dob_comes_from_decide(self):
        person = Person(record_ids=["CUS-1"], entity_type="Individual",
                        verified_name=Fact("Ana Silva", "KYC-1", "verified_kyc"))
        profile = HitProfile(hit_id="H-1", alert_id="A-1", entity_type="Individual",
                             names=[Fact("Ana Silva", "H-1", "name")],
                             dob_candidates=[Fact(PartialDate(1970), "H-1", "dobs")], dob_origin="dobs")
        official, row = _run_task(person, profile)
        self.assertEqual(official.decision, "REVIEW")
        self.assertEqual(decide(person, profile, ALERT, V).to_output(), official.to_output())
        self.assertEqual(row["task"]["side"], "customer")
        self.assertIn("date of birth", row["task"]["fact"])
        self.assertIn("after 1971", row["task"]["summary"])
        self.assertIn("DOB_MISMATCH", row["task"]["summary"])
        self.assertIn("no approved KYC check exists", row["task"]["where"])
        mismatch = decide(Person(record_ids=["CUS-1"], entity_type="Individual",
                                 verified_name=Fact("Ana Silva", "KYC-1", "verified_kyc"),
                                 verified_dob=Fact(PartialDate(1900), "KYC-1", "verified_kyc")),
                          profile, ALERT, V)
        match = decide(Person(record_ids=["CUS-1"], entity_type="Individual",
                              verified_name=Fact("Ana Silva", "KYC-1", "verified_kyc"),
                              verified_dob=Fact(PartialDate(1970), "KYC-1", "verified_kyc")),
                       profile, ALERT, V)
        codes = {(item["decision"], item["reason_code"]) for item in row["task"]["outcomes"]}
        self.assertIn((mismatch.decision, mismatch.reason_code), codes)
        self.assertIn((match.decision, match.reason_code), codes)

    def test_unknown_country_on_a_company(self):
        person = Person(record_ids=["CUS-1"], entity_type="Company",
                        verified_name=Fact("Pescanova SA", "KYC-1", "verified_kyc"))
        profile = HitProfile(hit_id="H-1", alert_id="A-1", entity_type="Company",
                             names=[Fact("Pescanova", "H-1", "name")],
                             countries=[Fact("Spain", "H-1", "hit_country")])
        official, row = _run_task(person, profile)
        self.assertEqual(official.decision, "REVIEW")
        self.assertEqual(row["task"]["side"], "customer")
        self.assertIn("country", row["task"]["fact"])
        # The name agrees and the country is still unknown, so the name alone is not a lean.
        self.assertEqual(row["band"], "neutral")
        self.assertIn("name match alone", row["band_reason"])
        confirmed = decide(Person(record_ids=["CUS-1"], entity_type="Company",
                                  verified_name=Fact("Pescanova SA", "KYC-1", "verified_kyc"),
                                  countries=[Fact("Spain", "KYC-1", "document_country")]),
                           profile, ALERT, V)
        self.assertEqual(confirmed.reason_code, "NAME_LOCATION_MATCH")
        codes = {(item["decision"], item["reason_code"]) for item in row["task"]["outcomes"]}
        self.assertIn((confirmed.decision, confirmed.reason_code), codes)
        self.assertEqual(decide(person, profile, ALERT, V).decision, "REVIEW")

    def test_location_clash_cannot_become_a_clearance(self):
        person = Person(record_ids=["CUS-1"], entity_type="Individual",
                        verified_name=Fact("Ana Silva", "KYC-1", "verified_kyc"),
                        verified_dob=Fact(PartialDate(1980, 1, 2), "KYC-1", "verified_kyc"),
                        countries=[Fact("Spain", "CUS-1", "residence_country")])
        profile = HitProfile(hit_id="H-1", alert_id="A-1", entity_type="Individual",
                             names=[Fact("Ana Silva", "H-1", "name")],
                             dob_candidates=[Fact(PartialDate(1980), "H-1", "dobs")], dob_origin="dobs",
                             countries=[Fact("Pakistan", "H-1", "hit_country")])
        official, row = _run_task(person, profile)
        self.assertEqual(official.decision, "REVIEW")
        self.assertTrue(all(item["decision"] != "DIFFERENT_ENTITY" for item in row["task"]["outcomes"]))
        self.assertEqual(row["band"], "leaning SAME")

    def test_plain_name_match_is_not_agreement(self):
        person = Person(record_ids=["CUS-1"], entity_type="Individual",
                        declared_names=[Fact("Ana Silva", "CUS-1", "record")])
        profile = HitProfile(hit_id="H-1", alert_id="A-1", entity_type="Individual",
                             names=[Fact("Ana Silva", "H-1", "name")])
        official, row = _run_task(person, profile)
        self.assertEqual(official.decision, "REVIEW")
        self.assertEqual(row["band"], "neutral")
        self.assertNotIn("name", row["agrees"])
        self.assertIn("plain name match", row["band_reason"])

    def test_verified_name_alone_is_not_a_lean(self):
        person = Person(record_ids=["CUS-1"], entity_type="Individual",
                        verified_name=Fact("Ana Silva", "KYC-1", "verified_kyc"))
        profile = HitProfile(hit_id="H-1", alert_id="A-1", entity_type="Individual",
                             names=[Fact("Ana Silva", "H-1", "name")])
        official, row = _run_task(person, profile)
        self.assertEqual(official.decision, "REVIEW")
        self.assertEqual(row["band"], "neutral")
        self.assertNotIn("verified name", row["agrees"])
        self.assertIn("name match alone", row["band_reason"])

    def test_ambiguous_customer(self):
        profile = HitProfile(hit_id="H-1", alert_id="A-1", entity_type="Individual",
                             names=[Fact("Ana Silva", "H-1", "name")],
                             dob_candidates=[Fact(PartialDate(1980), "H-1", "dobs")], dob_origin="dobs",
                             countries=[Fact("Spain", "H-1", "hit_country")])
        first = Person(record_ids=["CUS-A"], entity_type="Individual",
                       verified_name=Fact("Ana Silva", "KYC-1", "verified_kyc"),
                       verified_dob=Fact(PartialDate(1980, 1, 2), "KYC-1", "verified_kyc"),
                       countries=[Fact("Spain", "CUS-A", "residence_country")])
        second = Person(record_ids=["CUS-B"], entity_type="Individual",
                        verified_name=Fact("Ana Silva", "KYC-2", "verified_kyc"),
                        verified_dob=Fact(PartialDate(1950, 1, 1), "KYC-2", "verified_kyc"),
                        countries=[Fact("Spain", "CUS-B", "residence_country")])
        from screening.policy import combine
        official = combine([decide(first, profile, ALERT, V), decide(second, profile, ALERT, V)], profile, [first, second])
        self.assertEqual(official.reason_code, "AMBIGUOUS_CUSTOMER_RECORD")
        data = type("D", (), {"variants": V, "search_by_query": {}})()
        row = build_task(official, _Res([first, second]), _hit_row(profile), ALERT, data)
        self.assertEqual(row["band"], "neutral")
        self.assertEqual(row["task"]["fact"], "which customer record")
        self.assertIn("CUS-A", row["task"]["summary"])
        self.assertIn("CUS-B", row["task"]["summary"])
        self.assertEqual(row["expected_cost_saved"], 2.5)

    def test_a_clearance_is_not_annotated(self):
        person = Person(record_ids=["CUS-1"], entity_type="Individual",
                        verified_name=Fact("Ana Silva", "KYC-1", "verified_kyc"),
                        verified_dob=Fact(PartialDate(1950), "KYC-1", "verified_kyc"))
        profile = HitProfile(hit_id="H-1", alert_id="A-1", entity_type="Individual",
                             names=[Fact("Ana Silva", "H-1", "name")],
                             dob_candidates=[Fact(PartialDate(1980), "H-1", "dobs")], dob_origin="dobs")
        official = decide(person, profile, ALERT, V)
        self.assertEqual(official.decision, "DIFFERENT_ENTITY")
        before = official.to_output()
        data = type("D", (), {"variants": V, "search_by_query": {}})()
        self.assertIsNone(build_task(official, _Res([person]), _hit_row(profile), ALERT, data))
        self.assertEqual(decide(person, profile, ALERT, V).to_output(), before)

    def test_rank_uses_the_cost_matrix(self):
        self.assertEqual(round(expected_cost_saved([
            {"decision": "DIFFERENT_ENTITY"}, {"decision": "SAME_ENTITY"}, {"decision": "REVIEW"},
        ]), 4), round(5 / 3, 4))
        ranked = rank_queue([
            {"hit_id": "H-B", "expected_cost_saved": 1},
            {"hit_id": "H-C", "expected_cost_saved": 3},
            {"hit_id": "H-A", "expected_cost_saved": 1},
        ])
        self.assertEqual([row["hit_id"] for row in ranked], ["H-C", "H-A", "H-B"])
        self.assertEqual([row["rank"] for row in ranked], [1, 2, 3])

    def test_official_output_is_unchanged_and_queue_repeats(self):
        folder = write_folder(os.path.join(tempfile.mkdtemp(), "d"))
        out_dir = tempfile.mkdtemp()
        first, second = os.path.join(out_dir, "a.jsonl"), os.path.join(out_dir, "b.jsonl")
        with redirect_stderr(StringIO()):
            run(folder, first)
        queue_path = os.path.join(out_dir, "review_queue.jsonl")
        with open(first, "rb") as handle:
            official_bytes = handle.read()
        with open(queue_path, "rb") as handle:
            queue_bytes = handle.read()
        with redirect_stderr(StringIO()):
            run(folder, second)
        with open(second, "rb") as handle:
            self.assertEqual(handle.read(), official_bytes)
        with open(queue_path, "rb") as handle:
            self.assertEqual(handle.read(), queue_bytes)
        official = [json.loads(line) for line in official_bytes.decode().splitlines() if line.strip()]
        queue = [json.loads(line) for line in queue_bytes.decode().splitlines() if line.strip()]
        for row in official:
            self.assertEqual(list(row), [
                "hit_id", "alert_id", "decision", "reason_code", "customer_record_id", "reason", "evidence"])
        review_ids = {row["hit_id"] for row in official if row["decision"] == "REVIEW"}
        self.assertEqual({row["hit_id"] for row in queue}, review_ids)
        for row in queue:
            self.assertEqual(row["official_decision"], "REVIEW")


if __name__ == "__main__":
    unittest.main()
