"""Places we cannot tie to a country (HANDOFF.md B1, B2, P1, P2).

An unmapped place is never evidence of a mismatch: while any place on either side is
unresolved, 'every country tied to X' is not known, so location cannot clear a hit.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from screening import notes_parse
from screening.customer import resolve
from screening.hit import build_hit, hit_countries, hit_unresolved_places
from screening.load import load_data
from screening.models import (DIFFERENT_ENTITY, INDIVIDUAL, LOCATION_MISMATCH, REVIEW, Fact, Person)
from screening.names import Variants
from screening.normalize import find_place_countries, is_unresolved_place, to_country
from screening.policy import decide

ALERT = {"alert_id": "A-Y", "screened_at": "2026-11-01"}


def hit_row(**fields):
    row = {"hit_id": "H-Y", "alert_id": "A-Y", "entity_type": "Individual", "name": "Juan Perez"}
    row.update(fields)
    return row


def uk_customer(**extra):
    return Person(["CUS-1"], INDIVIDUAL, verified_name=Fact("Juan Perez", "KYC-1"),
                  countries=[Fact("United Kingdom", "CUS-1")], **extra)


class TestPlaceLookup(unittest.TestCase):          # B2
    def test_cities_and_regions(self):
        self.assertEqual(to_country("London"), "United Kingdom")
        self.assertEqual(to_country("Karachi"), "Pakistan")
        self.assertEqual(to_country("Lagos State"), "Nigeria")
        self.assertEqual(to_country("Lagos, Lagos State"), "Nigeria")
        self.assertEqual(to_country("10 Downing Street, London"), "United Kingdom")

    def test_formal_prefixes_and_inverted_names(self):
        self.assertEqual(to_country("Kingdom of Saudi Arabia"), "Saudi Arabia")
        self.assertEqual(to_country("Islamic Republic of Pakistan"), "Pakistan")
        self.assertEqual(to_country("Korea, Republic of"), "South Korea")
        self.assertEqual(to_country("Iran, Islamic Republic of"), "Iran")

    def test_georgia_the_us_state(self):
        self.assertEqual(to_country("Atlanta, Georgia"), "United States")
        self.assertEqual(to_country("Tbilisi, Georgia"), "Georgia")
        self.assertEqual(to_country("Georgia"), "Georgia")

    def test_country_still_wins_over_city(self):
        self.assertEqual(to_country("Spain [Residency]"), "Spain")
        self.assertEqual(to_country("Fayette County, Atlanta, Georgia, United States"), "United States")

    def test_unresolved(self):
        self.assertTrue(is_unresolved_place("Smallville"))
        for v in ("London", "International", "Europe [Associated]", "", None, "N/A"):
            self.assertFalse(is_unresolved_place(v), v)

    def test_places_in_free_text(self):
        self.assertEqual(find_place_countries("previously called Lagos home, 2012 to 2019"), ["Nigeria"])
        self.assertEqual(find_place_countries("it was a nice place by the river delta"), [])  # lower case
        self.assertEqual(find_place_countries("Paris Jackson lived abroad", ignore_names=["Paris Jackson"]), [])


class TestHitSide(unittest.TestCase):              # B1
    def test_city_address_resolves(self):
        self.assertEqual(hit_countries(hit_row(addresses=["London", "Karachi, Pakistan"])),
                         ["United Kingdom", "Pakistan"])

    def test_unmapped_place_is_recorded(self):
        self.assertEqual(hit_unresolved_places(hit_row(addresses=["Smallville", "Karachi, Pakistan"])),
                         ["Smallville"])
        self.assertEqual(hit_unresolved_places(hit_row(addresses=["International [Associated]"])), [])

    def test_unmapped_place_blocks_location_clearance(self):
        v = Variants()
        cleared = decide(uk_customer(), build_hit(hit_row(addresses=["Karachi, Pakistan"]), {}), ALERT, v)
        self.assertEqual((cleared.decision, cleared.reason_code), (DIFFERENT_ENTITY, LOCATION_MISMATCH))
        held = decide(uk_customer(), build_hit(hit_row(addresses=["Smallville", "Karachi, Pakistan"]), {}),
                      ALERT, v)
        self.assertEqual(held.decision, REVIEW)
        self.assertIn("Smallville could not be tied to a country", held.reason)

    def test_city_that_resolves_to_a_shared_country_is_not_cleared(self):
        d = decide(uk_customer(), build_hit(hit_row(addresses=["London", "Karachi, Pakistan"]), {}),
                   ALERT, Variants())
        self.assertNotEqual(d.decision, DIFFERENT_ENTITY)

    def test_customer_unresolved_place_blocks_too(self):
        p = uk_customer(unresolved_places=["Smallville (CUS-1)"])
        d = decide(p, build_hit(hit_row(addresses=["Karachi, Pakistan"]), {}), ALERT, Variants())
        self.assertEqual(d.decision, REVIEW)


CUSTOMERS = [
    {"record_id": "CUS-1", "entity_type": "Individual", "full_name": "Ada Obi", "dob": "1990-01-01",
     "nationality": "Nigeria", "residence_country": "Smallville", "email": "ada@x.example", "phone": "+1"},
    {"record_id": "CUS-2", "entity_type": "Individual", "full_name": "Bola Ade", "dob": "1985-02-02",
     "nationality": "Nigeria", "residence_country": "GB", "email": "bola@x.example", "phone": "+2"},
]
ACCOUNTS = [{"account_id": f"ACC-{i}", "customer_id": f"CUS-{i}", "login_handle": f"u{i}", "phone": None}
            for i in (1, 2)]
NOTES = [
    {"note_id": "NOTE-LAGOS", "requester_email": "bola@x.example", "created_at": "2024-02-02",
     "channel": "phone", "text": "The customer previously called Lagos home, from 2012 until 2019."},
    {"note_id": "NOTE-SMALL", "requester_email": "bola@x.example", "created_at": "2024-02-03",
     "channel": "email", "text": "Spent 2014 to 2018 living and working in Smallville."},
]


class TestCustomerSide(unittest.TestCase):         # P1, P2
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        for name, rows in (("customers", CUSTOMERS), ("accounts", ACCOUNTS), ("notes", NOTES)):
            with open(os.path.join(cls.tmp.name, name + ".jsonl"), "w", encoding="utf-8") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in rows)
        with contextlib.redirect_stderr(io.StringIO()):
            cls.data = load_data(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def person(self, account):
        alert = {"alert_id": "A1", "entity_type": "Individual", "account_ref": account, "hit_ids": []}
        return resolve(alert, self.data).persons[0]

    def test_unmapped_record_country_is_recorded(self):           # P1
        self.assertEqual(self.person("ACC-1").unresolved_places, ["Smallville (CUS-1)"])

    def test_residence_note_city_maps_to_country(self):            # P2
        self.assertEqual(notes_parse.parse_residence_note(NOTES[0]["text"]), ["Nigeria"])
        got = {(f.value, f.source_id) for f in self.person("ACC-2").countries}
        self.assertIn(("Nigeria", "NOTE-LAGOS"), got)

    def test_residence_note_with_unknown_place_is_recorded(self):  # P1 + P2
        self.assertEqual(self.person("ACC-2").unresolved_places, ["the place named in NOTE-SMALL"])


if __name__ == "__main__":
    unittest.main()
