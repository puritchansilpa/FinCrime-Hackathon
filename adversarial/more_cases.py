"""Fifty more cases, tags 59-108, around the seven misses in the first set.

`joins` is what the current resolver does, not what the policy requires.
Workstream A: load.py (phone_key, norm_key), customer.py, notes_parse.py.
Workstream B: hit.py.
"""


def add(b, same_reason, dob_reason, review_nodob, path_join, chain, qname):
    def loc_reason(cust, hit):
        return ("The customer is linked only to %s but the hit is linked only to %s." % (cust, hit))

    def pair(tag, title, category, weakness, naive_note, module,
             a_name, b_name, dob_a, dob_b, phone_a, phone_b,
             kyc_a_name, kyc_a_dob, kyc_a_at, kyc_b_name, kyc_b_dob, kyc_b_at,
             hit_name, hit_dob, country, city, gold, joins,
             naive_decision, naive_code, doc_a=None, doc_b=None,
             kyc_b_result="approved"):
        """gold 'merge': the two records are one person and B's check decides SAME.
        gold 'keep': they are not one person; A's check matches the hit (SAME).
        """
        a = b.customer(tag, a_name, dob_a, country, city, phone=phone_a)
        other = b.customer(tag + "B", b_name, dob_b, country, city, phone=phone_b)
        acc, app, kid_a = chain(
            b, tag, a, kyc_a_name, kyc_a_dob, country,
            checked_at=kyc_a_at, doc=doc_a, acc_phone=phone_a)
        chain(b, tag + "B", other, kyc_b_name, kyc_b_dob, country,
              checked_at=kyc_b_at, doc=doc_b, acc_phone=phone_b,
              result=kyc_b_result)
        kid_b = "ADV-KYC-%sB" % tag
        hid = b.hit(tag, "ADV-A-%s" % tag, hit_name, dobs=hit_dob, countries=country)
        b.alert(tag, hit_name, [hid], dob=hit_dob, country=country, city=city, account=acc)
        if gold == "merge":
            decision = "SAME_ENTITY"
            codes = ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"]
            customers = [a, other]
            evidence = [a, other, kid_b]
            reason = same_reason(kyc_b_dob, kid_b, hit_dob, country, hit_name)
            how = "same phone and full date of birth, or same document number -> one person: %s, %s" % (a, other)
            steps = [
                "account_ref %s -> accounts -> customer %s" % (acc, a),
                how,
                "latest approved check %s" % kid_b,
            ]
            naive_customer = a
        else:
            decision = "SAME_ENTITY"
            codes = ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"]
            customers = [a]
            evidence = [a, kid_a]
            reason = same_reason(kyc_a_dob, kid_a, hit_dob, country, hit_name)
            steps = [
                "account_ref %s -> accounts -> customer %s" % (acc, a),
                "%s -> accounts %s -> onboarding ADV-APP-%s -> latest approved check %s" % (a, acc, tag, kid_a),
            ]
            naive_customer = a
        b.lab(hid, "ADV-A-%s" % tag, decision, codes, customers, evidence, reason,
              path_join(steps, decision, codes, reason),
              category, weakness, naive_decision, naive_code, naive_note,
              naive_customer, title, module=module)
        b.groups("ADV-A-%s" % tag, [[a, other]] if joins else [[a]])

    # --- phones. Spaces, dashes and brackets already share a digit string. ---
    pair("59", "Spaces in a phone number", "phone_dob_merge",
         "The same number is written with spaces. The newest approved check agrees with the hit; the linked record's older check does not.",
         "Compares the phone strings and keeps the older check, then clears.",
         "load.py phone_key, via customer.py",
         "Otto Feldmann", "Lina Feldmann", "1990-01-15", "1990-01-15",
         "+49 151 234 5601", "+491512345601",
         "Otto Feldmann", "1960-01-01", "2018-01-01", "Lina Feldmann", "1990-01-15", "2024-06-01",
         "Lina Feldmann", "1990-01-15", "Germany", "Munich", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")
    pair("60", "Dashes in a phone number", "phone_dob_merge",
         "Dashes do not make a new phone number. Same full date of birth, so the records are one person.",
         "Keeps the dashes and clears on the older check.",
         "load.py phone_key, via customer.py",
         "Otto Lindholm", "Lina Lindholm", "1988-03-03", "1988-03-03",
         "+44-7700-900-601", "+447700900601",
         "Otto Lindholm", "1955-03-03", "2018-01-01", "Lina Lindholm", "1988-03-03", "2024-06-01",
         "Lina Lindholm", "1988-03-03", "United Kingdom", "Leeds", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")
    pair("61", "Brackets in a phone number", "phone_dob_merge",
         "Brackets and a leading plus are the same number as the digits alone.",
         "String-compares the bracketed form and clears.",
         "load.py phone_key, via customer.py",
         "Otto Vasiliev", "Lina Vasiliev", "1987-07-07", "1987-07-07",
         "+1 (202) 555-0161", "+12025550161",
         "Otto Vasiliev", "1950-07-07", "2018-01-01", "Lina Vasiliev", "1987-07-07", "2024-06-01",
         "Lina Vasiliev", "1987-07-07", "United States", "Chicago", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")
    pair("62", "National 0 versus +44", "phone_dob_merge",
         "07700 900621 is the same United Kingdom number as +44 7700 900621. The trunk 0 is not a different subscriber. Same full date of birth.",
         "Keeps the leading 0, does not join the records, and clears on the older check.",
         "load.py phone_key, via customer.py",
         "Otto Morello", "Lina Morello", "1992-05-05", "1992-05-05",
         "+44 7700 900621", "07700 900621",
         "Otto Morello", "1962-05-05", "2018-01-01", "Lina Morello", "1992-05-05", "2024-06-01",
         "Lina Morello", "1992-05-05", "United Kingdom", "Manchester", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")
    pair("63", "00 prefix with spaces", "phone_dob_merge",
         "0033 6 12 34 56 78 is the same French number as +33 6 12 34 56 78. Same full date of birth.",
         "Keeps the 00 exit code and clears on the older check.",
         "load.py phone_key, via customer.py",
         "Otto Quintana", "Lina Quintana", "1993-06-06", "1993-06-06",
         "+33 6 12 34 56 78", "0033 6 12 34 56 78",
         "Otto Quintana", "1963-06-06", "2018-01-01", "Lina Quintana", "1993-06-06", "2024-06-01",
         "Lina Quintana", "1993-06-06", "France", "Lyon", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")
    pair("64", "Extension x99", "phone_dob_merge",
         "x99 is an extension on the same number, not a different phone. Same full date of birth.",
         "Appends 99 to the digits and treats it as a different number, then clears.",
         "load.py phone_key, via customer.py",
         "Otto Barragan", "Lina Barragan", "1994-08-08", "1994-08-08",
         "+1 202 555 0164", "+1 202 555 0164 x99",
         "Otto Barragan", "1964-08-08", "2018-01-01", "Lina Barragan", "1994-08-08", "2024-06-01",
         "Lina Barragan", "1994-08-08", "United States", "Boston", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")
    pair("65", "Extension written as ext", "phone_dob_merge",
         "ext. 205 is an extension on +1 202 555 0165. Same number, same full date of birth.",
         "Keeps the extension digits and clears.",
         "load.py phone_key, via customer.py",
         "Otto Castell", "Lina Castell", "1995-09-09", "1995-09-09",
         "+1 202 555 0165", "+1 202 555 0165 ext. 205",
         "Otto Castell", "1965-09-09", "2018-01-01", "Lina Castell", "1995-09-09", "2024-06-01",
         "Lina Castell", "1995-09-09", "United States", "Denver", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")
    pair("66", "Same phone, different full date of birth", "phone_dob_merge",
         "The number matches and the dates of birth do not. Family members share phones. Do not merge. The linked customer's own check agrees with the hit.",
         "Joins on the phone alone, takes the other person's newer check, and clears.",
         "customer.py",
         "Lina Donnelly", "Otto Donnelly", "1991-02-02", "1966-02-02",
         "+1 202 555 0166", "+1 202 555 0166",
         "Lina Donnelly", "1991-02-02", "2024-06-01", "Otto Donnelly", "1966-02-02", "2025-06-01",
         "Lina Donnelly", "1991-02-02", "Ireland", "Dublin", "keep", False,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")
    pair("67", "Same phone, only a year on the other record", "phone_dob_merge",
         "A full date and a year-only date are not the same full date of birth. Do not merge. The linked check agrees with the hit.",
         "Joins on phone plus birth year, takes the other check, and clears.",
         "customer.py",
         "Lina Fournier", "Otto Fournier", "1985-07-07", "1985",
         "+33 6 11 22 33 67", "+33611223367",
         "Lina Fournier", "1985-07-07", "2024-06-01", "Otto Fournier", "1960-01-01", "2025-06-01",
         "Lina Fournier", "1985-07-07", "France", "Nantes", "keep", False,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")
    pair("68", "Phone numbers one digit apart", "phone_dob_merge",
         "+1 202 555 0168 and +1 202 555 0169 are different numbers, and the dates of birth differ. The linked check agrees with the hit.",
         "Fuzzy-matches the phone, merges, and clears on the other person's check.",
         "customer.py",
         "Lina Gallardo", "Otto Gallardo", "1986-04-04", "1956-04-04",
         "+1 202 555 0168", "+1 202 555 0169",
         "Lina Gallardo", "1986-04-04", "2024-06-01", "Otto Gallardo", "1956-04-04", "2025-06-01",
         "Lina Gallardo", "1986-04-04", "Spain", "Valencia", "keep", False,
         "DIFFERENT_ENTITY", "DOB_MISMATCH")

    # --- document numbers ---
    pair("69", "Dash in a document number", "document_merge",
         "WQ-770069 and WQ770069 are the same document number on approved checks.",
         "Keeps the dash, does not join, and clears on the older check.",
         "load.py norm_key, via customer.py",
         "Otto Janssen", "Lina Janssen", "1972-02-02", "1991-04-04",
         "+1 202 555 1169", "+1 202 555 1269",
         "Otto Janssen", "1972-02-02", "2018-01-01", "Lina Janssen", "1991-04-04", "2024-06-01",
         "Lina Janssen", "1991-04-04", "Netherlands", "Rotterdam", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH", doc_a="WQ-770069", doc_b="WQ770069")
    pair("70", "Document number differs only by case", "document_merge",
         "Case does not change a document number. The newest approved check agrees with the hit.",
         "Compares case-sensitively and clears.",
         "load.py norm_key, via customer.py",
         "Otto Lefebvre", "Lina Lefebvre", "1971-01-01", "1992-08-08",
         "+1 202 555 1170", "+1 202 555 1270",
         "Otto Lefebvre", "1971-01-01", "2018-01-01", "Lina Lefebvre", "1992-08-08", "2024-06-01",
         "Lina Lefebvre", "1992-08-08", "Belgium", "Brussels", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH", doc_a="wq770070", doc_b="WQ770070")
    pair("71", "Double space in a document number", "document_merge",
         "WQ  770071 and WQ770071 are the same document number.",
         "Keeps the spaces and clears.",
         "load.py norm_key, via customer.py",
         "Otto Montague", "Lina Montague", "1973-03-03", "1993-03-03",
         "+1 202 555 1171", "+1 202 555 1271",
         "Otto Montague", "1973-03-03", "2018-01-01", "Lina Montague", "1993-03-03", "2024-06-01",
         "Lina Montague", "1993-03-03", "Canada", "Toronto", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH", doc_a="WQ  770071", doc_b="WQ770071")
    pair("72", "Dash and space in a document number", "document_merge",
         "WQ-77 0072 and WQ770072 are the same document number.",
         "Requires the punctuation to match and clears.",
         "load.py norm_key, via customer.py",
         "Otto Noriega", "Lina Noriega", "1974-04-04", "1994-04-04",
         "+1 202 555 1172", "+1 202 555 1272",
         "Otto Noriega", "1974-04-04", "2018-01-01", "Lina Noriega", "1994-04-04", "2024-06-01",
         "Lina Noriega", "1994-04-04", "Spain", "Bilbao", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH", doc_a="WQ-77 0072", doc_b="WQ770072")
    pair("73", "Leading zeros in a document number", "document_merge",
         "000770073 and 770073 are the same document number.",
         "Keeps the leading zeros and clears.",
         "load.py norm_key, via customer.py",
         "Otto Olsson", "Lina Olsson", "1975-05-05", "1995-05-05",
         "+1 202 555 1173", "+1 202 555 1273",
         "Otto Olsson", "1975-05-05", "2018-01-01", "Lina Olsson", "1995-05-05", "2024-06-01",
         "Lina Olsson", "1995-05-05", "Sweden", "Stockholm", "merge", True,
         "DIFFERENT_ENTITY", "DOB_MISMATCH", doc_a="000770073", doc_b="770073")
    pair("74", "Document numbers one digit apart", "document_merge",
         "WQ770074 and WQ770075 are different documents, and the people have different dates of birth. The linked check agrees with the hit.",
         "Fuzzy-matches the document number, merges, and clears.",
         "customer.py",
         "Lina Papadakis", "Otto Papadakis", "1989-09-09", "1959-09-09",
         "+1 202 555 1174", "+1 202 555 1274",
         "Lina Papadakis", "1989-09-09", "2024-06-01", "Otto Papadakis", "1959-09-09", "2025-06-01",
         "Lina Papadakis", "1989-09-09", "Greece", "Athens", "keep", False,
         "DIFFERENT_ENTITY", "DOB_MISMATCH", doc_a="WQ770074", doc_b="WQ770084")
    pair("75", "Same number only on a rejected check", "document_merge",
         "The other record's copy of WQ770075 was rejected, so it does not join the person. The linked approved check agrees with the hit.",
         "Joins on a rejected check's document number and clears.",
         "customer.py",
         "Lina Quintero", "Otto Quintero", "1990-10-10", "1960-10-10",
         "+1 202 555 1175", "+1 202 555 1275",
         "Lina Quintero", "1990-10-10", "2024-06-01", "Otto Quintero", "1960-10-10", "2025-06-01",
         "Lina Quintero", "1990-10-10", "Spain", "Seville", "keep", False,
         "DIFFERENT_ENTITY", "DOB_MISMATCH", doc_a="WQ770075", doc_b="WQ770075",
         kyc_b_result="rejected")

    def note_case(tag, title, text, declared, verified, hit_dob, country, city, name,
                  decision, codes, evidence_kind, reason, weakness, naive_decision, naive_code,
                  naive_note, module, ambiguous=False, ambiguous_note=None):
        cid = b.customer(tag, name, declared, country, city)
        acc = b.account(tag, cid)
        email = b.customers[cid]["email"]
        nid = b.note(tag, email, text, "kyc", "2024-06-01")
        hid = b.hit(tag, "ADV-A-%s" % tag, name, dobs=hit_dob, countries=country)
        b.alert(tag, name, [hid], dob=hit_dob, country=country, city=city, account=acc)
        evidence = [cid] if evidence_kind == "record" else [cid, nid]
        steps = ["account_ref %s -> accounts -> customer %s" % (acc, cid),
                 "customer email -> notes -> %s" % nid]
        b.lab(hid, "ADV-A-%s" % tag, decision, codes, [cid], evidence, reason,
              path_join(steps, decision, codes, reason),
              "kyc_note", weakness, naive_decision, naive_code, naive_note, cid, title,
              ambiguous, ambiguous_note, module)
        b.groups("ADV-A-%s" % tag, [[cid]])

    note_case(
        "76", "Old passport expired, check approved",
        "The old passport has expired. Sumsub approved LINA RINALDI, DOB 1982-04-04, via a German passport on 2024-06-01.",
        "1970-01-01", "1982-04-04", "1982-04-04", "Germany", "Berlin", "Lina Rinaldi",
        "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], "note",
        same_reason("1982-04-04", "ADV-NOTE-76", "1982-04-04", "Germany", "Lina Rinaldi"),
        "The expired passport is the old document. The sentence is an approved check for 1982-04-04. The record's 1970-01-01 is only declared.",
        "DIFFERENT_ENTITY", "DOB_MISMATCH",
        "Sees expired, drops the note, and clears on 1970-01-01.",
        "notes_parse.py")
    note_case(
        "77", "Prior document had expired",
        "A prior identity document had expired. Persona approved LINA STAVROS, DOB 1983-05-05, using a passport issued in Greece on 2024-06-01.",
        "1968-05-05", "1983-05-05", "1983-05-05", "Greece", "Athens", "Lina Stavros",
        "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], "note",
        same_reason("1983-05-05", "ADV-NOTE-77", "1983-05-05", "Greece", "Lina Stavros"),
        "Had expired describes the prior document. The new check is approved.",
        "DIFFERENT_ENTITY", "DOB_MISMATCH",
        "Treats the whole note as expired and clears on the declared date.",
        "notes_parse.py")
    note_case(
        "78", "Previous check rejected, this one approved",
        "The previous check was rejected. Onfido approved LINA TAVARES, DOB 1984-06-06, via a Portuguese passport on 2024-08-01.",
        "1969-06-06", "1984-06-06", "1984-06-06", "Portugal", "Lisbon", "Lina Tavares",
        "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], "note",
        same_reason("1984-06-06", "ADV-NOTE-78", "1984-06-06", "Portugal", "Lina Tavares"),
        "Rejected applies to the previous check. This note records a later approval.",
        "DIFFERENT_ENTITY", "DOB_MISMATCH",
        "Sees rejected anywhere and drops the approval.",
        "notes_parse.py")
    note_case(
        "79", "Out of date licence replaced",
        "The out of date licence was replaced. Persona approved LINA UEDA, DOB 1985-07-07, via a Japanese passport on 2024-06-01.",
        "1967-07-07", "1985-07-07", "1985-07-07", "Japan", "Tokyo", "Lina Ueda",
        "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], "note",
        same_reason("1985-07-07", "ADV-NOTE-79", "1985-07-07", "Japan", "Lina Ueda"),
        "Out of date describes the replaced licence. The check in the sentence is approved.",
        "DIFFERENT_ENTITY", "DOB_MISMATCH",
        "Matches out of date, drops the note, and clears.",
        "notes_parse.py")
    note_case(
        "80", "The check itself expired",
        "The check expired before Persona could approve LINA VILLANUEVA, DOB 1986-08-08, via a Spanish passport.",
        "1971-08-08", None, "1986-08-08", "Spain", "Madrid", "Lina Villanueva",
        "DIFFERENT_ENTITY", ["DOB_MISMATCH"], "record",
        dob_reason("1971-08-08", "ADV-CUS-80", "the hit's listed date of birth is 1986-08-08"),
        "This check expired and was not approved. It is not evidence. The declared date of birth contradicts the hit.",
        "SAME_ENTITY", "NAME_DOB_MATCH",
        "Sees the word approve and the date in the note, and confirms.",
        "notes_parse.py")
    note_case(
        "81", "Clean approved note",
        "Persona approved LINA WESTERBERG, born 4 July 1982, using a passport issued in Sweden on 2024-06-01.",
        "1962-07-04", "1982-07-04", "1982-07-04", "Sweden", "Stockholm", "Lina Westerberg",
        "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], "note",
        same_reason("1982-07-04", "ADV-NOTE-81", "1982-07-04", "Sweden", "Lina Westerberg"),
        "A note with no expired or rejected wording is an approved check. The declared 1962-07-04 does not outrank it.",
        "DIFFERENT_ENTITY", "DOB_MISMATCH",
        "Ignores the note and clears on the declared date.",
        "notes_parse.py")
    note_case(
        "82", "Expired flag was an error",
        "The expired flag was a system error. Onfido approved LINA XANTHOS, DOB 1987-09-09, via a Greek passport on 2024-06-01.",
        "1964-09-09", "1987-09-09", "1987-09-09", "Greece", "Athens", "Lina Xanthos",
        "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], "note",
        same_reason("1987-09-09", "ADV-NOTE-82", "1987-09-09", "Greece", "Lina Xanthos"),
        "The note says the expired flag was wrong and the check was approved.",
        "DIFFERENT_ENTITY", "DOB_MISMATCH",
        "Matches expired, drops the note, and clears on 1964-09-09.",
        "notes_parse.py")

    def lived(tag, title, text, name, home, hit_country, city, decision, weakness,
              naive_decision, naive_code, naive_note, module, cite_note):
        cid = b.customer(tag, name, "1990-02-02", home, city)
        acc, app, kid = chain(b, tag, cid, name, "1990-02-02", home)
        nid = b.note(tag, b.customers[cid]["email"], text, "phone")
        hid = b.hit(tag, "ADV-A-%s" % tag, name, countries=hit_country)
        b.alert(tag, name, [hid], dob="1990-02-02", country=home, city=city, account=acc)
        if decision == "REVIEW":
            codes = ["INSUFFICIENT_DATA"]
            reason = review_nodob(hit_country, name)
            evidence = [cid, nid] if cite_note else [cid, kid]
        else:
            codes = ["LOCATION_MISMATCH"]
            reason = loc_reason(home, hit_country)
            evidence = [cid, kid]
        steps = [
            "account_ref %s -> accounts -> customer %s" % (acc, cid),
            "customer email -> notes -> %s" % nid,
        ]
        b.lab(hid, "ADV-A-%s" % tag, decision, codes, [cid], evidence, reason,
              path_join(steps, decision, codes, reason),
              "residence_note", weakness, naive_decision, naive_code, naive_note, cid, title,
              module=module)
        b.groups("ADV-A-%s" % tag, [[cid]])

    lived("83", "Raised in Pakistan", "She was raised in Pakistan.",
          "Amina Yilmaz", "France", "Pakistan", "Lyon", "REVIEW",
          "Raised in Pakistan means she lived there. The hit has no date of birth, so the shared country leaves it for review.",
          "DIFFERENT_ENTITY", "LOCATION_MISMATCH",
          "Does not read raised in, and clears France against Pakistan.",
          "notes_parse.py", True)
    lived("84", "National of Nigeria", "She is a national of Nigeria.",
          "Amina Zuniga", "France", "Nigeria", "Paris", "REVIEW",
          "The note states her nationality. Nigeria is a country tied to her. The hit gives no date of birth.",
          "DIFFERENT_ENTITY", "LOCATION_MISMATCH",
          "Only reads the residence field and clears France against Nigeria.",
          "notes_parse.py", True)
    lived("85", "Grew up in Ghana", "She grew up in Ghana before moving here.",
          "Amina Almeida", "France", "Ghana", "Lille", "REVIEW",
          "Grew up in Ghana is a place she lived. No date of birth on the hit.",
          "DIFFERENT_ENTITY", "LOCATION_MISMATCH",
          "Misses grew up in and clears.",
          "notes_parse.py", True)
    lived("86", "Moved from Pakistan to France", "She moved from Pakistan to France in 2010.",
          "Amina Bouchard", "France", "Pakistan", "Toulouse", "REVIEW",
          "Moved from Pakistan means she lived there, and the hit is linked to Pakistan. No date of birth on the hit.",
          "DIFFERENT_ENTITY", "LOCATION_MISMATCH",
          "Ignores the note and clears France against Pakistan.",
          "notes_parse.py", True)
    lived("87", "A sister lives in Pakistan", "Her sister lives in Pakistan.",
          "Amina Carvalho", "France", "Pakistan", "Nice", "DIFFERENT_ENTITY",
          "The sister lives in Pakistan. The note does not say the customer did. She is linked only to France, and the hit gives no date of birth.",
          "REVIEW", "INSUFFICIENT_DATA",
          "Treats every country in a note as the customer's and will not clear.",
          "notes_parse.py", False)
    lived("88", "A brother moved from Pakistan", "His brother moved from Pakistan in 2011.",
          "Amina Dragovic", "France", "Pakistan", "Bordeaux", "DIFFERENT_ENTITY",
          "The move is the brother's. The customer is linked only to France. The hit gives no date of birth, so the country difference clears it.",
          "REVIEW", "INSUFFICIENT_DATA",
          "Reads Pakistan off the relative's sentence and refuses to clear.",
          "notes_parse.py", False)
    lived("89", "Originally from Italy", "She is originally from Italy.",
          "Amina Elbaz", "France", "Italy", "Marseille", "REVIEW",
          "Originally from Italy ties Italy to her. The hit is Italy and has no date of birth.",
          "DIFFERENT_ENTITY", "LOCATION_MISMATCH",
          "Does not read originally from and clears France against Italy.",
          "notes_parse.py", True)

    def profile(tag, title, notes, name, dob, country, city, dobs, decision, codes, reason,
                weakness, naive_decision, naive_code, naive_note, module,
                ambiguous=False, ambiguous_note=None, evidence="kyc"):
        cid = b.customer(tag, name, dob, country, city)
        acc, app, kid = chain(b, tag, cid, name, dob, country)
        hid = b.hit(tag, "ADV-A-%s" % tag, name, dobs=dobs, countries=country, profile_notes=notes)
        b.alert(tag, name, [hid], dob=dob, country=country, city=city, account=acc)
        ev = [kid] if evidence == "kyc" else [cid, kid]
        steps = ["account_ref %s -> accounts -> customer %s" % (acc, cid),
                 "%s -> accounts %s -> onboarding %s -> latest approved check %s" % (cid, acc, app, kid)]
        b.lab(hid, "ADV-A-%s" % tag, decision, codes, [cid], ev, reason,
              path_join(steps, decision, codes, reason),
              "explicit_dob", weakness, naive_decision, naive_code, naive_note, cid, title,
              ambiguous, ambiguous_note, module)
        b.groups("ADV-A-%s" % tag, [[cid]])

    profile("90", "Born on in the profile",
            "Lina Fierro was born on 12 March 1975 in Madrid.",
            "Lina Fierro", "1975-03-12", "Spain", "Madrid", None,
            "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
            same_reason("1975-03-12", "ADV-KYC-90", "1975-03-12", "Spain", "Lina Fierro"),
            "The first paragraph states the birth date. There is no dobs field. Name and Spain agree.",
            "REVIEW", "INSUFFICIENT_DATA",
            "Only reads aged-N sentences, finds no date of birth, and sends it to review.",
            "hit.py")
    profile("91", "b. in the profile",
            "Lina Gauthier, b. 12 March 1976, Lyon.",
            "Lina Gauthier", "1976-03-12", "France", "Lyon", None,
            "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
            same_reason("1976-03-12", "ADV-KYC-91", "1976-03-12", "France", "Lina Gauthier"),
            "b. 12 March 1976 is her date of birth. Name and France agree.",
            "REVIEW", "INSUFFICIENT_DATA",
            "Does not read b. and leaves the hit for review.",
            "hit.py")
    profile("92", "DOB: sentence in the profile",
            "DOB: 5 June 1980.",
            "Lina Haddad", "1980-06-05", "France", "Paris", None,
            "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
            same_reason("1980-06-05", "ADV-KYC-92", "1980-06-05", "France", "Lina Haddad"),
            "The profile says DOB: 5 June 1980. That agrees with the approved check.",
            "REVIEW", "INSUFFICIENT_DATA",
            "Does not read a DOB: line.",
            "hit.py")
    profile("93", "Aged 45 in 2019",
            "She was aged 45 in 2019.",
            "Lina Iversen", "1974-02-02", "Sweden", "Stockholm", None,
            "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
            same_reason("1974-02-02", "ADV-KYC-93", "1973 or 1974", "Sweden", "Lina Iversen"),
            "Aged 45 in 2019 means born in 1973 or 1974. 1974 agrees. Name and Sweden agree.",
            "REVIEW", "INSUFFICIENT_DATA",
            "Ignores an age with a bare year.",
            "hit.py", evidence="both")
    profile("94", "The age is the father's",
            "His father, not the listed person, was aged 70 in March 2019. He keeps a low profile in Spain.",
            "Lina Jankovic", "1988-05-05", "Spain", "Madrid", None,
            "REVIEW", ["INSUFFICIENT_DATA"],
            review_nodob("Spain", "Lina Jankovic"),
            "The only age in the first paragraph is the father's, so the hit has no date of birth. Name and Spain agree.",
            "DIFFERENT_ENTITY", "DOB_MISMATCH",
            "Uses the father's age (1948 or 1949) and clears 1988.",
            "hit.py", True,
            "POLICY.md says an age in the first paragraph gives the hit's birth years. This sentence is about the father, which the text says. A mechanical reading of every age sentence would clear on 1948 or 1949. The label does not treat that age as the hit's.")
    profile("95", "Born on a contradicting date",
            "Lina Kaczmarek was born on 12 March 1960 in Warsaw.",
            "Lina Kaczmarek", "1988-05-05", "Poland", "Warsaw", None,
            "DIFFERENT_ENTITY", ["DOB_MISMATCH"],
            dob_reason("1988-05-05", "ADV-KYC-95", "the hit's profile notes put its birth date at 1960-03-12"),
            "The profile states a birth date and it contradicts the approved check. That clears.",
            "REVIEW", "INSUFFICIENT_DATA",
            "Does not read born on, so it cannot clear and leaves the hit for review.",
            "hit.py")
    profile("96", "Born on only in the second paragraph",
            "Lina Langlois sits on the city council in Lyon.\n\nShe was born on 12 March 1960.",
            "Lina Langlois", "1988-05-05", "France", "Lyon", None,
            "REVIEW", ["INSUFFICIENT_DATA"],
            review_nodob("France", "Lina Langlois"),
            "A date of birth in the second paragraph does not count. The first paragraph gives none. Name and France agree, so this is review, not a clear.",
            "DIFFERENT_ENTITY", "DOB_MISMATCH",
            "Reads born on anywhere in the notes and clears on 1960-03-12.",
            "hit.py")

    def search_case(tag, title, name, dob, country, city, category, phrase_title, snippet,
                    decision, reason, weakness, naive_decision, naive_code, naive_note,
                    cite_sr, dobs_origin_agrees):
        cid = b.customer(tag, name, dob, country, city)
        acc, app, kid = chain(b, tag, cid, name, dob, country)
        sid = b.sr(tag, qname(name), snippet, phrase_title)
        hid = b.hit(tag, "ADV-A-%s" % tag, name, countries=country,
                    primary_category=category, categories=category)
        b.alert(tag, name, [hid], dob=dob, country=country, city=city, account=acc)
        if decision == "SAME_ENTITY":
            codes = ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"]
            evidence = [cid, kid, sid]
        else:
            codes = ["INSUFFICIENT_DATA"]
            evidence = [cid, kid]
        steps = ["account_ref %s -> accounts -> customer %s" % (acc, cid)]
        if cite_sr:
            steps.append("search results for the hit's name -> %s (same role and country as the hit)" % sid)
        b.lab(hid, "ADV-A-%s" % tag, decision, codes, [cid], evidence, reason,
              path_join(steps, decision, codes, reason),
              "search_result", weakness, naive_decision, naive_code, naive_note, cid, title,
              module="hit.py")
        b.groups("ADV-A-%s" % tag, [[cid]])

    search_case(
        "97", "PEP phrase only in the title", "Pilar Mbeki", "1974-06-06", "Spain", "Madrid", "PEP",
        "Pilar Mbeki, a politically exposed person",
        "In March 2019, Spain noted Pilar Mbeki, who was 45 and sat on a council.",
        "SAME_ENTITY",
        same_reason("1974-06-06", "ADV-KYC-97", "1973 or 1974", "Spain", "Pilar Mbeki"),
        "The title says she is a politically exposed person. The snippet puts her in Spain, aged 45 in March 2019 (1973 or 1974).",
        "REVIEW", "INSUFFICIENT_DATA",
        "Requires the listing phrase in the snippet and then has no date of birth.",
        True, True)
    search_case(
        "98", "Sanctions phrase only in the title", "Bruno Nkrumah", "1974-07-07", "Spain", "Seville",
        "Sanctions",
        "Bruno Nkrumah, a sanctioned individual",
        "In March 2019, Spain noted Bruno Nkrumah, who was 45 and sat on a council.",
        "SAME_ENTITY",
        same_reason("1974-07-07", "ADV-KYC-98", "1973 or 1974", "Spain", "Bruno Nkrumah"),
        "The title says a sanctioned individual, which is this hit's category, and the snippet gives Spain and the age.",
        "REVIEW", "INSUFFICIENT_DATA",
        "Does not read the title, so the age is never used.",
        True, True)
    search_case(
        "99", "Country named only in the title", "Ines Okeke", "1974-08-08", "Spain", "Bilbao", "PEP",
        "Ines Okeke, a politically exposed person in Spain",
        "In March 2019, a council noted Ines Okeke, who was 45.",
        "SAME_ENTITY",
        same_reason("1974-08-08", "ADV-KYC-99", "1973 or 1974", "Spain", "Ines Okeke"),
        "The result's title has the listing phrase and Spain. The snippet has the age. Together they are about this hit.",
        "REVIEW", "INSUFFICIENT_DATA",
        "Looks only at the snippet, finds no listing phrase and no country, and drops the result.",
        True, True)
    search_case(
        "100", "Listing phrase in the snippet", "Rosa Petrovic", "1974-09-09", "Spain", "Valencia", "PEP",
        "Rosa Petrovic - report",
        "In March 2019, Spain described Rosa Petrovic as a politically exposed person who was 45 and sat on a council.",
        "SAME_ENTITY",
        same_reason("1974-09-09", "ADV-KYC-100", "1973 or 1974", "Spain", "Rosa Petrovic"),
        "The snippet itself has the listing phrase, Spain, and the age. 1974 agrees.",
        "REVIEW", "INSUFFICIENT_DATA",
        "Ignores search results and will not confirm.",
        True, True)
    search_case(
        "101", "Title phrase, country is not the hit's", "Hugo Qureshi", "1974-10-10", "Spain", "Madrid", "PEP",
        "Hugo Qureshi, a politically exposed person",
        "In March 1980, Brazil noted Hugo Qureshi, who was 40 and worked as a coach.",
        "REVIEW",
        review_nodob("Spain", "Hugo Qureshi"),
        "The title has the right phrase, but the snippet is Brazil and the hit is only Spain. That result is a namesake. The hit has no date of birth.",
        "DIFFERENT_ENTITY", "DOB_MISMATCH",
        "Trusts the title phrase, uses the Brazil age (1939 or 1940), and clears.",
        False, False)
    search_case(
        "102", "Wrong listing phrase in the title", "Nuria Radovan", "1974-11-11", "Spain", "Seville", "PEP",
        "Nuria Radovan, a sanctioned individual",
        "In March 1980, Spain noted Nuria Radovan, who was 40 and sat on a council.",
        "REVIEW",
        review_nodob("Spain", "Nuria Radovan"),
        "The hit is a PEP. Sanctioned individual is a different kind of listing, so this result is not about the hit. No date of birth is left.",
        "DIFFERENT_ENTITY", "DOB_MISMATCH",
        "Accepts any listing phrase, uses 1939 or 1940, and clears.",
        False, False)

    def death(tag, title, notes, name, dob, country, city, decision, codes, reason, weakness,
              naive_decision, naive_code, naive_note, ambiguous=False, ambiguous_note=None,
              screened_at="2026-11-15"):
        cid = b.customer(tag, name, dob, country, city)
        acc, app, kid = chain(b, tag, cid, name, dob, country)
        hid = b.hit(tag, "ADV-A-%s" % tag, name, dobs=dob, countries=country, profile_notes=notes)
        b.alert(tag, name, [hid], dob=dob, country=country, city=city, account=acc, screened_at=screened_at)
        evidence = [cid] if decision == "DIFFERENT_ENTITY" else [cid, kid]
        steps = ["account_ref %s -> accounts -> customer %s" % (acc, cid),
                 "profile notes give the death date"]
        b.lab(hid, "ADV-A-%s" % tag, decision, codes, [cid], evidence, reason,
              path_join(steps, decision, codes, reason),
              "deceased", weakness, naive_decision, naive_code, naive_note, cid, title,
              ambiguous, ambiguous_note, "hit.py")
        b.groups("ADV-A-%s" % tag, [[cid]])

    death_note = ("POLICY.md says the profile gives a date of death, and does not say it must be in deceased_date. "
                  "A reading that only the field counts would confirm, because the name and date of birth agree.")
    death("103", "Died on in the profile",
          "He died on 3 March 2018 in Madrid.",
          "Soren Szymanski", "1948-03-03", "Spain", "Madrid",
          "DIFFERENT_ENTITY", ["DECEASED"],
          "The hit's profile gives a date of death of 2018-03-03, before the customer was screened on 2026-11-15.",
          "The profile says he died on 3 March 2018, before screening. Name and date of birth would otherwise agree.",
          "SAME_ENTITY", "NAME_DOB_LOCATION_MATCH",
          "Reads only deceased_date and confirms.",
          True, death_note)
    death("104", "Passed away in the profile",
          "He passed away on 3 March 2018.",
          "Soren Tshabalala", "1949-04-04", "France", "Lyon",
          "DIFFERENT_ENTITY", ["DECEASED"],
          "The hit's profile gives a date of death of 2018-03-03, before the customer was screened on 2026-11-15.",
          "Passed away on 3 March 2018 is a date of death before screening.",
          "SAME_ENTITY", "NAME_DOB_LOCATION_MATCH",
          "Does not treat passed away as a death date and confirms.",
          True, death_note)
    death("105", "Date of death line",
          "Date of death: 2018-03-03.",
          "Soren Umeh", "1950-05-05", "Nigeria", "Lagos",
          "DIFFERENT_ENTITY", ["DECEASED"],
          "The hit's profile gives a date of death of 2018-03-03, before the customer was screened on 2026-11-15.",
          "The line is a date of death, and it is before screening.",
          "SAME_ENTITY", "NAME_DOB_LOCATION_MATCH",
          "Ignores a date-of-death line that is not the deceased_date field.",
          True, death_note)
    death("106", "Death in the notes is after screening",
          "He died on 1 December 2026.",
          "Soren Vandenberg", "1951-06-06", "Belgium", "Brussels",
          "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
          same_reason("1951-06-06", "ADV-KYC-106", "1951-06-06", "Belgium", "Soren Vandenberg"),
          "1 December 2026 is after screening on 15 November 2026. A later death does not clear. Name and date of birth agree.",
          "DIFFERENT_ENTITY", "DECEASED",
          "Any death sentence clears, including one after the screening date.")
    death("107", "The father died, not the subject",
          "His father died on 3 March 2018. The listed person is alive.",
          "Soren Wozniak", "1952-07-07", "Poland", "Warsaw",
          "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
          same_reason("1952-07-07", "ADV-KYC-107", "1952-07-07", "Poland", "Soren Wozniak"),
          "The death date is the father's. The profile does not give a date of death for the listed person. Name and date of birth agree.",
          "DIFFERENT_ENTITY", "DECEASED",
          "Clears on any died-on date in the notes.")
    death("108", "Died on the screening date, in prose",
          "He died on 15 November 2026.",
          "Soren Yoshida", "1953-08-08", "Japan", "Tokyo",
          "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
          same_reason("1953-08-08", "ADV-KYC-108", "1953-08-08", "Japan", "Soren Yoshida"),
          "Death on the screening date is not before it, whether or not the sentence is read. Name and date of birth agree.",
          "DIFFERENT_ENTITY", "DECEASED",
          "Clears when the death date is on or before the screening date.")
