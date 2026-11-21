import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO

import _paths  # noqa: F401
from fixtures import write_folder
from screening.__main__ import run


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = write_folder(os.path.join(self.tmp.name, "d"))

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, name):
        out = os.path.join(self.tmp.name, "out", name)
        with redirect_stderr(StringIO()):
            run(self.folder, out)
        with open(out, encoding="utf-8") as fh:
            return fh.read()

    def test_one_line_per_hit_sorted_with_all_fields(self):
        lines = [json.loads(l) for l in self._run("a.jsonl").splitlines()]
        self.assertEqual([l["hit_id"] for l in lines], ["H-1", "H-2", "H-3", "H-9"])
        for l in lines:
            self.assertEqual(list(l), ["hit_id", "alert_id", "decision", "reason_code",
                                       "customer_record_id", "reason", "evidence"])
        orphan = lines[-1]
        self.assertEqual((orphan["decision"], orphan["alert_id"]), ("REVIEW", "A-MISSING"))

    def test_runs_are_byte_identical(self):
        self.assertEqual(self._run("a.jsonl"), self._run("b.jsonl"))

    def test_a_crashing_hit_becomes_review_not_clearance(self):
        from screening import hit as hit_mod
        original = hit_mod.build_hit

        def boom(row, data):
            if row["hit_id"] == "H-1":
                raise ValueError("bad record")
            return original(row, data)

        hit_mod.build_hit = boom
        try:
            lines = {json.loads(l)["hit_id"]: json.loads(l) for l in self._run("c.jsonl").splitlines()}
        finally:
            hit_mod.build_hit = original
        self.assertEqual(lines["H-1"]["decision"], "REVIEW")
        self.assertEqual(len(lines), 4)


if __name__ == "__main__":
    unittest.main()
