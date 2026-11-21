import unittest

import _paths  # noqa: F401
from screening.models import PartialDate
from screening.notes_parse import parse_kyc_note, parse_residence_note

D = PartialDate


class KycNoteTests(unittest.TestCase):
    def check(self, text, created, name, dob, country, result="approved", checked=None):
        p = parse_kyc_note(text, created)
        self.assertIsNotNone(p, text)
        self.assertEqual(p["name"], name, text)
        self.assertEqual(p["dob"], dob, text)
        self.assertEqual(p["doc_country"], country, text)
        self.assertEqual(p["result"], result, text)
        if checked:
            self.assertEqual(p["checked_at"], checked, text)

    def test_dev_phrasings(self):
        self.check("Sumsub completed identity verification for NILS MARTIN, born December 13, 1977, "
                   "using a national ID issued in Germany on 2023-02-19.", "2023-02-19",
                   "NILS MARTIN", D(1977, 12, 13), "Germany", checked=D(2023, 2, 19))
        self.check("On 2024-03-16, Persona successfully validated the national ID of TEMITOPE NWOSU, "
                   "DOB 22/09/1956, from Nigeria.", "2024-03-16", "TEMITOPE NWOSU", D(1956, 9, 22), "Nigeria")
        self.check("ANNA NOVAK's driving licence from Germany was accepted by Sumsub on 2024-10-15; "
                   "date of birth verified as December 3, 1954.", "2024-10-15",
                   "ANNA NOVAK", D(1954, 12, 3), "Germany")
        self.check("The national ID belonging to JAVIER BIANCHI (19/12/2003) from Germany was verified "
                   "via Veriff on 2024-12-17.", "2024-12-17", "JAVIER BIANCHI", D(2003, 12, 19), "Germany")
        self.check("Germany-issued passport verified for GIULIA BERNARD (DOB 22/12/1997) via Sumsub on "
                   "2023-09-20.", "2023-09-20", "GIULIA BERNARD", D(1997, 12, 22), "Germany")
        self.check("MARCO CONTI's 1959-04-09 birth date was verified via national ID from Germany by Onfido "
                   "on 2025-07-08.", "2025-07-08", "MARCO CONTI", D(1959, 4, 9), "Germany")
        self.check("Identity check successfully performed via Onfido on 2024-10-03 for ASAD ULLAH KHAN, "
                   "born 1966, using a United Kingdom driving licence.", "2024-10-03",
                   "ASAD ULLAH KHAN", D(1966), "United Kingdom")
        self.check("SULEIMAN YAHAYA, DOB 1956-08-08, was verified by Persona on 2025-07-05 via a Nigerian "
                   "passport.", "2025-07-05", "SULEIMAN YAHAYA", D(1956, 8, 8), "Nigeria")

    def test_placeholders_and_accents_stay_in_the_name(self):
        self.check("Sumsub verified the identity of PAWEŁ N/A N/A on 2025-02-20, utilizing a driving licence "
                   "from Spain showing 20 September 1962 as the birth date.", "2025-02-20",
                   "PAWEŁ N/A N/A", D(1962, 9, 20), "Spain")
        self.check("The Persona system validated FERNÁNDEZ ISABEL, DOB April 23, 1970, on 2023-06-17 via a "
                   "national ID from the United States.", "2023-06-17",
                   "FERNÁNDEZ ISABEL", D(1970, 4, 23), "United States")

    def test_unseen_style_paraphrases(self):
        # wordings that do not occur in dev
        self.check("KYC outcome 12 Mar 2025 - applicant MARIA DA SILVA SANTOS; doc: Brazilian passport; "
                   "D.O.B. 3rd of May 1990; status APPROVED by Jumio.", "2025-03-12",
                   "MARIA DA SILVA SANTOS", D(1990, 5, 3), "Brazil")
        self.check("Jumio could not verify KWAME MENSAH (born 1979-02-11): the Ghana passport image was "
                   "unreadable. Checked 2024-01-05.", "2024-01-05",
                   "KWAME MENSAH", D(1979, 2, 11), "Ghana", result="rejected")
        self.check("Onfido check for LI WEI, DOB 07/08/1985, Chinese passport, returned 'expired document' "
                   "on 2022-11-30.", "2022-11-30", "LI WEI", D(1985, 8, 7), "China", result="expired")
        self.check("Re-verification of the customer Ana Lucia Pereira (date of birth 1988-01-30) passed with "
                   "Veriff on 2025-06-01 using a Portuguese ID card.", "2025-06-01",
                   "Ana Lucia Pereira", D(1988, 1, 30), "Portugal")

    def test_not_a_kyc_note(self):
        self.assertIsNone(parse_kyc_note("Customer asked about savings interest rates.", "2024-01-01"))
        self.assertIsNone(parse_kyc_note("", "2024-01-01"))

    def test_two_countries_means_unknown_document_country(self):
        p = parse_kyc_note("On 2025-06-18, Onfido cleared LIAM HALL, born 1997-01-15, following the "
                           "verification of an Italy-issued driving licence (Note: United Kingdom).",
                           "2025-06-18")
        self.assertIsNone(p["doc_country"])


class ResidenceNoteTests(unittest.TestCase):
    def test_phrasings(self):
        cases = {
            "The client provided information confirming their employment and residency in Pakistan "
            "during 2012 and 2016.": ["Pakistan"],
            "Colombia was where the client lived and held a job from 2010 to 2013.": ["Colombia"],
            "From 2008 to 2018, the individual established their life and career inside the United "
            "Kingdom.": ["United Kingdom"],
            "The account holder reported that they lived and worked in Cote D'Ivoire throughout 2009 to "
            "2015.": ["Cote d'Ivoire"],
            "Customer says they moved from the Netherlands to Spain in 2019.": ["Netherlands", "Spain"],
            "Customer asked why a card payment was declined at a supermarket.": [],
            "Customer called to ask how long an international transfer takes.": [],
        }
        for text, want in cases.items():
            self.assertEqual(parse_residence_note(text), want, text)


if __name__ == "__main__":
    unittest.main()
