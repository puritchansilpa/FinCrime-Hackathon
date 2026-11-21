import json
import os
import tempfile
import unittest

import _paths  # noqa: F401
from screening.customer import dob_fits, name_fits, resolve, search
from screening.fallbacks import parse_date as _local_parse_date
from screening.load import load_data
from screening.models import PartialDate


def cust(rid, name, dob, email=None, phone="+1 555 0100", **kw):
    row = {"record_id": rid, "entity_type": "Individual", "full_name": name, "preferred_name": None,
           "login_name": None, "dob": dob, "nationality": "Spain", "residence_country": "ES",
           "email": email or f"{rid.lower()}@x.example", "phone": phone}
    row.update(kw)
    return row


def alert(aid, name, dob=None, **links):
    row = {"alert_id": aid, "customer_name": name, "entity_type": "Individual", "dob": dob,
           "country": None, "city": None, "account_ref": None, "login_handle": None, "email": None,
           "hit_ids": []}
    row.update(links)
    return row


CUSTOMERS = [
    # a family on one joint account: same surname and phone, different first name and DOB
    cust("CUS-10", "Elvira Velasco MORILLO", "1968-03-05"),
    cust("CUS-11", "Luca MORILLO", "19/12/1940", preferred_name="Luca"),
    cust("CUS-20", "Badsha Mia", "January 12, 1992", email="Badsha.Mia@Mail.example"),
    cust("CUS-30", "Ana Lima", "1990-01-01"),
    cust("CUS-31", "Rui Lima", "1991-01-01"),
    # search targets (no link)
    cust("CUS-40", "Christopher Paul George", "17 September 1951", nationality="Netherlands",
         residence_country="Netherlands", city="Munich", address="152 Station Road, Munich"),
    cust("CUS-41", "Christopher Paul George", "17 September 1951", nationality="Dutch",
         residence_country="United States", city="Chicago", address="116 Church Lane, Chicago"),
    cust("CUS-42", "Christopher Paul George", "1960-01-01", nationality="Netherlands",
         residence_country="NL", city="Munich", address="1 Road, Munich"),
    cust("CUS-50", "N26 Bank AG", "2013-02", entity_type="Company", nationality="Germany",
         residence_country="Germany", city="Berlin", address="125 Church Lane, Berlin"),
    cust("CUS-51", "N26 Bank AG", "2013-02", nationality="Germany", residence_country="DE",
         city="Berlin", address="1 Road, Berlin"),  # an Individual: wrong type for a company alert
    cust("CUS-60", "Mohammad Nadeem", "April 5, 1990", nationality="Pakistan", residence_country="PK"),
    cust("CUS-61", "Mohammad Nadeem", "18/05/1990", nationality="Pakistani", residence_country="Pakistan"),
    cust("CUS-62", "Mohammad Nadeem", "18/05/1990", nationality="Indian", residence_country="India"),
    cust("CUS-70", "Jonathon Smyth", "1985-02-02", nationality="British", residence_country="GB"),
]
ACCOUNTS = [
    {"account_id": "ACC-J", "customer_id": "CUS-10", "login_handle": "elvira1"},
    {"account_id": "ACC-J", "customer_id": "CUS-11", "login_handle": "luca1"},
    {"account_id": "ACC-B", "customer_id": "CUS-20", "login_handle": "Badsha92"},
    {"account_id": "ACC-L", "customer_id": "CUS-30", "login_handle": "ana9"},
    {"account_id": "ACC-L", "customer_id": "CUS-31", "login_handle": "rui9"},
    {"account_id": "ACC-GHOST", "customer_id": "CUS-404", "login_handle": "ghost"},
]


class DateAndNameTests(unittest.TestCase):
    def test_parse_formats(self):
        self.assertEqual(_local_parse_date("1968-03-05"), PartialDate(1968, 3, 5))
        self.assertEqual(_local_parse_date("19/12/1940"), PartialDate(1940, 12, 19))  # day-first
        self.assertEqual(_local_parse_date("17 June 1976"), PartialDate(1976, 6, 17))
        self.assertEqual(_local_parse_date("June 17, 1976"), PartialDate(1976, 6, 17))
        self.assertEqual(_local_parse_date("Sept 1976"), PartialDate(1976, 9))
        self.assertEqual(_local_parse_date("1976-06"), PartialDate(1976, 6))
        self.assertEqual(_local_parse_date("1976"), PartialDate(1976))
        self.assertIsNone(_local_parse_date("13/13/1976"))
        self.assertIsNone(_local_parse_date("unknown"))
        self.assertIsNone(_local_parse_date(None))

    def test_dob_fits_only_compares_known_parts(self):
        self.assertTrue(dob_fits("1980", "02/01/1980"))
        self.assertTrue(dob_fits("1980-01-02", "02/01/1980"))
        self.assertFalse(dob_fits("1980-01-02", "01/02/1980"))   # 1 Feb, not 2 Jan
        self.assertFalse(dob_fits("1981", "1980-01-02"))
        self.assertTrue(dob_fits(None, "1980-01-02"))             # unknown stays unknown
        self.assertTrue(dob_fits("garbage", "1980-01-02"))

    def test_name_fits(self):
        self.assertTrue(name_fits("Elvira Velasco MORILLO", ["Elvira Velasco Morillo"]))
        self.assertTrue(name_fits("ELVIRA MORILLO", ["Elvira Velasco Morillo"]))  # shorter name inside
        self.assertFalse(name_fits("Elvira Velasco MORILLO", ["Luca MORILLO", "Luca"]))  # family member
        self.assertTrue(name_fits("José Müller", [None, "Jose MULLER"]))
        self.assertFalse(name_fits(None, ["Ana"]))


class RecordFitsOrderTests(unittest.TestCase):
    """The fuzzy name check is the expensive one: it runs only after the cheap checks pass."""

    def test_name_is_not_compared_when_the_dob_already_rules_the_record_out(self):
        from unittest import mock
        from screening import customer
        alert = {"customer_name": "ANA LOPEZ", "dob": "1980-01-01", "entity_type": "Individual"}
        with mock.patch.object(customer, "name_fits", return_value=True) as names:
            self.assertFalse(customer.record_fits(alert, cust("CUS-1", "ANA LOPEZ", "1981-01-01")))
            names.assert_not_called()
            self.assertTrue(customer.record_fits(alert, cust("CUS-2", "ANA LOPEZ", "1980-01-01")))
            names.assert_called_once()


class ResolveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        for name, rows in (("customers", CUSTOMERS), ("accounts", ACCOUNTS)):
            with open(os.path.join(cls.tmp.name, name + ".jsonl"), "w", encoding="utf-8") as fh:
                fh.writelines(json.dumps(r) + "\n" for r in rows)
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            cls.data = load_data(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def ids(self, res):
        return [p.record_ids for p in res.persons]

    def test_joint_account_picks_the_screened_holder(self):
        res = resolve(alert("A1", "Elvira Velasco MORILLO", "1968-03-05", account_ref="ACC-J"), self.data)
        self.assertEqual(self.ids(res), [["CUS-10"]])
        self.assertIn("joint holders CUS-10 and CUS-11", res.path[0])
        self.assertIn("fit CUS-10", res.path[-1])

    def test_joint_account_uses_dob_when_names_both_fit(self):
        res = resolve(alert("A2", "Lima", "1991-01-01", account_ref="ACC-L"), self.data)
        self.assertEqual(self.ids(res), [["CUS-31"]])

    def test_joint_account_nobody_fits_keeps_all(self):
        res = resolve(alert("A3", "Someone Else", None, account_ref="ACC-J"), self.data)
        self.assertEqual(self.ids(res), [["CUS-10"], ["CUS-11"]])
        self.assertIn("fit none of them", " ".join(res.path))

    def test_joint_account_several_fit_keeps_them(self):
        res = resolve(alert("A4", "Lima", None, account_ref="ACC-L"), self.data)
        self.assertEqual(self.ids(res), [["CUS-30"], ["CUS-31"]])

    def test_login_and_email_links_ignore_case(self):
        res = resolve(alert("A5", "Badsha Mia", login_handle="badsha92"), self.data)
        self.assertEqual(self.ids(res), [["CUS-20"]])
        res = resolve(alert("A6", "Badsha Mia", email=" badsha.mia@mail.EXAMPLE "), self.data)
        self.assertEqual(self.ids(res), [["CUS-20"]])

    def test_single_linked_record_is_trusted_even_if_name_differs(self):
        res = resolve(alert("A7", "B. Mia", account_ref="ACC-B"), self.data)
        self.assertEqual(self.ids(res), [["CUS-20"]])

    def test_dead_links_and_no_link(self):
        res = resolve(alert("A8", "Ghost", account_ref="ACC-GHOST"), self.data)
        self.assertEqual(res.persons, [])
        self.assertIn("not in customers", res.path[0])
        res = resolve(alert("A9", "Nobody", account_ref="ACC-NOPE"), self.data)
        self.assertEqual(res.persons, [])
        res = resolve(alert("A10", "Nobody"), self.data)
        self.assertEqual(res.persons, [])
        self.assertIn("no record fits", res.path[-1])

    def test_search_uses_name_dob_country_and_city(self):
        a = alert("S1", "Christopher Paul George", "1951-09-17", country="Netherlands", city="Munich")
        res = resolve(a, self.data)
        # The search finds CUS-40 only (CUS-41 lives in Chicago, CUS-42 has another DOB);
        # CUS-41 then joins as the same person: same phone and same full date of birth.
        self.assertEqual(self.ids(res), [["CUS-40", "CUS-41"]])
        self.assertIn("name, date of birth, country and city -> customers -> CUS-40", res.path[0])

    def test_search_country_accepts_codes_and_demonyms(self):
        a = alert("S2", "Muhammad Nadeem", "1990", country="Pakistan")
        self.assertEqual([r["record_id"] for r in search(a, self.data)], ["CUS-60", "CUS-61"])

    def test_search_respects_entity_type(self):
        a = alert("S3", "N26 Bank SE", "2013-02", country="Germany", city="Berlin", entity_type="Company")
        self.assertEqual([r["record_id"] for r in search(a, self.data)], ["CUS-50"])

    def test_search_finds_typos_in_every_part_through_birth_year(self):
        a = alert("S4", "Jonathan Smith", "1985", country="United Kingdom")
        self.assertEqual([r["record_id"] for r in search(a, self.data)], ["CUS-70"])

    def test_search_without_match_finds_nobody(self):
        res = resolve(alert("S5", "Nobody Atall", "1900"), self.data)
        self.assertEqual(res.persons, [])
        self.assertIn("no record fits", res.path[0])

    def test_link_filter_also_uses_country(self):
        # both Lima holders fit the name; only one fits the screened country
        res = resolve(alert("S6", "Lima", None, account_ref="ACC-L", country="Spain"), self.data)
        self.assertEqual(len(res.persons), 2)
        res = resolve(alert("S7", "Lima", None, account_ref="ACC-L", country="France"), self.data)
        self.assertIn("fit none of them", " ".join(res.path))

    def test_person_facts_carry_their_source(self):
        person = resolve(alert("A11", "Luca Morillo", "1940", account_ref="ACC-J"), self.data).persons[0]
        self.assertEqual(person.record_ids, ["CUS-11"])
        self.assertEqual(person.entity_type, "Individual")
        self.assertEqual({(f.value, f.source_id) for f in person.declared_names},
                         {("Luca MORILLO", "CUS-11"), ("Luca", "CUS-11")})
        self.assertEqual(person.declared_dobs[0].value, PartialDate(1940, 12, 19))
        self.assertEqual(person.declared_dobs[0].source_id, "CUS-11")
        self.assertEqual(sorted(f.origin for f in person.countries), ["nationality", "residence_country"])


if __name__ == "__main__":
    unittest.main()
