"""Offline checks: Form D and NIH parsing, ranking, the store and the fit-answer reader.
Run: python -m tests.test_offline"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import yaml

import leads

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load(open(ROOT / "config.yaml", encoding="utf-8"))
FORM = """<edgarSubmission><primaryIssuer><entityName>Acme Health Inc</entityName><issuerAddress><city>Lombard</city>
<stateOrCountry>IL</stateOrCountry></issuerAddress><issuerPhoneNumber>630-555-0100</issuerPhoneNumber></primaryIssuer>
<relatedPersonsList><relatedPersonInfo><relatedPersonName><firstName>n/a</firstName><lastName>Acme GP LLC</lastName></relatedPersonName></relatedPersonInfo>
<relatedPersonInfo><relatedPersonName><firstName>JANE</firstName><lastName>DOE</lastName></relatedPersonName>
<relatedPersonRelationshipList><relationship>Director</relationship><relationship>Executive Officer</relationship></relatedPersonRelationshipList></relatedPersonInfo></relatedPersonsList>
<offeringData><industryGroup><industryGroupType>{industry}</industryGroupType></industryGroup>
<offeringSalesAmounts><totalAmountSold>{sold}</totalAmountSold></offeringSalesAmounts></offeringData></edgarSubmission>"""


def check(cond, msg):
    if not cond:
        raise SystemExit(f"FAILED: {msg}")


def main():
    today = date(2026, 11, 1)
    lead = leads.parse_form_d(FORM.format(industry="Other Health Care", sold=500000), CFG["form_d"], "2026-10-20", "123")
    check(lead and lead.company == "Acme Health Inc" and lead.city == "LOMBARD" and lead.regulated, "form d fields")
    check(lead.contact == "Jane Doe" and "Executive Officer" in lead.contact_title, "placeholder officers are skipped")
    check(leads.parse_form_d(FORM.format(industry="Pooled Investment Fund", sold=500000), CFG["form_d"], "2026-10-20", "1") is None, "funds are dropped")
    check(leads.parse_form_d(FORM.format(industry="Other Technology", sold=9000), CFG["form_d"], "2026-10-20", "1") is None, "too small is dropped")
    check(leads.parse_form_d(FORM.format(industry="Other Technology", sold=99000000), CFG["form_d"], "2026-10-20", "1") is None, "too big is dropped")

    check(leads.parse_form_d(FORM.format(industry="Other Health Care", sold=500000).replace("Acme Health Inc", "Acme Feeder Fund LLC"), CFG["form_d"], "2026-10-20", "1") is None, "investment vehicles are dropped")

    grants = leads.parse_nih([
        {"organization": {"org_name": "X BIO, INC.", "org_city": "EVANSTON", "primary_uei": "U1"}, "fiscal_year": 2025, "project_title": "Old", "contact_pi_name": "ROE, RICHARD"},
        {"organization": {"org_name": "X BIO, INC.", "org_city": "EVANSTON", "primary_uei": "U1"}, "fiscal_year": 2026, "project_title": "New", "contact_pi_name": "ROE, RICHARD", "award_amount": 1000},
    ])
    check(len(grants) == 1 and "New" in grants[0].signal and grants[0].contact == "Richard Roe", "one lead per company, latest grant")

    metro = set(CFG["metro"])
    far = leads.Lead("k", "s", "Far", "PEORIA", "Other Technology", "sig", "2026-01-01")
    check(leads.score(lead, metro, today) > leads.score(far, metro, today), "regulated, nearby and recent rank first")

    check(leads.read_answer('x {"fit": "YES", "offer": "Made up", "opener": "Hi"} y')["offer"] == "", "unknown offers are cleared")
    try:
        leads.read_answer("no json")
        raise SystemExit("FAILED: empty answers must not save")
    except ValueError:
        pass

    with tempfile.TemporaryDirectory() as tmp:
        store = leads.Store(Path(tmp) / "t.db")
        lead.score = 5
        store.upsert(lead, today)
        store.save_fit(lead.key, {"fit": "YES", "why": "w", "offer": leads.OFFERS[0], "opener": "o"})
        store.upsert(lead, today)
        check(store.shown()[0]["fit"] == "YES", "a refresh keeps the fit check")
        check(not store.unchecked(5), "checked leads aren't paid for twice")
        store.conn.close()
    with tempfile.TemporaryDirectory() as tmp:
        store = leads.Store(Path(tmp) / "d.db")
        store.upsert(lead, today)
        store.save_fit(lead.key, {"fit": "YES", "why": "w", "offer": leads.OFFERS[0], "opener": "Saw your raise."})
        subject, body = leads.compose(store.shown()[0], "jane@acme.example")
        check("Hi Jane," in body and "Saw your raise." in body and "security readiness review" in body, "draft uses the lead")
        check("won't write again" in body, "postal address and opt-out")
        check("Steddy" not in body and "Acme Health" in subject, "draft is clean")
        store.conn.close()
    check(leads.pick_email(["loans@bank.com", "info@bank.com", "jane.doe@bank.com", "x@other.com"], "bank.com") == "info@bank.com", "a general inbox on their own domain")
    check(leads.pick_email(["privacy@bank.com", "jane@bank.com"], "bank.com") == "", "no personal or service addresses")
    bank2 = leads.Lead("fdic:2", "FDIC", "Far Bank", "PEORIA", "Community bank", "s", "2026-11-02", regulated=True, detail="2 offices; Peoria County")
    bank3 = leads.Lead("fdic:3", "FDIC", "Near Bank", "BARRINGTON", "Community bank", "s", "2026-11-02", regulated=True, detail="2 offices; Lake County")
    check(leads.score(bank3, set(), today, {"Lake"}) > leads.score(bank2, set(), today, {"Lake"}), "Chicago-area counties rank first")
    check(leads.FORBIDDEN.search("our client Steddy") and leads.FORBIDDEN.search("614 Nolan Avenue") and not leads.FORBIDDEN.search("a fintech startup"), "forbidden claims and the home address are caught")
    with tempfile.TemporaryDirectory() as tmp:
        store = leads.Store(Path(tmp) / "b.db")
        bank3.score = 6
        store.upsert(bank3, today)
        store.mark_banks_fit()
        row = store.to_draft(5)[0]
        check(row["fit"] == "YES" and row["offer"] == "Security readiness review", "banks are a fit without an AI check")
        store.conn.execute("UPDATE leads SET email_checked = '2026-11-02', email = ''")
        check(not store.to_draft(5), "a lead with no public address isn't retried")
        store.conn.close()
    check(leads.cu_name({"CU_NAME": "NATIONAL POLICE", "CU_TYPE": "1"}) == "National Police Federal Credit Union"
          and leads.cu_name({"CU_NAME": "SELFRELIANCE", "CU_TYPE": "2"}) == "Selfreliance Credit Union", "credit union names follow their charter")
    check(leads.AI_TELLS.search("This is exactly the kind of work we love!") and leads.AI_TELLS.search("we leverage AI")
          and not leads.AI_TELLS.search(leads.EXAMPLES), "generated-sounding phrases are caught, and the examples pass")
    print("All checks passed")


if __name__ == "__main__":
    main()
