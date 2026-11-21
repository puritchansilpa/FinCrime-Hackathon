import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "system"))

from screening.models import COMPANY, PartialDate as D  # noqa: E402
from screening.hit import (  # noqa: E402
    age_at_date, birth_years, build_hit, dated_reports, hit_countries, listing_phrase,
)


class TestAgeAtDate(unittest.TestCase):
    def test_wordings_seen_in_dev(self):
        cases = {
            "In January 2025, investigators questioned 38-year-old Tomasz Paweł Drozd.": 38,
            "Michael Earl Tilley, aged 46, underwent questioning by investigators in January 2023.": 46,
            "Questioned in April 2006, Alexander Ostrowsky was 42 years old.": 42,
            "Back in September 2001, Thuận Thị Lê reached the age of 23 upon receiving a public appointment.": 23,
            "When investigators conducted questioning of Michael Earl Tilley in January 2023, he was 46.": 46,
            "Regarding the June 2006 investigation, Tomasz Drozd was 27 at the time he was questioned.": 27,
        }
        for text, age in cases.items():
            self.assertEqual(age_at_date(text)[0], age, text)

    def test_two_birth_years(self):
        self.assertEqual(birth_years(45, D(2019, 3)), frozenset({1973, 1974}))

    def test_numbers_that_are_not_ages(self):
        for text in ("including PKR 3,100,000 in cash in October 2025.",
                     "This company is a sanctions concern because it is 100.00% owned, as of 2016.",
                     "as defined in Section 101(9) & (28) of CERCLA in March 2026"):
            self.assertIsNone(age_at_date(text), text)

    def test_needs_a_date(self):
        self.assertIsNone(age_at_date("Michael Earl Tilley, aged 46, was questioned."))

    def test_snippet_any_wording(self):
        for text, age in {
            "In October 2006, a Colombia local newspaper featured an interview with 26, Maria Miller.": 26,
            "Halima Obi, a 72, a marathon runner in Denmark, appeared according to September 2020 records.": 72,
            "In January 1981, a hospital nurse named Matteo Rossi was quoted in an India local news story; he was 17.": 17,
            "In March 2004, Ana Lima, forty-five, was named in adverse media in Brazil.": 45,
        }.items():
            self.assertEqual(age_at_date(text, snippet=True)[0], age, text)


class TestDatedReports(unittest.TestCase):
    def test_exact_form_only(self):
        notes = "\n".join([
            "According to the thenews.com.pk; January 08, 2020: In January 2020, he was arrested.",
            "According to US Attorney - Southern District of Florida;  April 19, 2019: On April 18 …",
            "According to the FIA; June 2014: month-only does not count.",
            "According to US BOP; as of December 01, 2021: other wording does not count.",
            "The report said that According to X; May 05, 2001: mid-line does not count.",
        ])
        self.assertEqual(dated_reports(notes), [D(2020, 1, 8), D(2019, 4, 19)])


class TestBuildHit(unittest.TestCase):
    def test_countries_from_all_fields(self):
        row = {"countries": "Brazil", "nationality": "Jaén, Jaén, Spain", "citizenship": "Iraq; United States",
               "addresses": "10 Main St, Toronto, Canada [Business]; Europe [Associated]",
               "place_of_birth": "Kampala, Uganda"}
        self.assertEqual(sorted(hit_countries(row)),
                         ["Brazil", "Canada", "Iraq", "Spain", "Uganda", "United States"])

    def test_listing_phrase_from_primary_or_first_category(self):
        self.assertEqual(listing_phrase({"primary_category": "PEP"}), "a politically exposed person")
        self.assertEqual(listing_phrase({"categories": "Sanctions; Enforcement"}), "a sanctioned individual")
        self.assertEqual(listing_phrase({"categories": "Registration"}), "named on a watchlist")

    def test_search_results_only_when_no_other_dob(self):
        row = {"hit_id": "H-1", "alert_id": "A-1", "entity_type": "Individual", "name": "COSTA, MARCOS ROBERTO",
               "primary_category": "PEP", "addresses": "Ribeirao Pires, Sao Paulo, Brazil"}
        index = {"costa marcos roberto": [
            {"result_id": "SR-1", "title": "x", "snippet":
                "May 2019 news reports profiled 33 year old MARCOS ROBERTO COSTA, who is a politically exposed person in Brazil."},
            {"result_id": "SR-2", "title": "x", "snippet":
                "In August 2025, 79 year old MARCOS ROBERTO COSTA, named in adverse media in United Kingdom."},
            {"result_id": "SR-3", "title": "x", "snippet":
                "In 2010, MARCOS ROBERTO COSTA, 21, a politically exposed person in Canada, spoke."},
        ]}
        hp = build_hit(row, index)
        self.assertEqual([(c.source_id, c.value) for c in hp.dob_candidates], [("SR-1", frozenset({1985, 1986}))])
        hp = build_hit({**row, "dobs": "1985"}, index)
        self.assertEqual([c.origin for c in hp.dob_candidates], ["dobs"])

    def test_company_uses_dobs_only(self):
        row = {"hit_id": "H-2", "alert_id": "A-2", "entity_type": "Company", "name": "Acme Ltd",
               "profile_notes": "In May 2010, the 12-year-old company was fined."}
        hp = build_hit(row, {})
        self.assertEqual(hp.entity_type, COMPANY)
        self.assertEqual(hp.dob_candidates, [])


if __name__ == "__main__":
    unittest.main()
