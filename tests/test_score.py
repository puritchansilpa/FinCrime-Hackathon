import unittest

import _paths  # noqa: F401
import score as S


def pred(hid, dec, code, cust=None, ev=(), reason="One. Two."):
    return {"hit_id": hid, "alert_id": "A", "decision": dec, "reason_code": code,
            "customer_record_id": cust, "reason": reason, "evidence": list(ev)}


LABELS = [
    {"hit_id": "H-1", "decision": "DIFFERENT_ENTITY", "reason_codes": "DOB_MISMATCH",
     "customer_record_ids": "CUS-1", "evidence": "KYC-1"},
    {"hit_id": "H-2", "decision": "SAME_ENTITY", "reason_codes": "NAME_DOB_MATCH; NAME_DOB_LOCATION_MATCH",
     "customer_record_ids": "CUS-2; CUS-3", "evidence": "CUS-2; KYC-2"},
    {"hit_id": "H-3", "decision": "REVIEW", "reason_codes": "INSUFFICIENT_DATA",
     "customer_record_ids": "AMBIGUOUS", "evidence": ""},
]


class ScoreTests(unittest.TestCase):
    def test_all_review_scores_zero(self):
        preds = {l["hit_id"]: pred(l["hit_id"], "REVIEW", "INSUFFICIENT_DATA") for l in LABELS}
        res = S.score(preds, LABELS)
        self.assertEqual(res["baseline"], 5)
        self.assertEqual(res["cost"], 5)
        self.assertEqual(res["decision_score"], 0.0)
        self.assertEqual(res["unsafe"], [])

    def test_clear_everything_scores_zero_and_flags_unsafe(self):
        preds = {l["hit_id"]: pred(l["hit_id"], "DIFFERENT_ENTITY", "DOB_MISMATCH") for l in LABELS}
        res = S.score(preds, LABELS)
        self.assertEqual(res["cost"], 120)
        self.assertEqual(res["decision_score"], 0.0)
        self.assertEqual(res["unsafe"], ["H-2", "H-3"])

    def test_perfect_run(self):
        preds = {
            "H-1": pred("H-1", "DIFFERENT_ENTITY", "DOB_MISMATCH", "CUS-1", ["KYC-1"]),
            "H-2": pred("H-2", "SAME_ENTITY", "NAME_DOB_MATCH", "CUS-3", ["KYC-2", "CUS-2"]),
            "H-3": pred("H-3", "REVIEW", "INSUFFICIENT_DATA", "AMBIGUOUS", []),
        }
        res = S.score(preds, LABELS)
        self.assertEqual(res["decision_score"], 1.0)
        self.assertEqual(res["reason_rates"],
                         {"code": 1.0, "customer": 1.0, "evidence_exact": 1.0, "reason_text": 1.0})
        self.assertAlmostEqual(res["combined"], 1.0)

    def test_reason_problems_are_reported(self):
        preds = {"H-1": pred("H-1", "DIFFERENT_ENTITY", "LOCATION_MISMATCH", "CUS-9",
                             ["KYC-1", "CUS-1"], reason="Too short")}
        res = S.score(preds, LABELS[:1])
        probs = " ".join(res["rows"][0]["problems"])
        for word in ("code", "customer", "evidence", "sentences"):
            self.assertIn(word, probs)

    def test_format_checks(self):
        rows = [(1, pred("H-1", "SAME_ENTITY", "DOB_MISMATCH")),
                (2, pred("H-1", "REVIEW", "INSUFFICIENT_DATA")),
                (3, {"hit_id": "H-4"})]
        _, problems = S.check_format(rows, hit_ids=["H-1", "H-2"])
        text = "\n".join(problems)
        self.assertIn("does not belong", text)
        self.assertIn("duplicate", text)
        self.assertIn("missing fields", text)
        self.assertIn("no prediction", text)
        self.assertIn("unknown hits", text)


if __name__ == "__main__":
    unittest.main()
