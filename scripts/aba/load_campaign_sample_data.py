"""Load ABA sample campaigns, campaign members (existing Leads and Contacts) and link existing ABA
opportunities to them as Primary Campaign Source. Safe to re-run: skips campaigns that already exist.

Usage (from the project root):
    python scripts/aba/load_campaign_sample_data.py
"""
import json
import subprocess
import time

ORG = "ABA_Dev"

CAMPAIGNS = [
    {"Name": "SAP Innovation Day Riyadh 2026", "Type": "Event", "Status": "Completed", "IsActive": "true",
     "StartDate": "2026-09-24", "EndDate": "2026-09-24", "BudgetedCost": 150000, "ActualCost": 138000,
     "ExpectedRevenue": 5000000, "ExpectedResponse": 40,
     "Event_Venue__c": "Riyadh Front Exhibition & Conference Center", "Event_Street__c": "Airport Road",
     "Event_City__c": "Riyadh", "Event_Country__c": "Saudi Arabia",
     "Description": "Customer event showcasing SAP S/4HANA, SuccessFactors and Data & Analytics offerings.",
     "members": [("Contact", "Rose Gonzalez", "Attended"), ("Contact", "Sean Forbes", "Attended"),
                 ("Contact", "Jack Rogers", "No Show"), ("Contact", "Tim Barr", "Attended"),
                 ("Lead", "Bertha Boxer", "Attended"), ("Lead", "Phyllis Cotton", "No Show"),
                 ("Lead", "Jeff Glimpse", "Registered")],
     "opportunities": ["Najd Retail Group – Data & Analytics 2026", "Khaleej Finance House – Data & Analytics 2026",
                       "Bahrain Telecom Partners – Data & Analytics 2027"]},
    {"Name": "SuccessFactors Webinar – Oct 2026", "Type": "Webinar", "Status": "Planned", "IsActive": "true",
     "StartDate": "2026-10-22", "EndDate": "2026-10-22", "BudgetedCost": 15000, "ExpectedResponse": 30,
     "Description": "Online session on SAP SuccessFactors for HR leaders.",
     "members": [("Contact", "Stella Pavlova", "Registered"), ("Contact", "Lauren Boyle", "Registered"),
                 ("Contact", "Babara Levy", "Invited"), ("Lead", "Mike Braund", "Registered"),
                 ("Lead", "Patricia Feager", "Invited")],
     "opportunities": ["Al Noor Healthcare – SAP SuccessFactors 2027"]},
    {"Name": "SAP Partner Portal Referrals 2026", "Type": "Partner Portal", "Status": "In Progress", "IsActive": "true",
     "StartDate": "2026-01-01", "EndDate": "2026-12-31", "BudgetedCost": 50000,
     "Description": "Opportunities referred through the SAP partner portal.",
     "members": [("Contact", "Andy Young", "Qualified"), ("Contact", "Edna Frank", "Referred")],
     "opportunities": ["Desert Bloom Foods – SAP S/4HANA 2026", "Desert Bloom Foods – SAP SuccessFactors 2026",
                       "Riyadh Smart Utilities – SAP SuccessFactors 2026", "Emirates Facility Mgmt – Data & Analytics 2027"]},
]


def sf(*args, stdin=None):
    out = subprocess.run(["sf.cmd", *args, "-o", ORG], input=stdin, capture_output=True, text=True, encoding="utf-8").stdout
    return json.loads(out) if out.strip().startswith(("{", "[")) else out


def query(q):
    return sf("data", "query", "-q", q, "--json")["result"]["records"]


def rest(method, path, body):
    # The CLI occasionally reads an empty body from stdin (JSON_PARSER_ERROR); retry those.
    for attempt in range(4):
        out = sf("api", "request", "rest", f"/services/data/v67.0/{path}", "-X", method, "--body", "-", stdin=json.dumps(body))
        if "JSON_PARSER_ERROR" in str(out):
            time.sleep(2)
            continue
        if isinstance(out, list) or (isinstance(out, dict) and out.get("success") is False) or "errorCode" in str(out):
            raise RuntimeError(f"{method} {path} failed: {out}")
        return out
    raise RuntimeError(f"{method} {path} failed after retries: {out}")


def esc(s):
    return s.replace("'", "\\'")


def main():
    for c in CAMPAIGNS:
        existing = query(f"SELECT Id FROM Campaign WHERE Name = '{esc(c['Name'])}'")
        if existing:
            cid = existing[0]["Id"]
            print(f"exists  {c['Name']} ({c['Type']}) {cid} - completing members and links")
        else:
            fields = {k: v for k, v in c.items() if k not in ("members", "opportunities")}
            fields["IsActive"] = fields["IsActive"] == "true"
            cid = rest("POST", "sobjects/Campaign", fields)["id"]
            print(f"created {c['Name']} ({c['Type']}) {cid}")
        current = {r.get("LeadId") or r.get("ContactId")
                   for r in query(f"SELECT LeadId, ContactId FROM CampaignMember WHERE CampaignId = '{cid}'")}

        # Wait for the asynchronous flow to set the member statuses for this type.
        needed = {m[2] for m in c["members"]}
        for _ in range(20):
            labels = {r["Label"] for r in query(f"SELECT Label FROM CampaignMemberStatus WHERE CampaignId = '{cid}'")}
            if needed <= labels:
                break
            time.sleep(6)
        else:
            raise RuntimeError(f"statuses {needed - labels} not created on {c['Name']}")

        for kind, name, status in c["members"]:
            person = query(f"SELECT Id FROM {kind} WHERE Name = '{esc(name)}' LIMIT 1")
            if not person:
                print(f"   ! {kind} {name} not found, skipped")
                continue
            if person[0]["Id"] in current:
                print(f"   = {kind:7s} {name:16s} already a member")
                continue
            rest("POST", "sobjects/CampaignMember", {"CampaignId": cid, f"{kind}Id": person[0]["Id"], "Status": status})
            print(f"   + {kind:7s} {name:16s} {status}")

        for opp in c["opportunities"]:
            rows = query(f"SELECT Id FROM Opportunity WHERE Name = '{esc(opp)}'")
            for r in rows:
                rest("PATCH", f"sobjects/Opportunity/{r['Id']}", {"CampaignId": cid})
            print(f"   ~ linked opportunity {opp} ({len(rows)})")


if __name__ == "__main__":
    main()
