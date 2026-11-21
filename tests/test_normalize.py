import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "system"))

from screening.models import PartialDate as D  # noqa: E402
from screening.normalize import (  # noqa: E402
    age_at, dates_compatible, find_countries, name_parts, parse_date, parse_date_list,
    screened_details, search_query, split_list, to_countries, to_country,
)


class TestDates(unittest.TestCase):
    def test_formats_seen_in_dev(self):
        self.assertEqual(parse_date("1979-12-02"), D(1979, 12, 2))
        self.assertEqual(parse_date("19/05/2004"), D(2004, 5, 19))      # day-first
        self.assertEqual(parse_date("February 19, 2002"), D(2002, 2, 19))
        self.assertEqual(parse_date("17 June 1976"), D(1976, 6, 17))
        self.assertEqual(parse_date("August 6, 1967"), D(1967, 8, 6))
        self.assertEqual(parse_date("1968"), D(1968))
        self.assertEqual(parse_date("1968-02"), D(1968, 2))
        self.assertEqual(parse_date("2016/7/8"), D(2016, 7, 8))

    def test_variants_we_may_meet(self):
        self.assertEqual(parse_date("17th June 1976"), D(1976, 6, 17))
        self.assertEqual(parse_date("Sept. 5, 2020"), D(2020, 9, 5))
        self.assertEqual(parse_date("June 2016"), D(2016, 6))
        self.assertEqual(parse_date("June, 2018"), D(2018, 6))
        self.assertEqual(parse_date("05/13/1990"), D(1990, 5, 13))      # second part > 12 -> month-first
        self.assertEqual(parse_date("17.06.1976"), D(1976, 6, 17))

    def test_unknown_stays_unknown(self):
        self.assertIsNone(parse_date(None))
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date("unknown"))
        self.assertIsNone(parse_date("31/02/2000"))                      # impossible date

    def test_list_field(self):
        self.assertEqual(parse_date_list("1989; 1988"), [D(1989), D(1988)])
        self.assertEqual(parse_date_list(["1968-01-12", "1968"]), [D(1968, 1, 12), D(1968)])
        self.assertEqual(parse_date_list(None), [])

    def test_compatible_every_part_both_give(self):
        self.assertTrue(dates_compatible(D(1968, 3, 5), D(1968)))       # year alone fits a full date
        self.assertTrue(dates_compatible(D(1968, 3, 5), D(1968, 3)))
        self.assertFalse(dates_compatible(D(1968, 3, 5), D(1968, 4)))
        self.assertFalse(dates_compatible(D(1968, 3, 5), D(1968, 3, 6)))
        self.assertFalse(dates_compatible(D(1968), D(1969)))
        self.assertFalse(dates_compatible(None, D(1969)))

    def test_age_at(self):
        self.assertEqual(age_at(D(2007, 6, 1), D(2020, 1, 8)), 12)
        self.assertEqual(age_at(D(2007), D(2020, 1, 8)), 13)            # unknown month: largest age


class TestCountries(unittest.TestCase):
    def test_field_values(self):
        self.assertEqual(to_country("GB"), "United Kingdom")
        self.assertEqual(to_country("Nigerian"), "Nigeria")
        self.assertEqual(to_country("Spain [Residency]"), "Spain")
        self.assertEqual(to_country("Jaén, Jaén, Spain"), "Spain")
        self.assertEqual(to_country("Cote D'Ivoire"), to_country("Côte d'Ivoire"))
        self.assertEqual(to_country("the Netherlands"), "Netherlands")
        self.assertEqual(to_country("USA"), "United States")

    def test_territories_are_their_own_country(self):
        self.assertEqual(to_country("Puerto Rico"), "Puerto Rico")
        self.assertEqual(to_country("Macao Special Administrative Region of China"), "Macao")
        self.assertEqual(to_country("Jersey [Headquarters]"), "Jersey")

    def test_not_countries(self):
        for v in ("International", "Europe [Associated]", "NA", "", None):
            self.assertIsNone(to_country(v))

    def test_list_field(self):
        self.assertEqual(to_countries("Iraq; United States"), ["Iraq", "United States"])

    def test_free_text(self):
        self.assertEqual(find_countries("SULEIMAN YAHAYA, DOB 1956-08-08, was verified via a Nigerian passport."),
                         ["Nigeria"])
        self.assertEqual(find_countries("worked and lived in the Netherlands from 2015 to 2019"), ["Netherlands"])
        self.assertEqual(find_countries("based in Guinea-Bissau"), ["Guinea-Bissau"])
        self.assertEqual(find_countries("born in New Jersey"), ["United States"])
        self.assertEqual(find_countries("Jordan Chad, 45, a teacher in Peru", ignore_names=["Jordan Chad"]), ["Peru"])


class TestNameParts(unittest.TestCase):
    def test_case_accents_punctuation_brackets(self):
        self.assertEqual(name_parts("Stefanović, Milan"), ["stefanovic", "milan"])
        self.assertEqual(name_parts("Juan (Johnny) Perez"), ["juan", "perez"])
        self.assertEqual(name_parts("Jean-Philippe Laurent"), ["jean", "philippe", "laurent"])

    def test_initials_are_not_parts(self):
        self.assertEqual(name_parts("Carl E. Andersen"), ["carl", "andersen"])

    def test_placeholders_are_not_parts(self):
        self.assertEqual(name_parts("NA TEST Smith UNKNOWN XXX 123 N/A"), ["smith"])

    def test_distinct_parts_count_once(self):
        self.assertEqual(name_parts("Juan Juan Perez"), ["juan", "perez"])

    def test_company_legal_forms(self):
        self.assertEqual(name_parts("Danske Bank A/S", True, ["as"]), ["danske", "bank"])
        self.assertEqual(name_parts("Stadtwerke München GmbH", True, ["gmbh"]), ["stadtwerke", "munchen"])

    def test_split_list(self):
        self.assertEqual(split_list("a; b;; c"), ["a", "b", "c"])          # browse workbook
        self.assertEqual(split_list(["1981", "1980"]), ["1981", "1980"])   # data room arrays
        self.assertEqual(split_list(["Baitkamari village, Bangladesh"]), ["Baitkamari village, Bangladesh"])
        self.assertEqual(split_list([{"city": "Madrid", "country": "Spain"}]), ["Spain"])
        self.assertEqual(split_list([]), [])

    def test_screened_details_both_layouts(self):
        nested = {"alert_id": "A-1", "customer": {"name": "Ana Lima", "entity_type": "Individual",
                                                  "dob": "1980", "country": "Brazil", "city": None}}
        flat = {"alert_id": "A-1", "customer_name": "Ana Lima", "entity_type": "Individual",
                "dob": "1980", "country": "Brazil", "city": None}
        self.assertEqual(screened_details(nested), screened_details(flat))
        self.assertEqual(screened_details(nested)["name"], "Ana Lima")

    def test_search_query(self):
        self.assertEqual(search_query("COSTA, MARCOS ROBERTO"), "costa marcos roberto")
        self.assertEqual(search_query("Paul P Griffin"), "griffin paul")
        self.assertEqual(search_query("Raković, Aleksandar"), "aleksandar rakovic")


if __name__ == "__main__":
    unittest.main()
