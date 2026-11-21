"""The review app builder (tools/build_review_ui.py) on a tiny hand-made folder."""
import contextlib
import io
import json
import os
import re
import tempfile
import unittest

import _paths  # noqa: F401
import build_review_ui
import fixtures
from screening import __main__ as runner


class TestReviewUiBuild(unittest.TestCase):
    def test_build_embeds_every_hit_and_its_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = fixtures.write_folder(os.path.join(tmp, "data"))
            out = os.path.join(tmp, "out", "dev.jsonl")
            page = os.path.join(tmp, "ui.html")
            with contextlib.redirect_stderr(io.StringIO()):
                runner.run(data, out)
                build_review_ui.main(["--data", data, "--output", out, "--out", page])
            html = open(page, encoding="utf-8").read()
            blob = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1)
            self.assertNotIn("</", blob)                       # cannot break out of the script tag
            payload = json.loads(blob)
            lines = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
            in_alerts = {h["hit_id"] for h in lines if h["alert_id"] != "A-MISSING"}
            self.assertEqual({h["id"] for h in payload["hits"]}, in_alerts)
            for h in payload["hits"]:
                for rid in h["evidence"]:
                    self.assertIn(rid, payload["records"], rid)
                self.assertEqual(h["queue"] is not None, h["decision"] == "REVIEW")


if __name__ == "__main__":
    unittest.main()
