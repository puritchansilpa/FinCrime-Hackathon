import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system"))

from screening.names import Variants, edit_distance, names_agree, parts_match  # noqa: E402

GROUPS = [
    ["muhammad", "mohammed", "mohammad", "mohamed", "muhammed", "mohamad", "mohd", "muhamad"],
    ["yusuf", "yousef", "youssef", "yousuf", "josef", "joseph", "joe"],
    ["joseph", "joe", "jose", "giuseppe", "jozef"],
    ["anthony", "antony", "tony", "antonio"],
    ["ali", "aly"],
]
V = Variants(groups=GROUPS)


class TestPartsMatch(unittest.TestCase):
    def test_identical(self):
        self.assertTrue(parts_match("milan", "milan", V))

    def test_variants(self):
        self.assertTrue(parts_match("muhammad", "mohamed", V))
        self.assertTrue(parts_match("tony", "anthony", V))
        self.assertTrue(parts_match("ali", "aly", V))            # short, but listed together

    def test_overlapping_groups_are_not_transitive(self):
        self.assertTrue(parts_match("joseph", "yusuf", V))
        self.assertTrue(parts_match("joseph", "jose", V))
        self.assertFalse(parts_match("yusuf", "jose", V))

    def test_edit_limits_by_length(self):
        self.assertTrue(parts_match("smith", "smyth", V))         # 5 letters, 1 edit
        self.assertFalse(parts_match("smith", "smyht", V))        # 2 edits
        self.assertTrue(parts_match("johansson", "johanson", V))  # 8 letters, 1 edit
        self.assertTrue(parts_match("stefanovic", "stefanovich", V))
        self.assertTrue(parts_match("abubakar", "abubeker", V))   # 2 edits on 8 letters
        self.assertFalse(parts_match("abubakar", "abuboker1", V))

    def test_shorter_part_decides(self):
        self.assertFalse(parts_match("anna", "annabel", V))       # shorter = 4 -> 1 edit; distance 3
        self.assertTrue(parts_match("abdul", "abdull", V))

    def test_short_parts_must_be_identical(self):
        self.assertFalse(parts_match("kim", "kin", V))
        self.assertFalse(parts_match("lee", "li", V))

    def test_swap_is_two_edits(self):
        self.assertEqual(edit_distance("mira", "miar"), 2)
        self.assertFalse(parts_match("mira", "miar", V))          # 4 letters allow only 1
        self.assertTrue(parts_match("christina", "chrsitina", V))  # 9 letters allow 2


class TestNamesAgree(unittest.TestCase):
    def test_two_parts_match(self):
        self.assertTrue(names_agree("Maria Garcia Lopez", "Maria Lopez Fernandez", V))

    def test_reordered(self):
        self.assertTrue(names_agree("Wei Li", "Li Wei", V))
        self.assertTrue(names_agree("Samuel Bernard", "Bernard, Samuel", V))

    def test_every_part_of_shorter_name(self):
        self.assertTrue(names_agree("Rajesh Kumar", "Rajesh Kumar Singh", V))
        self.assertTrue(names_agree("Grillz", "Grillz Reyes", V))  # single-part alias

    def test_one_part_only_is_not_enough(self):
        self.assertFalse(names_agree("John Smith", "John Doe", V))

    def test_written_together_or_apart(self):
        self.assertTrue(names_agree("Abdulsalam", "Abdul Salam", V))
        self.assertTrue(names_agree("Abdulsalam Bello", "Abdul Salam Bello", V))
        self.assertTrue(names_agree("Abdul Salam Bello", "Bello Abdulsalam", V))

    def test_variant_plus_edit(self):
        self.assertTrue(names_agree("Muhammad Nadeem Ghani", "Mohammad Nadeem Ghani", V))
        self.assertTrue(names_agree("Tony Okafor", "Anthony Okafor", V))

    def test_initials_and_placeholders_ignored(self):
        self.assertTrue(names_agree("Carl E. Andersen", "Carl Andersen", V))
        self.assertFalse(names_agree("NA TEST", "Carl Andersen", V))

    def test_companies_ignore_legal_forms(self):
        self.assertTrue(names_agree("Danske Bank A/S", "Danske Bank", V, is_company=True))
        self.assertTrue(names_agree("Sterling Bank LTD", "Sterling Bank & Trust Co.", V, is_company=True))
        self.assertFalse(names_agree("Acme GmbH", "Zenith GmbH", V, is_company=True))


class TestVariantsLoading(unittest.TestCase):
    def test_data_room_file(self):
        p = ROOT / "screening" / "dev" / "name_variants.json"
        if not p.exists():
            self.skipTest("data room not present")
        v = Variants.load(p)                       # {"description", "groups", "company_legal_forms"}
        self.assertEqual(len(v.groups), 55)
        self.assertTrue(v.same_group("mohammed", "muhammad"))
        self.assertIn("gmbh", v.legal_forms)

    def test_other_layouts(self):
        v = Variants.from_obj({"muhammad": ["mohammed"], "legal_forms": ["ltd"]})
        self.assertTrue(v.same_group("muhammad", "mohammed"))
        self.assertEqual(v.legal_forms, ("ltd",))
        v = Variants.from_obj([["ali", "aly"]])
        self.assertTrue(v.same_group("ali", "aly"))


if __name__ == "__main__":
    unittest.main()
