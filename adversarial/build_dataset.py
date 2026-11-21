#!/usr/bin/env python3
"""Write the adversarial dataset under adversarial/.

The JSONL files are what the runner scores. This script rebuilds them and checks
that customer resolution sees the people each case intends. Gold answers follow
dev/POLICY.md; they are not fitted to the pipeline.

    python3 adversarial/build_dataset.py
"""
import json
import os
import re
import shutil
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "adversarial")
sys.path.insert(0, os.path.join(ROOT, "system"))

SCREENED = "2026-11-15"


def qname(name):
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return " ".join(sorted(w for w in re.findall(r"[a-z]+", text) if len(w) > 1))


def phone_for(tag):
    digits = int("".join(ch for ch in tag if ch.isdigit()) or "0")
    extra = sum(ord(ch) for ch in tag if ch.isalpha())
    return "+1 202%04d%03d" % (digits, extra)


def email_for(tag, name):
    slug = re.sub(r"[^a-z]", "", name.lower())[:20] or "customer"
    return "%s.%s@mailbox.example" % (slug, tag.lower())


def dump(name, rows, key):
    rows = sorted(rows, key=lambda r: r[key])
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


class Bank:
    def __init__(self):
        self.customers, self.accounts, self.onboarding = {}, {}, []
        self.kyc, self.notes, self.hits, self.alerts = {}, {}, {}, {}
        self.search, self.labels = {}, {}
        self.expect = {}

    def customer(self, tag, name, dob, country, city, phone=None, email=None,
                 nationality=None, residence=None, address=None, entity="Individual",
                 preferred=None):
        cid = "ADV-CUS-%s" % tag
        if cid in self.customers:
            raise SystemExit("duplicate customer " + cid)
        self.customers[cid] = {
            "record_id": cid,
            "entity_type": entity,
            "full_name": name,
            "preferred_name": preferred,
            "login_name": None,
            "dob": dob,
            "nationality": nationality if nationality is not None else country,
            "residence_country": residence if residence is not None else country,
            "city": city,
            "address": address or ("10 High Street, %s" % city),
            "email": email or email_for(tag, name),
            "phone": phone or phone_for(tag),
            "occupation": None if entity == "Company" else "Analyst",
            "employer": None if entity == "Company" else "Northwind",
            "registration_number": ("REG-%s" % tag) if entity == "Company" else None,
            "onboarded_at": "2021-04-01",
            "status": "active",
            "last_kyc_refresh": "2024-06-01",
        }
        return cid

    def account(self, tag, cid, phone=None, login=None):
        aid = "ADV-ACC-%s" % tag
        self.accounts[aid + "|" + cid] = {
            "account_id": aid,
            "customer_id": cid,
            "login_handle": login or ("adv%s" % tag.lower()),
            "phone": phone if phone is not None else self.customers[cid]["phone"],
            "opened_at": "2021-04-01",
            "status": "active",
        }
        return aid

    def onboard(self, tag, acc, cid):
        app = "ADV-APP-%s" % tag
        self.onboarding.append({
            "account_id": acc,
            "customer_id": cid,
            "kyc_applicant_id": app,
            "onboarded_at": "2021-04-01",
        })
        return app

    def kyc_check(self, tag, app, name, dob, country, result="approved",
                  checked_at="2024-03-15", doc=None, provider=None, doc_type=None):
        kid = "ADV-KYC-%s" % tag
        if kid in self.kyc:
            raise SystemExit("duplicate kyc " + kid)
        company = doc_type == "certificate of incorporation"
        self.kyc[kid] = {
            "check_id": kid,
            "applicant_id": app,
            "provider": provider or ("Companies registry lookup" if company else "Persona"),
            "verified_name": name,
            "verified_dob": dob,
            "document_type": doc_type or ("certificate of incorporation" if company else "passport"),
            "document_number": doc if doc is not None else ("DOC%s" % tag),
            "document_country": country,
            "result": result,
            "checked_at": checked_at,
        }
        return kid

    def note(self, tag, email, text, channel, created_at="2024-06-01"):
        nid = "ADV-NOTE-%s" % tag
        self.notes[nid] = {
            "note_id": nid,
            "requester_email": email,
            "created_at": created_at,
            "channel": channel,
            "text": text,
        }
        return nid

    def hit(self, tag, alert, name, **fields):
        hid = "ADV-H-%s" % tag
        row = {
            "hit_id": hid,
            "alert_id": alert,
            "match_score": 91.0,
            "entity_type": "Individual",
            "name": name,
            "aliases": None,
            "gender": None,
            "dobs": None,
            "place_of_birth": None,
            "life_status": None,
            "deceased_date": None,
            "nationality": None,
            "citizenship": None,
            "countries": None,
            "addresses": None,
            "identifiers": None,
            "categories": "PEP",
            "primary_category": "PEP",
            "position_or_allegation": None,
            "details": None,
            "relationships": None,
            "profile_notes": None,
            "sources": None,
            "source_urls": None,
        }
        row.update(fields)
        self.hits[hid] = row
        return hid

    def alert(self, tag, name, hit_ids, dob=None, country=None, city=None,
              account=None, login=None, email=None, entity="Individual",
              screened_at=SCREENED):
        aid = "ADV-A-%s" % tag
        self.alerts[aid] = {
            "alert_id": aid,
            "screened_at": screened_at,
            "customer_name": name,
            "entity_type": entity,
            "dob": dob,
            "country": country,
            "city": city,
            "account_ref": account,
            "login_handle": login,
            "email": email,
            "hit_count": len(hit_ids),
            "hit_ids": "; ".join(hit_ids),
        }
        return aid

    def sr(self, tag, query, snippet, title):
        sid = "ADV-SR-%s" % tag
        self.search[sid] = {
            "result_id": sid,
            "query": query,
            "title": title,
            "snippet": snippet,
            "source": "registry-news.example",
        }
        return sid

    def lab(self, hit, alert, decision, codes, customers, evidence, reason, path,
            category, weakness, naive_decision, naive_code, naive_note,
            naive_customer=None, title="", ambiguous=False, ambiguous_note=None,
            module=""):
        if isinstance(customers, list):
            cust = "; ".join(customers)
        else:
            cust = customers
        self.labels[hit] = {
            "hit_id": hit,
            "alert_id": alert,
            "decision": decision,
            "reason_codes": "; ".join(codes),
            "customer_record_ids": cust,
            "evidence": "; ".join(sorted(evidence)),
            "reference_reason": reason,
            "path": path,
            "title": title,
            "category": category,
            "weakness": weakness,
            "naive_decision": naive_decision,
            "naive_reason_code": naive_code,
            "naive_customer_record_id": naive_customer,
            "naive_note": naive_note,
            "ambiguous_policy": ambiguous,
            "ambiguous_policy_note": ambiguous_note,
            "module": module,
        }

    def groups(self, alert, groups):
        self.expect[alert] = tuple(sorted(tuple(sorted(g)) for g in groups))


def chain(b, tag, cid, name, dob, country, result="approved", checked_at="2024-03-15",
          doc=None, provider=None, doc_type=None, acc_phone=None):
    acc = b.account(tag, cid, phone=acc_phone)
    app = b.onboard(tag, acc, cid)
    kid = b.kyc_check(tag, app, name, dob, country, result, checked_at, doc, provider, doc_type)
    return acc, app, kid


def same_reason(dob, src, hit_dob, country, hit_name, country_too=True):
    text = "The customer's date of birth %s (%s) agrees with the hit's %s." % (dob, src, hit_dob)
    if country_too:
        text += " Both the customer and the hit are linked to %s." % country
    text += " The customer's name agrees with the hit's name %s." % hit_name
    return text


def dob_reason(dob, src, what):
    return "The customer's date of birth is %s (%s) but %s." % (dob, src, what)


def review_nodob(country, hit_name):
    return (
        "Both the customer and the hit are linked to %s. "
        "The customer's name agrees with the hit's name %s. "
        "Nothing in the customer's records contradicts the hit, and the date of birth "
        "cannot be compared with it, so the hit can be neither cleared nor confirmed."
    ) % (country, hit_name)


def path_join(steps, decision, codes, reason):
    shown = "[" + ", ".join("'%s'" % c for c in codes) + "]"
    return " → ".join(steps + ["%s %s: %s" % (decision, shown, reason)])


def link_path(link, acc, login, email, cid):
    if link == "login":
        return "login_handle %s -> accounts %s -> customer %s" % (login, acc, cid)
    if link == "email":
        return "email %s -> customers -> %s" % (email, cid)
    return "account_ref %s -> accounts -> customer %s" % (acc, cid)


def simple(b, spec):
    """One linked person, one approved check, one hit."""
    tag = spec["tag"]
    name = spec["name"]
    dob = spec.get("record_dob", spec["dob"])
    country = spec["country"]
    city = spec["city"]
    entity = spec.get("entity", "Individual")
    cid = b.customer(
        tag, spec.get("record_name", name), dob, country, city,
        nationality=spec.get("nationality"), residence=spec.get("residence"),
        address=spec.get("address"), entity=entity,
    )
    kyc_name = spec.get("kyc_name", name)
    kyc_dob = spec.get("kyc_dob", spec["dob"])
    kyc_country = spec.get("kyc_country", spec.get("residence", country))
    doc_type = "certificate of incorporation" if entity == "Company" else None
    acc, app, kid = chain(
        b, tag, cid, kyc_name, kyc_dob, kyc_country, doc_type=doc_type,
        checked_at=spec.get("checked_at", "2024-03-15"),
    )
    for extra in spec.get("extra_kyc", ()):
        b.kyc_check(
            extra["tag"], app, extra.get("name", kyc_name), extra["dob"],
            extra.get("country", kyc_country), extra.get("result", "approved"),
            extra.get("checked_at", "2025-09-01"), extra.get("doc"),
            doc_type=doc_type,
        )
    rec = b.customers[cid]
    link = spec.get("link", "account")
    login = b.accounts[acc + "|" + cid]["login_handle"]
    alert_account = acc if link == "account" else None
    alert_login = login if link == "login" else None
    alert_email = rec["email"] if link == "email" else None
    hid = "ADV-H-%s" % tag
    aid = "ADV-A-%s" % tag
    hit_name = spec.get("hit_name", name)
    hit_fields = {
        "entity_type": spec.get("hit_entity", entity),
        "dobs": spec.get("dobs", spec.get("hit_dob", spec["dob"])),
        "countries": spec.get("hit_countries", country),
        "aliases": spec.get("aliases"),
        "profile_notes": spec.get("profile_notes"),
        "deceased_date": spec.get("deceased_date"),
        "life_status": spec.get("life_status"),
        "citizenship": spec.get("citizenship"),
        "addresses": spec.get("addresses"),
        "primary_category": spec.get("primary_category", "SOE" if entity == "Company" else "PEP"),
        "categories": spec.get("categories", "SOE" if entity == "Company" else "PEP"),
    }
    b.hit(tag, aid, hit_name, **hit_fields)
    b.alert(
        tag, spec.get("screened_name", name), [hid],
        dob=spec.get("screened_dob", dob), country=spec.get("screened_country", country),
        city=city, account=alert_account, login=alert_login, email=alert_email,
        entity=entity, screened_at=spec.get("screened_at", SCREENED),
    )
    if spec.get("note"):
        b.note(tag, rec["email"], spec["note"], spec.get("note_channel", "phone"))
    codes = spec["codes"]
    reason = spec["reason"]
    evidence = []
    for token in spec["evidence"]:
        evidence.append({
            "CUS": cid, "KYC": kid, "NOTE": "ADV-NOTE-%s" % tag, "SR": "ADV-SR-%s" % tag,
        }.get(token, token))
    steps = [link_path(link, acc, login, rec["email"], cid)]
    if spec.get("note"):
        steps.append("customer email -> notes -> ADV-NOTE-%s" % tag)
    if kid and spec.get("cite_kyc_path", True):
        steps.append("%s -> accounts %s -> onboarding %s -> latest approved check %s" % (cid, acc, app, kid))
    b.lab(
        hid, aid, spec["decision"], codes, spec.get("customers", [cid]), evidence, reason,
        path_join(steps, spec["decision"], codes, reason),
        spec["category"], spec["weakness"], spec["naive_decision"], spec["naive_code"],
        spec["naive_note"], spec.get("naive_customer", cid), spec.get("title", ""),
        spec.get("ambiguous", False), spec.get("ambiguous_note"),
    )
    b.groups(aid, spec.get("expect", [[cid]]))


def build(b):
    # --- 01 family share phone, address and surname: do not merge ---
    son = b.customer("01", "Owen Hartley", "1995-04-04", "United Kingdom", "Leeds",
                     phone="+44 7700900101", address="14 Bridge Road, Leeds")
    father = b.customer("01B", "Graham Hartley", "1968-04-04", "United Kingdom", "Leeds",
                        phone="+44 7700900101", address="14 Bridge Road, Leeds")
    acc, app, kid = chain(b, "01", son, "Owen Hartley", "1995-04-04", "United Kingdom",
                          checked_at="2022-01-01")
    chain(b, "01B", father, "Graham Hartley", "1968-04-04", "United Kingdom",
          checked_at="2025-06-01")
    hid = b.hit("01", "ADV-A-01", "Owen Hartley", dobs="1995-04-04", countries="United Kingdom")
    b.alert("01", "Owen Hartley", [hid], dob="1995-04-04", country="United Kingdom",
            city="Leeds", account=acc)
    reason = same_reason("1995-04-04", kid, "1995-04-04", "United Kingdom", "Owen Hartley")
    b.lab(hid, "ADV-A-01", "SAME_ENTITY",
          ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], [son], [son, kid], reason,
          path_join([
              "account_ref %s -> accounts -> customer %s" % (acc, son),
              "%s -> accounts %s -> onboarding %s -> latest approved check %s" % (son, acc, app, kid),
          ], "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], reason),
          "family", "Shared phone, address and surname are not the same person.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "A phone-or-address merge pulls in the father's newer approved check (born 1968-04-04) and clears the son.",
          son, "Family share a phone and address")
    b.groups("ADV-A-01", [[son]])

    # --- 02 joint account, shorter name fits the father too; decisions differ ---
    hans = b.customer("02", "Hans Peter Meier", "1960-03-01", "Germany", "Hamburg",
                      phone="+49 1510000002", address="2 Hafenstrasse, Hamburg")
    peter = b.customer("02B", "Peter Meier", "1960-11-11", "Germany", "Hamburg",
                       phone="+49 1510000002", address="2 Hafenstrasse, Hamburg")
    b.account("02", hans)
    b.account("02", peter, login="adv02")
    app_h = b.onboard("02", "ADV-ACC-02", hans)
    app_p = b.onboard("02B", "ADV-ACC-02", peter)
    kyc_h = b.kyc_check("02", app_h, "Hans Peter Meier", "1960-03-01", "Germany")
    kyc_p = b.kyc_check("02B", app_p, "Peter Meier", "1960-11-11", "Germany")
    hid = b.hit("02", "ADV-A-02", "Peter Meier", dobs="1960-11-11", countries="Germany")
    b.alert("02", "Peter Meier", [hid], dob="1960", country="Germany", city="Hamburg",
            account="ADV-ACC-02")
    reason = ("2 different people fit the screened name and year (ADV-CUS-02, ADV-CUS-02B) "
              "and they lead to different decisions, so the hit needs review.")
    b.lab(hid, "ADV-A-02", "REVIEW", ["AMBIGUOUS_CUSTOMER_RECORD"], "AMBIGUOUS",
          [hans, peter, kyc_h, kyc_p], reason,
          path_join([
              "account_ref ADV-ACC-02 -> accounts: joint holders ADV-CUS-02 and ADV-CUS-02B -> "
              "the screened name and date of birth fit ADV-CUS-02, ADV-CUS-02B",
              "2 different people fit (records ADV-CUS-02, ADV-CUS-02B); each is decided separately",
          ], "REVIEW", ["AMBIGUOUS_CUSTOMER_RECORD"], reason),
          "ambiguous_customer",
          "Every part of the shorter name matches, so the father fits too. Same phone is not a merge: the full dates of birth differ.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Picks the father (first record) and clears on March versus November.",
          "ADV-CUS-02", "Shorter name pulls in a relative")
    b.groups("ADV-A-02", [[hans], [peter]])

    # --- 03 same phone number written with 00, same full DOB: must merge ---
    bad = b.customer("03", "Marcus Hale", "1992-04-04", "Germany", "Munich",
                     phone="+49 15123456789")
    good = b.customer("03B", "Bobby Nguyen", "1992-04-04", "Germany", "Munich",
                      phone="004915123456789")
    acc, app, kid_bad = chain(b, "03", bad, "Marcus Hale", "1970-05-05", "Germany",
                              checked_at="2019-01-01")
    chain(b, "03B", good, "Bobby Nguyen", "1992-04-04", "Germany", checked_at="2024-08-01")
    hid = b.hit("03", "ADV-A-03", "Robert Nguyen", dobs="1992-04-04", countries="Germany")
    b.alert("03", "Robert Nguyen", [hid], dob="1992-04-04", country="Germany",
            city="Munich", account=acc)
    kid_good = "ADV-KYC-03B"
    reason = same_reason("1992-04-04", kid_good, "1992-04-04", "Germany", "Robert Nguyen")
    b.lab(hid, "ADV-A-03", "SAME_ENTITY",
          ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], [bad, good],
          [bad, good, kid_good], reason,
          path_join([
              "account_ref %s -> accounts -> customer %s" % (acc, bad),
              "same phone and date of birth -> one person: ADV-CUS-03, ADV-CUS-03B",
              "latest approved check ADV-KYC-03B",
          ], "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], reason),
          "phone_dob_merge",
          "The two records are the same phone number (+49 versus the 00 international prefix) and the same full date of birth. The newest approved check is Bobby Nguyen, which agrees with Robert Nguyen.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Does not join the 00-prefix number, keeps Marcus Hale's 1970-05-05 check, and clears.",
          bad, "Same phone written with 00")
    b.groups("ADV-A-03", [[bad]])

    # --- 04 same document number, spacing differs: must merge ---
    left = b.customer("04", "Helen Kruger", "1972-02-02", "Spain", "Madrid")
    right = b.customer("04B", "Ines Navarro", "1991-03-03", "Spain", "Madrid")
    acc, app, kid_l = chain(b, "04", left, "Helen Kruger", "1972-02-02", "Spain",
                            checked_at="2018-04-01", doc="LQ 448219")
    chain(b, "04B", right, "Ines Navarro", "1991-03-03", "Spain",
          checked_at="2024-08-01", doc="LQ448219")
    hid = b.hit("04", "ADV-A-04", "Ines Navarro", dobs="1991-03-03", countries="Spain")
    b.alert("04", "Ines Navarro", [hid], dob="1991-03-03", country="Spain",
            city="Madrid", account=acc)
    kid_r = "ADV-KYC-04B"
    reason = same_reason("1991-03-03", kid_r, "1991-03-03", "Spain", "Ines Navarro")
    b.lab(hid, "ADV-A-04", "SAME_ENTITY",
          ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], [left, right],
          [left, right, kid_r], reason,
          path_join([
              "account_ref %s -> accounts -> customer %s" % (acc, left),
              "same document number on approved checks -> one person: ADV-CUS-04, ADV-CUS-04B",
              "latest approved check ADV-KYC-04B",
          ], "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], reason),
          "document_merge",
          "Approved checks LQ 448219 and LQ448219 are the same document number. The newest check agrees with the hit.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Treats the space as a different document, keeps Helen Kruger's 1972 check, and clears.",
          left, "Document number with a space")
    b.groups("ADV-A-04", [[left]])

    # --- 07 approved note that mentions an expired passport ---
    jane = b.customer("07", "Jane Marie Cole", "1970-01-01", "Canada", "Toronto")
    acc = b.account("07", jane)
    text = ("The customer's previous passport expired in 2019. Onfido approved JANE MARIE COLE, "
            "DOB 1982-04-04, via a Canadian passport on 2024-06-01.")
    nid = b.note("07", b.customers[jane]["email"], text, "kyc", "2024-06-01")
    hid = b.hit("07", "ADV-A-07", "Jane Marie Cole", dobs="1982-04-04", countries="Canada")
    b.alert("07", "Jane Marie Cole", [hid], dob="1982-04-04", country="Canada",
            city="Toronto", account=acc)
    reason = same_reason("1982-04-04", nid, "1982-04-04", "Canada", "Jane Marie Cole")
    b.lab(hid, "ADV-A-07", "SAME_ENTITY",
          ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], [jane], [jane, nid], reason,
          path_join([
              "account_ref %s -> accounts -> customer %s" % (acc, jane),
              "customer email -> notes -> %s" % nid,
          ], "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], reason),
          "kyc_note",
          "The word expired refers to the old passport. The sentence is an approved check for 1982-04-04. The record's 1970-01-01 is only self-declared.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Sees 'expired', drops the note, and clears on the declared date of birth 1970-01-01.",
          jane, "Approved note says a passport expired")
    b.groups("ADV-A-07", [[jane]])

    # --- 10 "grew up in" is a country the notes tie to the customer ---
    amina = b.customer("10", "Amina Diallo", "1993-05-05", "France", "Lyon")
    acc, app, kid = chain(b, "10", amina, "Amina Diallo", "1993-05-05", "France")
    nid = b.note("10", b.customers[amina]["email"],
                 "Customer grew up in Pakistan and still visits family there.", "phone")
    hid = b.hit("10", "ADV-A-10", "Amina Diallo", countries="Pakistan")
    b.alert("10", "Amina Diallo", [hid], dob="1993-05-05", country="France",
            city="Lyon", email=b.customers[amina]["email"])
    reason = review_nodob("Pakistan", "Amina Diallo")
    b.lab(hid, "ADV-A-10", "REVIEW", ["INSUFFICIENT_DATA"], [amina], [amina, nid], reason,
          path_join([
              "email %s -> customers -> %s" % (b.customers[amina]["email"], amina),
              "customer email -> notes -> %s" % nid,
          ], "REVIEW", ["INSUFFICIENT_DATA"], reason),
          "residence_note",
          "The note says she grew up in Pakistan, so Pakistan is a country tied to her. The hit has no date of birth, so the shared country leaves the hit for review.",
          "DIFFERENT_ENTITY", "LOCATION_MISMATCH",
          "Misses 'grew up in' and clears France against Pakistan.",
          amina, "Residence phrased as grew up in")
    b.groups("ADV-A-10", [[amina]])

    # --- 12 hit country only via citizenship demonym and an address ---
    ife = b.customer("12", "Ifeanyi Okafor", "1986-02-02", "Nigeria", "Kano")
    acc, app, kid = chain(b, "12", ife, "Ifeanyi Okafor", "1986-02-02", "Nigeria")
    hid = b.hit("12", "ADV-A-12", "Ifeanyi Okafor", countries="Russia", citizenship="Nigerian",
                addresses="12 King Street, Madrid, Spain")
    b.alert("12", "Ifeanyi Okafor", [hid], dob="1986-02-02", country="Nigeria",
            city="Kano", account=acc)
    reason = review_nodob("Nigeria", "Ifeanyi Okafor")
    b.lab(hid, "ADV-A-12", "REVIEW", ["INSUFFICIENT_DATA"], [ife], [ife, kid], reason,
          path_join([
              "account_ref %s -> accounts -> customer %s" % (acc, ife),
              "%s -> accounts %s -> onboarding %s -> latest approved check %s" % (ife, acc, app, kid),
          ], "REVIEW", ["INSUFFICIENT_DATA"], reason),
          "countries",
          "Nigerian citizenship and the Spain address are countries tied to the hit. Nigeria is shared, and the hit gives no date of birth.",
          "DIFFERENT_ENTITY", "LOCATION_MISMATCH",
          "Compares only the countries field (Russia) and clears.",
          ife, "Hit country on citizenship and address")
    b.groups("ADV-A-12", [[ife]])

    # --- 20 namesake search result is not the hit's date of birth ---
    mateo = b.customer("20", "Mateo Vargas", "1988-11-03", "Spain", "Valencia")
    acc, app, kid = chain(b, "20", mateo, "Mateo Vargas", "1988-11-03", "Spain")
    b.sr("20", qname("Mateo Vargas"),
         "In March 1980, Spain saw a local news piece featuring Mateo Vargas, who was 40 and worked as a coach.",
         "Mateo Vargas - report")
    hid = b.hit("20", "ADV-A-20", "Mateo Vargas", countries="Spain", primary_category="PEP",
                categories="PEP")
    b.alert("20", "Mateo Vargas", [hid], dob="1988-11-03", country="Spain",
            city="Valencia", account=acc)
    reason = review_nodob("Spain", "Mateo Vargas")
    b.lab(hid, "ADV-A-20", "REVIEW", ["INSUFFICIENT_DATA"], [mateo], [mateo, kid], reason,
          path_join([
              "account_ref %s -> accounts -> customer %s" % (acc, mateo),
              "search results for the hit's name -> ADV-SR-20 is a namesake (not the hit's listing)",
          ], "REVIEW", ["INSUFFICIENT_DATA"], reason),
          "search_result",
          "The only search result is about a namesake: it does not describe a politically exposed person. The hit has no date of birth.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Uses the namesake's age and clears 1988 against 1939 or 1940.",
          mateo, "DOB only in a namesake snippet")
    b.groups("ADV-A-20", [[mateo]])

    # --- 21 corroborated search result, namesake sitting next to it ---
    jose = b.customer("21", "Jose Garcia", "1974-08-08", "Spain", "Seville")
    acc, app, kid = chain(b, "21", jose, "Jose Garcia", "1974-08-08", "Spain")
    good_sr = b.sr("21", qname("Jose Garcia"),
                   "In March 2019, Spain described Jose Garcia as a politically exposed person who was 45 and sat on a council.",
                   "Jose Garcia - pep")
    b.sr("21N", qname("Jose Garcia"),
         "In March 1980, Spain saw a local news piece featuring Jose Garcia, who was 40 and worked as a coach.",
         "Jose Garcia - report")
    hid = b.hit("21", "ADV-A-21", "Jose Garcia", countries="Spain", primary_category="PEP",
                categories="PEP")
    b.alert("21", "Jose Garcia", [hid], dob="1974-08-08", country="Spain",
            city="Seville", account=acc)
    reason = same_reason("1974-08-08", kid, "1973 or 1974", "Spain", "Jose Garcia")
    b.lab(hid, "ADV-A-21", "SAME_ENTITY",
          ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], [jose], [jose, kid, good_sr], reason,
          path_join([
              "account_ref %s -> accounts -> customer %s" % (acc, jose),
              "%s -> accounts %s -> onboarding %s -> latest approved check %s" % (jose, acc, app, kid),
              "search results for the hit's name -> %s (same role and country as the hit)" % good_sr,
          ], "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], reason),
          "search_result",
          "ADV-SR-21 describes a politically exposed person in Spain and gives 1973 or 1974. ADV-SR-21N is a namesake and is not used.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Averages in the namesake snippet and clears.",
          jose, "Search DOB corroborated by listing and country")
    b.groups("ADV-A-21", [[jose]])

    # --- 22 listing phrase only in the title ---
    luis = b.customer("22", "Luis Romero", "1974-01-15", "Spain", "Bilbao")
    acc, app, kid = chain(b, "22", luis, "Luis Romero", "1974-01-15", "Spain")
    sid = b.sr("22", qname("Luis Romero"),
               "In March 2019, Spain noted Luis Romero, who was 45 and sat on a council.",
               "Luis Romero, a politically exposed person")
    hid = b.hit("22", "ADV-A-22", "Luis Romero", countries="Spain", primary_category="PEP",
                categories="PEP")
    b.alert("22", "Luis Romero", [hid], dob="1974-01-15", country="Spain",
            city="Bilbao", account=acc)
    reason = same_reason("1974-01-15", kid, "1973 or 1974", "Spain", "Luis Romero")
    b.lab(hid, "ADV-A-22", "SAME_ENTITY",
          ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], [luis], [luis, kid, sid], reason,
          path_join([
              "account_ref %s -> accounts -> customer %s" % (acc, luis),
              "search results for the hit's name -> %s (same role and country as the hit)" % sid,
          ], "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], reason),
          "search_result",
          "The result's title says he is a politically exposed person and the snippet places him in Spain at age 45 in March 2019 (born 1973 or 1974).",
          "REVIEW", "INSUFFICIENT_DATA",
          "Requires the listing phrase in the snippet body and then has no date of birth, so it sends the hit to review.",
          luis, "Listing phrase only in the title")
    b.groups("ADV-A-22", [[luis]])

    # --- 45 two people, both cleared the same way ---
    n1 = b.customer("45", "Noah Okonkwo", "1982-01-15", "Nigeria", "Lagos")
    n2 = b.customer("45B", "Noah Okonkwo", "1982-08-20", "Nigeria", "Lagos")
    acc1, app1, k1 = chain(b, "45", n1, "Noah Okonkwo", "1982-01-15", "Nigeria")
    acc2, app2, k2 = chain(b, "45B", n2, "Noah Okonkwo", "1982-08-20", "Nigeria")
    hid = b.hit("45", "ADV-A-45", "Noah Okonkwo", dobs="1955-04-04", countries="Nigeria")
    b.alert("45", "Noah Okonkwo", [hid], dob="1982", country="Nigeria", city="Lagos")
    reason = ("The customer's date of birth is 1982-01-15 (ADV-KYC-45), and the other fitting "
              "customer's is 1982-08-20 (ADV-KYC-45B); both contradict the hit's listed date of birth 1955-04-04.")
    b.lab(hid, "ADV-A-45", "DIFFERENT_ENTITY", ["DOB_MISMATCH"], "AMBIGUOUS",
          [n1, n2, k1, k2], reason,
          path_join([
              "name, date of birth, country and city -> customers",
              "2 different people fit (records ADV-CUS-45, ADV-CUS-45B); each is decided separately",
              "both lead to DIFFERENT_ENTITY",
          ], "DIFFERENT_ENTITY", ["DOB_MISMATCH"], reason),
          "ambiguous_customer",
          "Both fitting people are cleared on date of birth, so the decision is the clearance. customer_record_id is still AMBIGUOUS.",
          "REVIEW", "AMBIGUOUS_CUSTOMER_RECORD",
          "Treats every multi-person alert as AMBIGUOUS_CUSTOMER_RECORD, or returns one customer's id.",
          "AMBIGUOUS", "Several people, same decision")
    b.groups("ADV-A-45", [[n1], [n2]])

    # --- 46 two people, decisions differ ---
    mismatch = b.customer("46", "Lucia Ferraro", "1978-09-09", "Italy", "Rome")
    match = b.customer("46B", "Lucia Ferraro", "1978-02-02", "Italy", "Rome")
    chain(b, "46", mismatch, "Lucia Ferraro", "1978-09-09", "Italy")
    chain(b, "46B", match, "Lucia Ferraro", "1978-02-02", "Italy")
    hid = b.hit("46", "ADV-A-46", "Lucia Ferraro", dobs="1978-02-02", countries="Italy")
    b.alert("46", "Lucia Ferraro", [hid], dob="1978", country="Italy", city="Rome")
    reason = ("2 different people fit the screened name and year (ADV-CUS-46, ADV-CUS-46B) "
              "and they lead to different decisions, so the hit needs review.")
    b.lab(hid, "ADV-A-46", "REVIEW", ["AMBIGUOUS_CUSTOMER_RECORD"], "AMBIGUOUS",
          ["ADV-CUS-46", "ADV-CUS-46B", "ADV-KYC-46", "ADV-KYC-46B"], reason,
          path_join([
              "name, date of birth, country and city -> customers",
              "2 different people fit (records ADV-CUS-46, ADV-CUS-46B); each is decided separately",
          ], "REVIEW", ["AMBIGUOUS_CUSTOMER_RECORD"], reason),
          "ambiguous_customer",
          "A screened year fits both full dates. One date agrees with the hit and the other contradicts it.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Keeps the first record (September) and clears.",
          "ADV-CUS-46", "Several people, different decisions")
    b.groups("ADV-A-46", [[mismatch], [match]])

    # --- 47-49 one alert, three hits, only one is the customer ---
    cam = b.customer("47", "Camille Durand", "1988-07-21", "France", "Paris")
    acc, app, kid = chain(b, "47", cam, "Camille Durand", "1988-07-21", "France")
    h1 = b.hit("47", "ADV-A-47", "Camille Durand", dobs="1988-07-21", countries="France")
    h2 = b.hit("48", "ADV-A-47", "Camille Durand", dobs="1952-02-02", countries="France")
    h3 = b.hit("49", "ADV-A-47", "Camille Durand", countries="France")
    b.alert("47", "Camille Durand", [h1, h2, h3], dob="1988-07-21", country="France",
            city="Paris", account=acc)
    r1 = same_reason("1988-07-21", kid, "1988-07-21", "France", "Camille Durand")
    r2 = dob_reason("1988-07-21", kid, "the hit's listed date of birth is 1952-02-02")
    r3 = review_nodob("France", "Camille Durand")
    base = [
        "account_ref %s -> accounts -> customer %s" % (acc, cam),
        "%s -> accounts %s -> onboarding %s -> latest approved check %s" % (cam, acc, app, kid),
    ]
    b.lab(h1, "ADV-A-47", "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
          [cam], [cam, kid], r1, path_join(base, "SAME_ENTITY", ["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"], r1),
          "multi_hit", "This hit's name, date of birth and country agree. The other hits on the alert are different people.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Copies the other hit's 1952 date of birth onto this one and clears.",
          cam, "Only one of three hits is the customer")
    b.lab(h2, "ADV-A-47", "DIFFERENT_ENTITY", ["DOB_MISMATCH"], [cam], [kid], r2,
          path_join(base, "DIFFERENT_ENTITY", ["DOB_MISMATCH"], r2),
          "multi_hit", "Same alert, different hit. The listed date of birth contradicts the customer's.",
          "SAME_ENTITY", "NAME_DOB_LOCATION_MATCH",
          "Confirms every hit whose name matches and ignores this hit's own date of birth.",
          cam, "Sibling hit is a different person")
    b.lab(h3, "ADV-A-47", "REVIEW", ["INSUFFICIENT_DATA"], [cam], [cam, kid], r3,
          path_join(base, "REVIEW", ["INSUFFICIENT_DATA"], r3),
          "multi_hit", "This hit has no date of birth. Name and country agree, so it is review, not a clearance and not a confirm.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Borrows the sibling hit's date of birth and clears.",
          cam, "Sibling hit has no date of birth")
    b.groups("ADV-A-47", [[cam]])

    # --- 54 date of death only in the profile prose ---
    mag = b.customer("54", "Magnus Ekstrom", "1955-05-05", "Italy", "Milan")
    acc, app, kid = chain(b, "54", mag, "Magnus Ekstrom", "1955-05-05", "Italy")
    hid = b.hit("54", "ADV-A-54", "Magnus Ekstrom", dobs="1955-05-05", countries="Italy",
                life_status="Deceased",
                profile_notes="He died on January 2, 2019.")
    b.alert("54", "Magnus Ekstrom", [hid], dob="1955-05-05", country="Italy", city="Milan",
            account=acc, screened_at="2026-11-15")
    reason = ("The hit's profile gives a date of death of 2019-01-02, before the customer "
              "was screened on 2026-11-15.")
    note = ("POLICY.md says a date of death in the profile clears the hit when it is before screening, "
            "but it does not say the date has to sit in deceased_date. Here it is only in the profile notes. "
            "A reading that only the field counts would decide SAME_ENTITY, because the name and date of birth agree.")
    b.lab(hid, "ADV-A-54", "DIFFERENT_ENTITY", ["DECEASED"], [mag], [mag], reason,
          path_join([
              "account_ref %s -> accounts -> customer %s" % (acc, mag),
              "profile notes: died on January 2, 2019",
          ], "DIFFERENT_ENTITY", ["DECEASED"], reason),
          "deceased", "Death date is in the profile notes, before screening, and the name and date of birth would otherwise agree.",
          "SAME_ENTITY", "NAME_DOB_LOCATION_MATCH",
          "Reads only deceased_date, finds it empty, and confirms.",
          mag, "Death date written in prose", ambiguous=True, ambiguous_note=note)
    b.groups("ADV-A-54", [[mag]])

    # --- 55 screened city York also sits in a street name ---
    leeds = b.customer("55", "Clara Yelverton", "1991-08-08", "United Kingdom", "Leeds",
                       address="14 York Road, Leeds")
    york = b.customer("55B", "Clara Yelverton", "1991-02-02", "United Kingdom", "York",
                      address="4 Minster Yard, York")
    chain(b, "55", leeds, "Clara Yelverton", "1991-08-08", "United Kingdom")
    chain(b, "55B", york, "Clara Yelverton", "1991-02-02", "United Kingdom")
    hid = b.hit("55", "ADV-A-55", "Clara Yelverton", dobs="1991-02-02", countries="United Kingdom")
    b.alert("55", "Clara Yelverton", [hid], dob="1991", country="United Kingdom", city="York")
    reason = ("2 different people fit the screened name, year and city string "
              "(ADV-CUS-55, ADV-CUS-55B) and they lead to different decisions, so the hit needs review.")
    note = ("POLICY.md says the screened city must appear in the record's city or address. "
            "'York' appears in '14 York Road, Leeds', so both customers fit and the decisions differ. "
            "A stricter reading, that the city is the place rather than a street word, would keep only "
            "ADV-CUS-55B and decide SAME_ENTITY.")
    b.lab(hid, "ADV-A-55", "REVIEW", ["AMBIGUOUS_CUSTOMER_RECORD"], "AMBIGUOUS",
          ["ADV-CUS-55", "ADV-CUS-55B", "ADV-KYC-55", "ADV-KYC-55B"], reason,
          path_join([
              "name, date of birth, country and city -> customers",
              "2 different people fit (records ADV-CUS-55, ADV-CUS-55B); each is decided separately",
          ], "REVIEW", ["AMBIGUOUS_CUSTOMER_RECORD"], reason),
          "ambiguous_customer",
          "The York Road address contains the screened city as a word. One customer then agrees with the hit and the other does not.",
          "DIFFERENT_ENTITY", "DOB_MISMATCH",
          "Keeps the Leeds record (first id) and clears on the month.",
          "ADV-CUS-55", "City string inside a street name",
          ambiguous=True, ambiguous_note=note)
    b.groups("ADV-A-55", [[leeds], [york]])

    # --- 57 email link matches nobody ---
    priya = b.customer("57", "Nalini Krishnan", "1986-04-04", "Canada", "Toronto")
    acc, app, kid = chain(b, "57", priya, "Nalini Krishnan", "1986-04-04", "Canada")
    hid = b.hit("57", "ADV-A-57", "Nalini Krishnan", dobs="1986-04-04", countries="Canada")
    b.alert("57", "Nalini Krishnan", [hid], dob="1986-04-04", country="Canada",
            city="Toronto", email="nobody.adv@mailbox.example")
    reason = ("No customer record is reached by the alert's email link, so nothing verified "
              "can be compared with the hit and it needs review.")
    note = ("The alert has an email link and it matches no customer. POLICY.md says to follow the link, "
            "and to search only when there is no link. It does not say whether a link that finds nothing "
            "should fall back to a search. A search would find ADV-CUS-57 and confirm SAME_ENTITY.")
    b.lab(hid, "ADV-A-57", "REVIEW", ["INSUFFICIENT_DATA"], None, [], reason,
          path_join([
              "email nobody.adv@mailbox.example -> customers -> no customer found",
          ], "REVIEW", ["INSUFFICIENT_DATA"], reason),
          "customer_link",
          "The link was followed and found nobody. The screened name would match ADV-CUS-57 if a search were allowed.",
          "SAME_ENTITY", "NAME_DOB_LOCATION_MATCH",
          "Ignores the dead link, searches, and confirms Nalini Krishnan.",
          None, "Email link matches nobody", ambiguous=True, ambiguous_note=note)
    b.groups("ADV-A-57", [])

    # Straightforward linked cases. Reasons are the practice-label templates.
    rows = _simple_rows()
    for spec in rows:
        simple(b, spec)
    import more_cases
    more_cases.add(b, same_reason, dob_reason, review_nodob, path_join, chain, qname)
    for hid, module in {
        "ADV-H-03": "load.py phone_key, via customer.py",
        "ADV-H-04": "load.py norm_key, via customer.py",
        "ADV-H-07": "notes_parse.py",
        "ADV-H-10": "notes_parse.py",
        "ADV-H-19": "hit.py",
        "ADV-H-22": "hit.py",
        "ADV-H-54": "hit.py",
    }.items():
        b.labels[hid]["module"] = module


def _simple_rows():
    s = same_reason
    d = dob_reason
    rows = []

    def add(**kwargs):
        rows.append(kwargs)

    add(tag="05", title="Newer check rejected", category="kyc_status",
        name="Nora Bergstrom", dob="1984-06-12", country="Netherlands", city="Amsterdam",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1984-06-12", "ADV-KYC-05", "1984-06-12", "Netherlands", "Nora Bergstrom"),
        weakness="The newest check is rejected, so it is not evidence. The older approved check agrees.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DOB_MISMATCH",
        naive_note="Uses the latest check regardless of result and clears on 1960-01-01.",
        checked_at="2020-05-01",
        extra_kyc=[{"tag": "05R", "dob": "1960-01-01", "result": "rejected", "checked_at": "2025-09-01"}])

    add(tag="06", title="Newer check expired", category="kyc_status",
        name="Lars Kovacs", dob="1977-11-02", country="Hungary", city="Budapest",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1977-11-02", "ADV-KYC-06", "1977-11-02", "Hungary", "Lars Kovacs"),
        weakness="An expired check is not evidence, even when it is newer than the approved one.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DOB_MISMATCH",
        naive_note="Uses the expired 1999-01-01 check and clears.",
        checked_at="2019-04-01",
        extra_kyc=[{"tag": "06R", "dob": "1999-01-01", "result": "expired", "checked_at": "2025-09-01"}])

    add(tag="08", title="Verified DOB beats the record", category="verified_vs_declared",
        name="Elena Moretti", dob="1985-09-14", record_dob="1966-01-01",
        country="Italy", city="Rome", link="login",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["KYC"],
        reason=s("1985-09-14", "ADV-KYC-08", "1985-09-14", "Italy", "Elena Moretti"),
        weakness="The record's date of birth contradicts the hit. The approved check's date agrees, and verified wins.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DOB_MISMATCH",
        naive_note="Clears on the self-declared 1966-01-01.")

    add(tag="09", title="Verified name beats the record", category="verified_vs_declared",
        name="Samira Adeyemi", record_name="Samira Adeyemi", kyc_name="Chioma Adeyemi",
        dob="1990-03-12", country="Nigeria", city="Lagos",
        hit_name="Samira Adeyemi",
        decision="DIFFERENT_ENTITY", codes=["NAME_MISMATCH_VERIFIED"],
        evidence=["KYC"],
        reason="The customer's verified name is Chioma Adeyemi (ADV-KYC-09), which does not match the hit's name Samira Adeyemi.",
        weakness="The name on the record matches the hit. The verified legal name does not, and it outranks the record.",
        naive_decision="SAME_ENTITY", naive_code="NAME_DOB_LOCATION_MATCH",
        naive_note="Confirms on the record name and ignores the verified name.")

    add(tag="11", title="Customer has two countries", category="countries",
        name="Chinedu Okeke", dob="1981-01-09", country="Nigeria", city="Abuja",
        nationality="Nigeria", residence="United Kingdom",
        hit_countries="Nigeria; Russia", dobs=None, screened_country="Nigeria",
        decision="REVIEW", codes=["INSUFFICIENT_DATA"], evidence=["CUS"],
        reason=review_nodob("Nigeria", "Chinedu Okeke"),
        weakness="Residence is the United Kingdom and nationality is Nigeria. The hit lists Nigeria and Russia. Nigeria is shared, and there is no date of birth.",
        naive_decision="DIFFERENT_ENTITY", naive_code="LOCATION_MISMATCH",
        naive_note="Compares United Kingdom with Russia and clears.")

    add(tag="13", title="Document country is the shared one", category="countries",
        name="Camille Fontaine", dob="1976-07-07", country="France", city="Lyon",
        kyc_country="Belgium", hit_countries="Belgium", dobs=None,
        decision="REVIEW", codes=["INSUFFICIENT_DATA"], evidence=["CUS", "KYC"],
        reason=review_nodob("Belgium", "Camille Fontaine"),
        weakness="Residence is France. The approved document is Belgian, which the hit shares. No date of birth on the hit.",
        naive_decision="DIFFERENT_ENTITY", naive_code="LOCATION_MISMATCH",
        naive_note="Uses only the residence country and clears France against Belgium.")

    add(tag="14", title="Name and DOB agree, countries do not", category="location_exception",
        name="Yuki Nakamura", dob="1984-07-19", country="Japan", city="Tokyo",
        hit_countries="Brazil",
        decision="REVIEW", codes=["INSUFFICIENT_DATA"], evidence=["CUS", "KYC"],
        reason=("The customer's date of birth 1984-07-19 (ADV-KYC-14) agrees with the hit's 1984-07-19. "
                "The customer's name agrees with the hit's name Yuki Nakamura. "
                "The customer is linked only to Japan but the hit is linked only to Brazil, "
                "and a country difference does not clear a hit whose name and date of birth agree."),
        weakness="Location would clear, but name and date of birth agree, so the hit is review.",
        naive_decision="DIFFERENT_ENTITY", naive_code="LOCATION_MISMATCH",
        naive_note="Clears on Japan versus Brazil and ignores the name and date of birth agreement.")

    add(tag="15", title="Europe and International are not countries", category="not_a_country",
        name="Giulia Esposito", dob="1979-04-04", country="Italy", city="Milan",
        hit_countries="Europe; International",
        decision="SAME_ENTITY", codes=["NAME_DOB_MATCH"], evidence=["KYC"],
        reason=s("1979-04-04", "ADV-KYC-15", "1979-04-04", "Italy", "Giulia Esposito", False),
        weakness="The hit's only 'countries' are Europe and International, which are not countries. Nothing contradicts name and date of birth.",
        naive_decision="DIFFERENT_ENTITY", naive_code="LOCATION_MISMATCH",
        naive_note="Treats Europe as a country different from Italy and clears.")

    add(tag="16", title="Age in the first paragraph", category="profile_age",
        name="Elena Navarro", dob="1974-02-02", country="Spain", city="Madrid",
        dobs=None, profile_notes="She was aged 45 in March 2019 and kept a low profile.",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1974-02-02", "ADV-KYC-16", "1973 or 1974", "Spain", "Elena Navarro"),
        weakness="No dobs field. Aged 45 in March 2019 means born in 1973 or 1974, and 1974 agrees.",
        naive_decision="REVIEW", naive_code="INSUFFICIENT_DATA",
        naive_note="Ignores the age sentence and will not confirm without a dobs field.")

    add(tag="17", title="One year outside an age pair", category="dob_boundary",
        name="Pablo Ibanez", dob="1975-06-01", country="Spain", city="Bilbao",
        dobs=None, profile_notes="He was aged 45 in March 2019.",
        decision="REVIEW", codes=["INSUFFICIENT_DATA"], evidence=["CUS", "KYC"],
        reason=("Both the customer and the hit are linked to Spain. "
                "The customer's name agrees with the hit's name Pablo Ibanez. "
                "The customer's date of birth 1975-06-01 (ADV-KYC-17) is one year from the hit's 1973 or 1974, "
                "so the dates neither agree nor contradict and the hit can be neither cleared nor confirmed."),
        weakness="1975 is not one of 1973 or 1974, and it is not more than one year outside both. That is review, not a date-of-birth clearance.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DOB_MISMATCH",
        naive_note="Treats 'not one of the two years' as a mismatch and clears.")

    add(tag="18", title="Age buried in the second paragraph", category="profile_scope",
        name="Rafael Costa", dob="1990-05-05", country="Brazil", city="Recife",
        dobs=None,
        profile_notes=("Rafael Costa is a Brazilian politician who sat on the budget committee.\n\n"
                       "A later biography says he was aged 30 in June 2010."),
        decision="REVIEW", codes=["INSUFFICIENT_DATA"], evidence=["CUS", "KYC"],
        reason=review_nodob("Brazil", "Rafael Costa"),
        weakness="An age counts only in the first paragraph. The second paragraph's 1979 or 1980 would have contradicted 1990, and it does not count.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DOB_MISMATCH",
        naive_note="Reads the whole profile and clears on the second paragraph.")

    add(tag="19", title="Born-on sentence in the first paragraph", category="explicit_dob",
        name="Elena Varga", dob="1975-03-12", country="Hungary", city="Budapest",
        dobs=None,
        profile_notes="Elena Varga was born on 12 March 1975 in Budapest.",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1975-03-12", "ADV-KYC-19", "1975-03-12", "Hungary", "Elena Varga"),
        weakness="The first paragraph states the birth date outright. Name, that date and Hungary agree.",
        naive_decision="REVIEW", naive_code="INSUFFICIENT_DATA",
        naive_note="Only recognises 'aged N in <date>' and then has no date of birth.")

    add(tag="23", title="Year-only verified DOB agrees with a full date", category="partial_dob",
        name="Tomas Berger", dob="1988-11-03", kyc_dob="1988", country="France", city="Lyon",
        hit_dob="1988-11-03",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["KYC"],
        reason=s("1988", "ADV-KYC-23", "1988-11-03", "France", "Tomas Berger"),
        weakness="A birth year alone agrees with a full date when the year is the same.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DOB_MISMATCH",
        naive_note="Requires a full date on both sides and treats the missing month as a mismatch.")

    add(tag="24", title="Year-month on the hit agrees", category="partial_dob",
        name="Hugo Lambert", dob="1988-11-03", country="France", city="Nantes",
        hit_dob="1988-11", dobs="1988-11",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["KYC"],
        reason=s("1988-11-03", "ADV-KYC-24", "1988-11", "France", "Hugo Lambert"),
        weakness="The hit gives year and month. The day is only on the customer, so the dates agree.",
        naive_decision="REVIEW", naive_code="INSUFFICIENT_DATA",
        naive_note="Will not confirm until both sides have a day.")

    add(tag="25", title="Same year, month differs", category="partial_dob",
        name="Nina Hoffmann", dob="1988-11-03", country="Germany", city="Munich",
        hit_dob="1988-12", dobs="1988-12",
        decision="DIFFERENT_ENTITY", codes=["DOB_MISMATCH"], evidence=["KYC"],
        reason=d("1988-11-03", "ADV-KYC-25", "the hit's listed date of birth is 1988-12"),
        weakness="Both give a month in 1988 and the months differ, so every date the hit gives is contradicted.",
        naive_decision="SAME_ENTITY", naive_code="NAME_DOB_MATCH",
        naive_note="Treats the same year as enough and confirms.")

    add(tag="26", title="One year and one day apart", category="dob_boundary",
        name="Oscar Fischer", dob="1987-12-31", country="Germany", city="Hamburg",
        hit_dob="1988-01-01",
        decision="REVIEW", codes=["INSUFFICIENT_DATA"], evidence=["KYC"],
        reason=("Both the customer and the hit are linked to Germany. "
                "The customer's name agrees with the hit's name Oscar Fischer. "
                "The customer's date of birth 1987-12-31 (ADV-KYC-26) and the hit's 1988-01-01 "
                "are one year apart and not in the same year, so the dates neither agree nor contradict "
                "and the hit can be neither cleared nor confirmed."),
        weakness="More than one year outside is a mismatch, and a month clash counts only in the same year. A one-year gap is neither.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DOB_MISMATCH",
        naive_note="Sees December versus January and clears.")

    add(tag="27", title="One of two listed dates agrees", category="partial_dob",
        name="Vera Schneider", dob="1988-11-03", country="Germany", city="Cologne",
        dobs="1950-01-01; 1988-11-03",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["KYC"],
        reason=s("1988-11-03", "ADV-KYC-27", "1950-01-01, 1988-11-03", "Germany", "Vera Schneider"),
        weakness="One agreeing date is enough to stop a date-of-birth clearance, and here one date agrees outright.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DOB_MISMATCH",
        naive_note="Requires every listed date to match and clears on 1950-01-01.")

    add(tag="28", title="Slash date is day-first", category="day_first",
        name="Emma Laurent", dob="1980-06-05", kyc_dob="05/06/1980",
        country="France", city="Paris", link="login",
        hit_dob="1980-06-05",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["KYC"],
        reason=s("1980-06-05", "ADV-KYC-28", "1980-06-05", "France", "Emma Laurent"),
        weakness="05/06/1980 is 5 June 1980, the same day as 1980-06-05.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DOB_MISMATCH",
        naive_note="Reads the slash date month-first (5 May) and clears.")

    add(tag="29", title="Turns 16 on the report date", category="temporal_person",
        name="Lea Moreau", dob="2004-09-10", country="France", city="Lyon",
        profile_notes="According to Le Monde; September 10, 2020: elected to the council.",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("2004-09-10", "ADV-KYC-29", "2004-09-10", "France", "Lea Moreau"),
        weakness="On 10 September 2020 she turned 16. Younger than 16 is the clearance, and 16 is not younger than 16.",
        naive_decision="DIFFERENT_ENTITY", naive_code="TEMPORAL_IMPOSSIBILITY",
        naive_note="Clears at age <= 16.")

    add(tag="30", title="Day before the 16th birthday", category="temporal_person",
        name="Hugo Petit", dob="2004-09-10", country="France", city="Nantes",
        profile_notes="According to Le Monde; September 9, 2020: elected to the council.",
        decision="DIFFERENT_ENTITY", codes=["TEMPORAL_IMPOSSIBILITY"], evidence=["KYC"],
        reason=("The customer was born on 2004-09-10 (ADV-KYC-30), so they were 15 "
                "when the hit's profile reports activity on 2020-09-09."),
        weakness="The day before the 16th birthday she was 15, which is younger than 16, even though the name and date of birth agree.",
        naive_decision="SAME_ENTITY", naive_code="NAME_DOB_LOCATION_MATCH",
        naive_note="Confirms on name and date of birth and never checks the dated report.")

    add(tag="31", title="Month-only line is not a dated report", category="report_wording",
        name="Chloe Bernard", dob="2002-03-03", country="France", city="Lille",
        profile_notes="According to Reuters; June 2016: appointed minister.",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("2002-03-03", "ADV-KYC-31", "2002-03-03", "France", "Chloe Bernard"),
        weakness="A dated report is 'Month DD, YYYY'. 'June 2016' has no day, so it is not a report. She would have been 14 if it counted.",
        naive_decision="DIFFERENT_ENTITY", naive_code="TEMPORAL_IMPOSSIBILITY",
        naive_note="Treats June 2016 as the earliest report and clears.")

    add(tag="32", title="Other wording is not a dated report", category="report_wording",
        name="Marc Duval", dob="2000-01-01", country="France", city="Toulouse",
        profile_notes="On September 10, 2005, Reuters reported he led the council.",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("2000-01-01", "ADV-KYC-32", "2000-01-01", "France", "Marc Duval"),
        weakness="Only lines of the form 'According to …; Month DD, YYYY:' are dated reports. This sentence is not one. He would have been 5 if it counted.",
        naive_decision="DIFFERENT_ENTITY", naive_code="TEMPORAL_IMPOSSIBILITY",
        naive_note="Takes any date in the notes as a report and clears.")

    add(tag="33", title="Incorporated on the report date", category="temporal_company",
        name="Nordlicht Energie GmbH", hit_name="Nordlicht Energie Ltd",
        dob="2010-05-05", country="Germany", city="Berlin", entity="Company", hit_entity="Company",
        profile_notes="According to Handelsblatt; May 5, 2010: awarded a state contract.",
        decision="SAME_ENTITY", codes=["NAME_LOCATION_MATCH"], evidence=["CUS", "KYC"],
        reason=("Both the customer and the hit are linked to Germany. "
                "The customer's name agrees with the hit's name Nordlicht Energie Ltd."),
        weakness="Incorporated on the report date is not incorporated after it. Legal forms are not name parts, and the country agrees.",
        naive_decision="DIFFERENT_ENTITY", naive_code="TEMPORAL_IMPOSSIBILITY",
        naive_note="Treats 'on the same day' as impossible and clears.")

    add(tag="34", title="Incorporated the day after the report", category="temporal_company",
        name="Berglicht Werke GmbH", hit_name="Berglicht Werke Ltd",
        dob="2010-05-06", country="Germany", city="Hamburg", entity="Company", hit_entity="Company",
        profile_notes="According to Handelsblatt; May 5, 2010: awarded a state contract.",
        decision="DIFFERENT_ENTITY", codes=["TEMPORAL_IMPOSSIBILITY"], evidence=["KYC"],
        reason=("The customer was incorporated on 2010-05-06 (ADV-KYC-34), after the hit's "
                "profile reports activity on 2010-05-05."),
        weakness="The day after the report is after it, so the company could not be the subject. Name and country would otherwise agree.",
        naive_decision="SAME_ENTITY", naive_code="NAME_LOCATION_MATCH",
        naive_note="Confirms the company on name and country and skips the report.")

    add(tag="35", title="Legal form is not a name part", category="legal_form",
        name="Helvetia Handels GmbH", hit_name="Helvetia Handels Ltd",
        dob="2001-04-01", country="Switzerland", city="Zurich", entity="Company", hit_entity="Company",
        decision="SAME_ENTITY", codes=["NAME_LOCATION_MATCH"], evidence=["CUS", "KYC"],
        reason=("Both the customer and the hit are linked to Switzerland. "
                "The customer's name agrees with the hit's name Helvetia Handels Ltd."),
        weakness="GmbH and Ltd are legal forms. The remaining name and the country agree, and nothing contradicts them.",
        naive_decision="DIFFERENT_ENTITY", naive_code="NAME_MISMATCH_VERIFIED",
        naive_note="Requires the full strings to match, treats GmbH versus Ltd as a contradiction, and clears.")

    add(tag="36", title="Person versus company", category="entity_type",
        name="Helena Marks", hit_name="Helena Marks Ltd", dob="1980-01-01",
        country="Germany", city="Berlin", hit_entity="Company",
        decision="DIFFERENT_ENTITY", codes=["ENTITY_TYPE_MISMATCH"], evidence=["CUS"],
        reason="The customer is an individual (ADV-CUS-36) but the hit is a company.",
        weakness="The name would agree once Ltd is dropped, and the dates are the same number. One is a person and the other a company.",
        naive_decision="SAME_ENTITY", naive_code="NAME_DOB_LOCATION_MATCH",
        naive_note="Ignores entity type and confirms.")

    add(tag="37", title="Company versus person", category="entity_type",
        name="Helena Marks Ltd", hit_name="Helena Marks", dob="1980-01-01",
        country="Germany", city="Munich", entity="Company", hit_entity="Individual",
        decision="DIFFERENT_ENTITY", codes=["ENTITY_TYPE_MISMATCH"], evidence=["CUS"],
        reason="The customer is a company (ADV-CUS-37) but the hit is an individual.",
        weakness="The other direction of the same trap.",
        naive_decision="SAME_ENTITY", naive_code="NAME_LOCATION_MATCH",
        naive_note="Drops Ltd, matches the person, and confirms.")

    add(tag="38", title="Verified name is a placeholder", category="placeholder",
        name="Marta Blanco", record_name="Marta Blanco", kyc_name="TEST UNKNOWN",
        dob="1992-02-02", country="Spain", city="Madrid",
        decision="REVIEW", codes=["INSUFFICIENT_DATA"], evidence=["KYC"],
        reason=("The customer's verified name is TEST UNKNOWN (ADV-KYC-38), which has no real name parts, "
                "so the customer can be neither confirmed nor cleared on name. "
                "The date of birth 1992-02-02 agrees with the hit's 1992-02-02 and both are linked to Spain, "
                "but that is not enough."),
        weakness="Placeholders are not name parts. A verified name with fewer than two real parts cannot confirm or clear, even though the record name matches the hit.",
        naive_decision="DIFFERENT_ENTITY", naive_code="NAME_MISMATCH_VERIFIED",
        naive_note="Compares the placeholder as a real name and clears.",
        cite_kyc_path=True)

    add(tag="39", title="Single-part alias", category="alias",
        name="Wei Chen", hit_name="Johnathan Smith", aliases="Chen",
        dob="1978-08-08", country="China", city="Shanghai",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1978-08-08", "ADV-KYC-39", "1978-08-08", "China", "Chen"),
        weakness="A hit's single-part alias can agree with the customer's name. Chen does. The primary name does not.",
        naive_decision="DIFFERENT_ENTITY", naive_code="NAME_MISMATCH_VERIFIED",
        naive_note="Compares only Johnathan Smith and clears.")

    add(tag="40", title="Yusuf and Joseph are the same part", category="name_variant",
        name="Yusuf Khan", hit_name="Joseph Khan", dob="1971-01-11",
        country="Pakistan", city="Lahore",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1971-01-11", "ADV-KYC-40", "1971-01-11", "Pakistan", "Joseph Khan"),
        weakness="Yusuf and Joseph are listed together in name_variants.json. The edit distance alone would not match them.",
        naive_decision="DIFFERENT_ENTITY", naive_code="NAME_MISMATCH_VERIFIED",
        naive_note="No variant list, so only Khan matches and the name fails.")

    add(tag="41", title="Bob and Robert", category="name_variant",
        name="Bob Smith", hit_name="Robert Smith", dob="1969-09-09",
        country="United States", city="Chicago",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1969-09-09", "ADV-KYC-41", "1969-09-09", "United States", "Robert Smith"),
        weakness="Bob is a listed short form of Robert.",
        naive_decision="DIFFERENT_ENTITY", naive_code="NAME_MISMATCH_VERIFIED",
        naive_note="Exact token match fails Bob against Robert and clears.")

    add(tag="42", title="One-edit typo", category="name_edit",
        name="Anna Smyth", hit_name="Anna Smith", dob="1983-03-03",
        country="Ireland", city="Dublin",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1983-03-03", "ADV-KYC-42", "1983-03-03", "Ireland", "Anna Smith"),
        weakness="Smyth and Smith are one substitution in a five-letter part, which is inside the edit limit.",
        naive_decision="DIFFERENT_ENTITY", naive_code="NAME_MISMATCH_VERIFIED",
        naive_note="Exact match fails and clears.")

    add(tag="43", title="Parts written together", category="name_shape",
        name="Abdulsalam Karim", hit_name="Abdul Salam Karim", dob="1974-04-14",
        country="Nigeria", city="Kano",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1974-04-14", "ADV-KYC-43", "1974-04-14", "Nigeria", "Abdul Salam Karim"),
        weakness="Abdulsalam is Abdul and Salam written together, one part covering both.",
        naive_decision="DIFFERENT_ENTITY", naive_code="NAME_MISMATCH_VERIFIED",
        naive_note="Won't join split parts, so only Karim matches, and clears.")

    add(tag="44", title="Order, accents, brackets, honorific", category="name_shape",
        name="Munoz Jose", record_name="Dr. José Muñoz (Jr)", kyc_name="Dr. José Muñoz (Jr)",
        hit_name="Jose Munoz", dob="1982-12-12", country="Spain", city="Madrid",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1982-12-12", "ADV-KYC-44", "1982-12-12", "Spain", "Jose Munoz"),
        weakness="Accents, the bracketed Jr and the honorific Dr drop out or do not block two matching parts. Order does not matter.",
        naive_decision="DIFFERENT_ENTITY", naive_code="NAME_MISMATCH_VERIFIED",
        naive_note="Byte-compares the strings, keeps Dr and Jr, and clears.")

    add(tag="50", title="Died on the screening date", category="deceased",
        name="Soren Lindqvist", dob="1948-08-08", country="Germany", city="Berlin",
        deceased_date="2026-11-15", life_status="Deceased", screened_at="2026-11-15",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1948-08-08", "ADV-KYC-50", "1948-08-08", "Germany", "Soren Lindqvist"),
        weakness="A death on the screening date is not before it.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DECEASED",
        naive_note="Clears when death <= screening date.")

    add(tag="51", title="Died the day before screening", category="deceased",
        name="Freya Holmberg", dob="1944-04-04", country="Netherlands", city="Rotterdam",
        deceased_date="2026-11-14", life_status="Deceased", screened_at="2026-11-15",
        decision="DIFFERENT_ENTITY", codes=["DECEASED"], evidence=["CUS"],
        reason=("The hit's profile gives a date of death of 2026-11-14, before the customer "
                "was screened on 2026-11-15."),
        weakness="The day before screening is before it, even though name and date of birth agree.",
        naive_decision="SAME_ENTITY", naive_code="NAME_DOB_LOCATION_MATCH",
        naive_note="Confirms on name and date of birth and ignores the death date.")

    add(tag="52", title="Died after screening", category="deceased",
        name="Astrid Dahl", dob="1950-10-10", country="Belgium", city="Brussels",
        deceased_date="2026-12-01", life_status="Deceased", screened_at="2026-11-15",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1950-10-10", "ADV-KYC-52", "1950-10-10", "Belgium", "Astrid Dahl"),
        weakness="A later death does not clear. The profile can list someone who died after we screened them.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DECEASED",
        naive_note="Any death date clears.")

    add(tag="53", title="Death year equals the screening year", category="deceased",
        name="Ingrid Solberg", dob="1946-06-06", country="France", city="Paris",
        deceased_date="2026", life_status="Deceased", screened_at="2026-06-15",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1946-06-06", "ADV-KYC-53", "1946-06-06", "France", "Ingrid Solberg"),
        weakness="A year-only death in 2026 might be after 15 June 2026. It is not shown to be before screening.",
        naive_decision="DIFFERENT_ENTITY", naive_code="DECEASED",
        naive_note="Compares years only and clears.")

    add(tag="56", title="GB, British and UK are one country", category="countries",
        name="Adewale Balogun", dob="1973-03-03", country="United Kingdom", city="London",
        residence="GB", nationality="British", hit_countries="UK",
        decision="SAME_ENTITY", codes=["NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH"],
        evidence=["CUS", "KYC"],
        reason=s("1973-03-03", "ADV-KYC-56", "1973-03-03", "United Kingdom", "Adewale Balogun"),
        weakness="GB, British and UK are the United Kingdom. The name and date of birth agree as well.",
        naive_decision="DIFFERENT_ENTITY", naive_code="LOCATION_MISMATCH",
        naive_note="String-compares GB with UK and clears.")

    add(tag="58", title="Same year and month, day differs", category="dob_boundary",
        name="Klara Weiss", dob="1988-11-03", country="Germany", city="Stuttgart",
        hit_dob="1988-11-04",
        decision="DIFFERENT_ENTITY", codes=["DOB_MISMATCH"], evidence=["KYC"],
        reason=d("1988-11-03", "ADV-KYC-58", "the hit's listed date of birth is 1988-11-04"),
        weakness="Same year, same month, days both given and different. That contradicts.",
        naive_decision="SAME_ENTITY", naive_code="NAME_DOB_MATCH",
        naive_note="Allows a one-day gap and confirms.")

    return rows


def write(b):
    os.makedirs(OUT, exist_ok=True)
    src = os.path.join(ROOT, "dev", "name_variants.json")
    shutil.copyfile(src, os.path.join(OUT, "name_variants.json"))
    counts = {
        "alerts.jsonl": dump("alerts.jsonl", list(b.alerts.values()), "alert_id"),
        "hits.jsonl": dump("hits.jsonl", list(b.hits.values()), "hit_id"),
        "customers.jsonl": dump("customers.jsonl", list(b.customers.values()), "record_id"),
        "accounts.jsonl": dump("accounts.jsonl", list(b.accounts.values()), "account_id"),
        "onboarding.jsonl": dump("onboarding.jsonl", b.onboarding, "kyc_applicant_id"),
        "kyc_checks.jsonl": dump("kyc_checks.jsonl", list(b.kyc.values()), "check_id"),
        "notes.jsonl": dump("notes.jsonl", list(b.notes.values()), "note_id"),
        "search_results.jsonl": dump("search_results.jsonl", list(b.search.values()), "result_id"),
        "practice_labels.jsonl": dump("practice_labels.jsonl", list(b.labels.values()), "hit_id"),
    }
    return counts


def verify(b):
    from screening.customer import resolve, _parsed_kyc_note
    from screening.load import load_data

    _parsed_kyc_note.cache = {}
    data = load_data(OUT)
    bad = 0
    for alert in data.alerts:
        res = resolve(alert, data)
        got = tuple(sorted(tuple(p.record_ids) for p in res.persons))
        exp = b.expect.get(alert["alert_id"])
        if exp is None:
            print("no expectation", alert["alert_id"])
            bad += 1
            continue
        if got != exp:
            print("RESOLVE", alert["alert_id"])
            print("  got ", got)
            print("  want", exp)
            for line in res.path:
                print("  ", line)
            bad += 1
    # Traps that depend on the resolver dropping evidence.
    by_alert = {a["alert_id"]: a for a in data.alerts}
    _parsed_kyc_note.cache = {}
    jane = resolve(by_alert["ADV-A-07"], data).persons[0]
    if jane.verified_dob is not None or jane.verified_name is not None:
        print("note trap failed: expired-word note was kept", jane.verified_name, jane.verified_dob)
        bad += 1
    amina = resolve(by_alert["ADV-A-10"], data).persons[0]
    countries = {c.value for c in amina.countries}
    if "Pakistan" in countries or "France" not in countries:
        print("residence trap failed", countries)
        bad += 1
    nora = resolve(by_alert["ADV-A-05"], data).persons[0]
    if nora.verified_dob is None or nora.verified_dob.value.year != 1984:
        print("rejected-newer trap failed", nora.verified_dob)
        bad += 1
    lars = resolve(by_alert["ADV-A-06"], data).persons[0]
    if lars.verified_dob is None or lars.verified_dob.value.year != 1977:
        print("expired-newer trap failed", lars.verified_dob)
        bad += 1
    if bad:
        raise SystemExit("%s resolution checks failed" % bad)
    print("resolution checks passed (%s alerts)" % len(data.alerts))


def main():
    b = Bank()
    build(b)
    counts = write(b)
    verify(b)
    from collections import Counter
    cats = Counter(row["category"] for row in b.labels.values())
    decisions = Counter(row["decision"] for row in b.labels.values())
    naive_de = sum(1 for row in b.labels.values()
                   if row["naive_decision"] == "DIFFERENT_ENTITY" and row["decision"] != "DIFFERENT_ENTITY")
    print("files", counts)
    print("hits", len(b.labels), "decisions", dict(decisions))
    print("naive would wrongly clear", naive_de)
    for cat, n in sorted(cats.items()):
        print("  %-22s %s" % (cat, n))


if __name__ == "__main__":
    main()
