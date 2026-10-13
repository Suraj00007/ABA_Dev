"""Build an `sf data import tree` plan from the ABA sample CSVs.

Usage (from the project root):
    python scripts/aba/build_sample_data.py
    sf data import tree --plan data/aba/aba-plan.json -o ABA_Dev

OwnerName is mapped to org users via OWNER_MAP (Developer Edition has limited licences).
CreatedDate is back-dated so Age / sales-cycle reports are meaningful; the loading user
needs the 'Set Audit Fields upon Record Creation' setting and the ABA_Historical_Data_Load
permission set.
"""
import csv
import datetime as dt
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "aba")
TODAY = dt.date.today()

OWNER_MAP = {
    "Mohammed Fouad": "005gK00008Pc7v1QAB",          # Suraj OD
    "Venkatesh Rethinasamy": "005gK00008T6sxlQAB",
    "Mohammed Alburayh": "005gK00008T6tfMQAR",
}


def ref(name):
    return "Acc_" + re.sub(r"[^A-Za-z0-9]", "", name)


def read_csv(name):
    with open(os.path.join(ROOT, name), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def created_date(row, i):
    """Back-date CreatedDate: ~30-75 days before proposal submission, never in the future."""
    proposal = dt.date.fromisoformat(row["Proposal_Submission_Date__c"])
    created = proposal - dt.timedelta(days=30 + (i * 7) % 45)
    latest = TODAY - dt.timedelta(days=7 + (i * 5) % 40)
    created = min(created, latest)
    return f"{created.isoformat()}T09:00:00.000+0000"


def main():
    os.makedirs(OUT, exist_ok=True)
    accounts = read_csv("ABA_sample_accounts.csv")
    opps = read_csv("ABA_sample_opportunities.csv")

    acc_records = [{
        "attributes": {"type": "Account", "referenceId": ref(a["Name"])},
        "Name": a["Name"],
        "Industry": a["Industry"],
        "Segment__c": a["Segment__c"],
        "BillingCountry": a["BillingCountry"],
        "Type": "Customer",
    } for a in accounts]

    acc_names = {a["Name"] for a in accounts}
    opp_records = []
    for i, o in enumerate(opps):
        if o["AccountName"] not in acc_names:
            raise SystemExit(f"Unknown account {o['AccountName']!r} on {o['Name']!r}")
        rec = {
            "attributes": {"type": "Opportunity", "referenceId": f"Opp_{i + 1:02d}"},
            "Name": o["Name"],
            "AccountId": "@" + ref(o["AccountName"]),
            "OwnerId": OWNER_MAP[o["OwnerName"]],
            "StageName": o["StageName"],
            "Probability": float(o["Probability"]),
            "Amount": float(o["Amount"]),
            "CloseDate": o["CloseDate"],
            "Type": o["Type"],
            "LeadSource": o["LeadSource"],
            "Proposal_Submission_Date__c": o["Proposal_Submission_Date__c"],
            "Offering__c": o["Offering__c"],
            "CreatedDate": created_date(o, i),
        }
        if o["Win_Loss_Reason__c"]:
            rec["Win_Loss_Reason__c"] = o["Win_Loss_Reason__c"]
        if o["Win_Loss_Details__c"]:
            rec["Win_Loss_Details__c"] = o["Win_Loss_Details__c"]
        opp_records.append(rec)

    with open(os.path.join(OUT, "Account.json"), "w", encoding="utf-8") as f:
        json.dump({"records": acc_records}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(OUT, "Opportunity.json"), "w", encoding="utf-8") as f:
        json.dump({"records": opp_records}, f, indent=2, ensure_ascii=False)
    with open(os.path.join(OUT, "aba-plan.json"), "w", encoding="utf-8") as f:
        json.dump([
            {"sobject": "Account", "saveRefs": True, "resolveRefs": False, "files": ["Account.json"]},
            {"sobject": "Opportunity", "saveRefs": False, "resolveRefs": True, "files": ["Opportunity.json"]},
        ], f, indent=2)
    print(f"{len(acc_records)} accounts, {len(opp_records)} opportunities -> {OUT}")


if __name__ == "__main__":
    main()
