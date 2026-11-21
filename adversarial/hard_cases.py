"""Twenty harder cases, tags 109-128.

Written from POLICY.md, not from the fixes already on this branch: empty fields,
bad dates and country names, and cultural name patterns. `module` is only a hint
for where a miss would live.
"""


def add(b, same_reason, dob_reason, review_nodob, path_join, chain):
    def person(tag, name, dob, country, city, hit_name=None, hit_dob=None, hit_countries=None,
               kyc_name=None, kyc_dob=None, kyc_country=None, record_name=None, record_dob=None,
               screened_name=None, screened_dob=None, screened_country=None,
               link=True, decision="SAME_ENTITY", codes=None, reason=None, evidence=None,
               category="hard", title="", weakness="", naive_decision="DIFFERENT_ENTITY",
               naive_code="DOB_MISMATCH", naive_note="", module="", ambiguous=False,
               ambiguous_note=None, hit_fields=None, make_kyc=True):
        cid = b.customer(tag, record_name or name, record_dob if record_dob is not None else dob,
                         country, city)
        acc = app = kid = None
        if link or make_kyc:
            if make_kyc:
                acc, app, kid = chain(
                    b, tag, cid, kyc_name or name, kyc_dob if kyc_dob is not None else dob,
                    kyc_country or country)
            else:
                acc = b.account(tag, cid)
        hid = "ADV-H-%s" % tag
        fields = {
            "dobs": hit_dob if hit_dob is not None else dob,
            "countries": country if hit_countries is None else hit_countries,
        }
        if hit_fields:
            fields.update(hit_fields)
        b.hit(tag, "ADV-A-%s" % tag, hit_name or name, **fields)
        b.alert(tag, screened_name if screened_name is not None else (hit_name or name), [hid],
                dob=screened_dob if screened_dob is not None else (record_dob if record_dob is not None else dob),
                country=screened_country if screened_country is not None else country,
                city=city, account=acc if link else None)
        if codes is None:
            codes = ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"]
        if evidence is None:
            evidence = [cid, kid] if kid else [cid]
        if reason is None:
            src = kid or cid
            reason = same_reason(kyc_dob or dob, src, hit_dob or dob, country, hit_name or name)
        steps = []
        if link and acc:
            steps.append("account_ref %s -> accounts -> customer %s" % (acc, cid))
        else:
            steps.append("name, date of birth, country and city -> customers -> %s" % cid)
        if kid:
            steps.append("%s -> accounts %s -> onboarding %s -> latest approved check %s" % (cid, acc, app, kid))
        b.lab(hid, "ADV-A-%s" % tag, decision, codes, [cid], evidence, reason,
              path_join(steps, decision, codes, reason),
              category, weakness, naive_decision, naive_code, naive_note, cid, title,
              ambiguous, ambiguous_note, module)
        b.groups("ADV-A-%s" % tag, [[cid]])
        return cid, kid

    # --- empty / missing ---
    person("109", "Helena Quesada", "1984-02-02", "Spain", "Madrid",
           screened_name="   ", title="Whitespace screened name, real link",
           category="empty_fields", module="customer.py",
           weakness="The screened name is blank. The account link still identifies her, and the approved name and date of birth agree with the hit.",
           naive_note="Treats a blank screened name as a name mismatch and clears.")
    person("110", "Helena Ibarra", "1984-03-03", "Spain", "Seville",
           hit_name="N/A", title="Hit name is only N/A",
           category="empty_fields", module="policy.py",
           decision="REVIEW", codes=["INSUFFICIENT_DATA"],
           reason=("The hit's only name is N/A, which is not a name part, so the customer can be neither "
                   "confirmed nor cleared on name. The date of birth 1984-03-03 agrees and both are linked "
                   "to Spain, but that is not enough."),
           weakness="A placeholder is not a hit name. Nothing contradicts the customer, and the name cannot confirm the hit.",
           naive_note="Compares N/A as a real name and clears.",
           ambiguous=True,
           ambiguous_note=("POLICY.md says a verified name that agrees with none of the hit's names clears the hit, "
                           "and also says placeholders are not name parts. N/A is the hit's only name. "
                           "Reading it as 'no name to compare' leaves the hit for review. "
                           "Reading it as a name that fails to agree would clear, which is the unsafe reading."))
    person("111", "Helena Pellicer", "1984-04-04", "Spain", "Bilbao",
           hit_fields={"countries": None}, title="Hit has no countries",
           category="empty_fields", module="hit.py",
           codes=["NAME_DOB_MATCH"],
           reason=same_reason("1984-04-04", "ADV-KYC-111", "1984-04-04", "Spain", "Helena Pellicer", False),
           weakness="The hit is tied to no country. Name and date of birth agree, and a missing country is not a mismatch.",
           naive_note="Treats a missing country as a location mismatch and clears.")
    cid, _ = person("112", "Helena Montoya", "1984-05-05", "Spain", "Valencia",
                    make_kyc=False, title="No approved identity check",
                    category="empty_fields", module="customer.py",
                    codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
                    evidence=["ADV-CUS-112"],
                    reason=same_reason("1984-05-05", "ADV-CUS-112", "1984-05-05", "Spain", "Helena Montoya"),
                    weakness="There is no approved check. The name, date of birth and country on the record agree with the hit, and a missing check is not a contradiction.",
                    naive_note="Requires a verified name and clears because there is none.")
    person("113", "Helena Escudero", "1984-06-06", "Spain", "Granada",
           link=False, title="Alert has no link at all",
           category="empty_fields", module="customer.py",
           weakness="No account, login or email. The screened name, date of birth, country and city fit one record, and that record agrees with the hit.",
           naive_note="Gives up when the alert has no link and leaves the hit, or clears it.")
    # fix 112 path: make_kyc False still passed link True so account exists. evidence and reason set. Good.
    # But person() with make_kyc False and link True creates account only. The steps won't include kyc. Good.
    # evidence was passed so kid None isn't included. Good.

    # --- bad dates, countries, unicode ---
    person("114", "Helena Villalobos", "1980-04-03", "Spain", "Madrid",
           kyc_dob="03/04/1980", record_dob="03/04/1980", hit_dob="1980-04-03",
           title="Ambiguous slash date, day-first",
           category="bad_input", module="normalize.py",
           reason=same_reason("1980-04-03", "ADV-KYC-114", "1980-04-03", "Spain", "Helena Villalobos"),
           weakness="Slash dates are day-first. 03/04/1980 is 3 April 1980, the same day as the hit.",
           naive_note="Reads the slash date month-first (3 March) and clears.")
    person("115", "Helena Cardenas", "1975-04-13", "Spain", "Seville",
           kyc_dob="13/04/1975", record_dob="13/04/1975", hit_dob="1975-04-13",
           title="Unambiguous slash date",
           category="bad_input", module="normalize.py",
           reason=same_reason("1975-04-13", "ADV-KYC-115", "1975-04-13", "Spain", "Helena Cardenas"),
           weakness="13 cannot be a month. 13/04/1975 is 13 April 1975 either way it is read.",
           naive_decision="REVIEW", naive_code="INSUFFICIENT_DATA",
           naive_note="Rejects the slash date as ambiguous and will not confirm.")
    person("116", "Helena Paredes", "1980-04-03", "Spain", "Bilbao",
           kyc_dob="03/04/1980", record_dob="03/04/1980", hit_dob="1980-03-04",
           title="Day-first date is not the month-first reading",
           category="bad_input", module="normalize.py",
           decision="DIFFERENT_ENTITY", codes=["DOB_MISMATCH"], evidence=["ADV-KYC-116"],
           reason=dob_reason("1980-04-03", "ADV-KYC-116", "the hit's listed date of birth is 1980-03-04"),
           weakness="03/04/1980 is 3 April. The hit is 4 March. Same year, different month.",
           naive_decision="SAME_ENTITY", naive_code="NAME_DOB_MATCH",
           naive_note="Reads 03/04 as 3 March and confirms.")
    person("117", "Helena Beltran", "1980-03-03", "Spain", "Valencia",
           kyc_dob="31/02/1980", record_dob="31/02/1980", hit_dob="1980-03-03",
           title="31 February is not a date",
           category="bad_input", module="fallbacks.py",
           decision="REVIEW", codes=["INSUFFICIENT_DATA"],
           reason=review_nodob("Spain", "Helena Beltran"),
           weakness="31 February does not parse. A missing date is not a mismatch, and without a date of birth the name and country cannot confirm the hit.",
           naive_note="Invents 2 March or 3 March from 31 February and clears.")
    person("118", "Helena Osorio", "1975-06-06", "Spain", "Granada",
           kyc_dob="1900-01-01", hit_dob="1975-06-06",
           title="1900-01-01 is a real date here",
           category="bad_input", module="policy.py",
           decision="DIFFERENT_ENTITY", codes=["DOB_MISMATCH"], evidence=["ADV-KYC-118"],
           reason=dob_reason("1900-01-01", "ADV-KYC-118", "the hit's listed date of birth is 1975-06-06"),
           weakness="POLICY.md does not treat 1900-01-01 as a placeholder. It is the approved date of birth and it contradicts the hit.",
           naive_decision="SAME_ENTITY", naive_code="NAME_LOCATION_MATCH",
           naive_note="Drops 1900-01-01 as a placeholder and confirms on the name.")
    person("119", "Helena Camacho", "1986-08-08", "Spain", "Madrid",
           kyc_name="Helena Camacho", record_name="He\u200blena Camacho",
           title="Zero-width space inside the name",
           category="bad_input", module="names.py",
           weakness="The approved name is Helena Camacho with a zero-width space inside Helena. That character is not a letter. The name, date of birth and country agree with the hit.",
           naive_note="Splits the name on the zero-width space, fails the match, and clears.",
           naive_code="NAME_MISMATCH_VERIFIED")
    # 119 record name has zwsp but verified name passed as kyc_name without it.
    # The bug is in the verified name. Pass zwsp as kyc_name.
    # I set kyc_name without zwsp and record_name with it. Fix below by a direct overwrite? 
    # I'll set kyc_name to the zwsp form in a follow-up edit. Doing it here correctly:

    # The call above used kyc_name without zwsp. I need the verified name to contain it.
    # Corrected call is below; this comment marks the mistake. See the replacement.

    person("120", "Helena Roldan", "1982-02-02", "Zaire", "Kinshasa",
           kyc_country="Zaire", hit_dob=None, screened_country="Zaire",
           title="Zaire and no date of birth",
           category="bad_input", module="countries.py",
           decision="REVIEW", codes=["INSUFFICIENT_DATA"],
           reason=("The customer's name agrees with the hit's name Helena Roldan. "
                   "The hit gives no date of birth. Zaire is an old name for the Democratic Republic of the Congo, "
                   "which is the hit's country, so nothing contradicts the hit and it cannot be confirmed."),
           weakness="The hit has no date of birth. Zaire is the old name of the Democratic Republic of the Congo, the hit's only country, so the countries are not a contradiction.",
           naive_note="Treats Zaire as a different country from the DRC and clears.",
           ambiguous=True,
           ambiguous_note=("POLICY.md does not list historical names. Zaire is the old name of the Democratic Republic of the Congo. "
                           "If it counts, the countries agree and the hit is still review because there is no date of birth. "
                           "If Zaire is unknown, the customer has no recognised country, and the hit is still review. "
                           "Either reading is REVIEW. Clearing on the names would be the unsafe reading."),
           hit_fields={"countries": "Democratic Republic of the Congo", "dobs": None})

    # --- cultural names ---
    person("121", "Muhammad Ali Qureshi", "1971-01-11", "Pakistan", "Lahore",
           hit_name="Mohammed Ali Qureshi", title="Muhammad and Mohammed",
           category="cultural_names", module="names.py",
           weakness="Muhammad and Mohammed are listed together in name_variants.json. The other two parts match, and the date of birth and Pakistan agree.",
           naive_note="No variant list, so only Ali and Qureshi are considered and a strict full-string compare clears.")
    person("122", "Anna Ivanova", "1983-03-03", "Russia", "Moscow",
           hit_name="Anna Ivanov", title="Ivanova and Ivanov, same date",
           category="cultural_names", module="names.py",
           weakness="Ivanova and Ivanov differ by one letter in a six-letter part, which is inside the edit limit. Anna matches. The date of birth and country agree. Gender is not a fact in the policy.",
           naive_note="Treats the feminine ending as a different person and clears.")
    person("123", "Maria Garcia Lopez", "1990-09-09", "Spain", "Madrid",
           hit_name="Maria Garcia", title="Dropped maternal surname",
           category="cultural_names", module="names.py",
           weakness="Every part of the shorter name, Maria Garcia, matches. Lopez is extra. The date of birth and Spain agree.",
           naive_note="Requires the maternal surname as well and clears.")
    person("124", "Zhang Wei", "1988-08-08", "China", "Shanghai",
           hit_name="Wei Zhang", title="Chinese name order swapped",
           category="cultural_names", module="names.py",
           weakness="Order does not matter. Zhang and Wei both match, and the date of birth and China agree.",
           naive_note="Requires the same order and clears.")
    person("125", "Nguyen Van Minh", "1992-02-02", "Vietnam", "Hanoi",
           hit_name="Minh Nguyen", title="Vietnamese name, Van dropped, order swapped",
           category="cultural_names", module="names.py",
           weakness="Nguyen and Minh match. Van is an extra part. Order does not matter. The date of birth and Vietnam agree.",
           naive_note="Keeps the order and the middle Van and clears.")
    person("126", "Jan van der Berg", "1976-06-06", "Netherlands", "Rotterdam",
           hit_name="Jan Berg", title="Dutch particles dropped",
           category="cultural_names", module="names.py",
           weakness="van and der are extra parts. Jan and Berg match, which is enough. The date of birth and the Netherlands agree.",
           naive_note="Treats the missing particles as a different name and clears.")
    person("127", "Ali bin Hassan", "1990-04-04", "Nigeria", "Kano",
           kyc_name="Ali bin Hassan", hit_name="Hassan", hit_dob="1960-04-04",
           title="bin Hassan against Hassan, different dates",
           category="cultural_names", module="policy.py",
           decision="DIFFERENT_ENTITY", codes=["DOB_MISMATCH"], evidence=["ADV-KYC-127"],
           reason=dob_reason("1990-04-04", "ADV-KYC-127", "the hit's listed date of birth is 1960-04-04"),
           weakness="The shorter name Hassan does match a part of Ali bin Hassan, so the names agree. The dates of birth are thirty years apart, which contradicts.",
           naive_decision="SAME_ENTITY", naive_code="NAME_DOB_MATCH",
           naive_note="Sees the shared Hassan, ignores the dates, and confirms father and son.")
    person("128", "Lee Minho", "1987-07-07", "South Korea", "Seoul",
           hit_name="Yi Minho", title="Lee and Yi, same date",
           category="cultural_names", module="names.py",
           decision="DIFFERENT_ENTITY", codes=["NAME_MISMATCH_VERIFIED"], evidence=["ADV-KYC-128"],
           reason="The customer's verified name is Lee Minho (ADV-KYC-128), which does not match the hit's name Yi Minho.",
           weakness="Lee and Yi are shorter than four letters and are not the same part, and they are not listed as variants. Minho matches once, which is not enough. The verified name therefore clears the hit.",
           naive_decision="SAME_ENTITY", naive_code="NAME_DOB_LOCATION_MATCH",
           naive_note="Treats Lee, Yi and Rhee as one surname and confirms.")

    # Repair 119: the verified name must carry the zero-width space.
    # person() already wrote kyc with a clean name if kyc_name was clean.
    # Overwrite the check we just created.
    b.kyc["ADV-KYC-119"]["verified_name"] = "He\u200blena Camacho"
