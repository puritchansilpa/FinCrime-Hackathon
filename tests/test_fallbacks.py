import unittest

import _paths  # noqa: F401
from screening import fallbacks as F
from screening.models import PartialDate

VARIANTS = {
    "name_variants": [["muhammad", "mohammed", "mohammad", "mohamed"], ["joseph", "josef"],
                      ["joseph", "giuseppe"], ["michael", "mike"]],
    "company_legal_forms": ["ltd", "gmbh", "ag", "se", "inc"],
}


class DateTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(F.parse_date("1968-03-05"), PartialDate(1968, 3, 5))
        self.assertEqual(F.parse_date("19/12/1940"), PartialDate(1940, 12, 19))
        self.assertEqual(F.parse_date("17 June 1976"), PartialDate(1976, 6, 17))
        self.assertEqual(F.parse_date("June 17, 1976"), PartialDate(1976, 6, 17))
        self.assertEqual(F.parse_date("17th of June 1976"), PartialDate(1976, 6, 17))
        self.assertIsNone(F.parse_date("June of 1976 or so"))
        self.assertEqual(F.parse_date("February 1968"), PartialDate(1968, 2))
        self.assertEqual(F.parse_date("1976-06"), PartialDate(1976, 6))
        self.assertEqual(F.parse_date("1976"), PartialDate(1976))
        self.assertIsNone(F.parse_date("13/13/1976"))
        self.assertIsNone(F.parse_date("1976; 1977"))
        self.assertTrue(F.full_date(F.parse_date("1 May 1990")))
        self.assertFalse(F.full_date(F.parse_date("May 1990")))


class CountryTests(unittest.TestCase):
    def test_names_codes_demonyms(self):
        for raw, want in [("GB", "United Kingdom"), ("British", "United Kingdom"), ("Dutch", "Netherlands"),
                          ("US", "United States"), ("American", "United States"),
                          ("Cote D'Ivoire", "Cote d'Ivoire"), ("Côte d'Ivoire", "Cote d'Ivoire"),
                          ("Palestina", "Palestine"), ("Faisalabad, Punjab, Pakistan", "Pakistan"),
                          ("Canada [PEP]", "Canada"), ("Macao Special Administrative Region of China", "Macao"),
                          ("Puerto Rico", "Puerto Rico"), ("Jersey", "Jersey")]:
            self.assertEqual(F.to_country(raw), want, raw)

    def test_not_countries(self):
        for raw in ("International", "Europe [Associated]", "", None, "Atlantis"):
            self.assertIsNone(F.to_country(raw), raw)


class NameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        F.configure(VARIANTS)

    def test_parts(self):
        self.assertEqual(F.name_parts("Md. Saidul ISLAM (Jr)"), ["md", "saidul", "islam"])
        self.assertEqual(F.name_parts("XXX MARTON XXX"), ["marton"])
        self.assertEqual(F.name_parts("J. R. Smith 2nd 1990"), ["smith", "2nd"])
        self.assertEqual(F.name_parts("Mike O'Connor"), ["mike", "oconnor"])
        self.assertEqual(F.name_parts("Lafarge . GmbH", is_company=True), ["lafarge"])
        self.assertEqual(F.name_parts("N/A TEST unknown"), [])

    def test_agree(self):
        agree = [
            ("Muhammad Nadeem GHANI", "Mohammad Nadeem GHANI"),   # variants
            ("MD. SAEDUL ISLAM", "Md. Saidul Islam"),               # 1 edit in a 6-letter part
            ("Marcus Gerhard MUELLER", "Markus Gerhard MUELLER"),
            ("Abdulsalam Bello", "Abdul Salam Bello"),              # written together or apart
            ("Bello, Abdul Salam", "Abdulsalam"),                   # joined part covers both
            ("Mike Oconnor", "Michael O'Connor"),                   # variant + punctuation
            ("ELVIRA MORILLO", "Elvira Velasco Morillo"),           # shorter name fully matched
            ("Giuseppe Verdi", "Josef Verdi"),                      # 'joseph' bridges? no: see below
        ]
        for a, b in agree[:-1]:
            self.assertTrue(F.names_agree(a, b), (a, b))
        disagree = [
            ("Elvira Velasco MORILLO", "Luca MORILLO"),             # family: only the surname
            ("Ana Lee", "Ana Lim"),                                 # 3-letter parts must be identical
            ("Christopher Smith", "Kristofer Smyth"),               # too many edits each
            ("", "Ana"),
        ]
        for a, b in disagree:
            self.assertFalse(F.names_agree(a, b), (a, b))
        # giuseppe and josef are each grouped with joseph, but not with each other
        self.assertFalse(F.names_agree("Giuseppe", "Josef"))
        self.assertTrue(F.names_agree("Giuseppe", "Joseph"))

    def test_swap_is_two_edits(self):
        self.assertFalse(F.names_agree("Maria", "Mraia"))       # 5 letters: 1 edit allowed
        self.assertTrue(F.names_agree("Christopher", "Christohper"))  # 11 letters: 2 allowed

    def test_company_legal_forms_ignored(self):
        self.assertTrue(F.names_agree("N26 Bank AG", "N26 Bank SE", is_company=True))
        self.assertFalse(F.names_agree("Acme GmbH", "Zenith GmbH", is_company=True))


if __name__ == "__main__":
    unittest.main()
