"""One-time data migration: align the member statuses of campaigns created before the
'ABA Campaign - Set Member Statuses' flow with the status set of their (new) Campaign Type.

Existing statuses are renamed in place (so member history is kept), the default flag is set, and
missing statuses are added. Campaign members whose Status text did not follow a rename are updated.

Usage (from the project root):
    python scripts/aba/migrate_campaign_statuses.py
"""
import json
import subprocess

ORG = "ABA_Dev"

# Type -> ordered list of (label, is_default, has_responded)
STATUS_SETS = {
    "Event": [("Invited", True, False), ("Registered", False, False), ("Attended", False, True), ("No Show", False, False)],
    "Webinar": [("Invited", True, False), ("Registered", False, False), ("Attended", False, True), ("No Show", False, False)],
    "Email": [("Sent", True, False), ("Opened", False, False), ("Clicked", False, True), ("Unsubscribed", False, False)],
    "Social Media": [("Reached", True, False), ("Engaged", False, True)],
    "Website": [("Visited", True, False), ("Form Submitted", False, True)],
    "Sales Outreach": [("Contacted", True, False), ("Meeting Booked", False, True), ("Not Interested", False, False)],
    "Partner Portal": [("Referred", True, False), ("Qualified", False, True), ("Rejected", False, False)],
}
# Old Salesforce default label -> position in the new set (0 = default, 1 = before response, 2 = response)
OLD_TO_POSITION = {"Sent": 0, "Planned": 0, "Received": 1, "Responded": 2}


def sf(*args, stdin=None):
    out = subprocess.run(["sf.cmd", *args, "-o", ORG] + ([] if "rest" in args else ["--json"]),
                         input=stdin, capture_output=True, text=True, encoding="utf-8").stdout
    return json.loads(out) if out.strip().startswith(("{", "[")) else out


def query(q):
    return sf("data", "query", "-q", q)["result"]["records"]


def patch(sobject, rid, body):
    out = sf("api", "request", "rest", f"/services/data/v67.0/sobjects/{sobject}/{rid}", "-X", "PATCH",
             "--body", "-", stdin=json.dumps(body))
    if out and "errorCode" in str(out):
        raise RuntimeError(f"PATCH {sobject} {rid} {body} failed: {out}")
    return out


def main():
    campaigns = {c["Id"]: c for c in query("SELECT Id, Name, Type FROM Campaign WHERE Type != null")}
    statuses = query("SELECT Id, CampaignId, Label, IsDefault, HasResponded, SortOrder FROM CampaignMemberStatus "
                     "ORDER BY CampaignId, SortOrder")
    by_campaign = {}
    for s in statuses:
        by_campaign.setdefault(s["CampaignId"], []).append(s)

    for cid, current in by_campaign.items():
        camp = campaigns.get(cid)
        if not camp:
            continue
        target = STATUS_SETS[camp["Type"]]
        labels = [s["Label"] for s in current]
        if labels == [t[0] for t in target]:
            print(f"OK   {camp['Name']}: already aligned")
            continue
        print(f"MIGRATE {camp['Name']} ({camp['Type']}): {labels}")
        renames = {}
        # Pass 1: move every existing status to a temporary high sort order to avoid collisions.
        for i, s in enumerate(current):
            patch("CampaignMemberStatus", s["Id"], {"SortOrder": 50 + i})
        # Pass 2: rename/flag statuses that map onto a position in the new set.
        used = set()
        for s in current:
            pos = OLD_TO_POSITION.get(s["Label"])
            if pos is None or pos >= len(target) or pos in used:
                continue
            # Sets without a 'before response' status map Received onto nothing.
            if pos == 1 and target[1][2]:
                continue
            label, is_default, responded = target[pos] if pos < 2 else next(t for t in target if t[2])
            idx = [t[0] for t in target].index(label)
            patch("CampaignMemberStatus", s["Id"], {"Label": label, "IsDefault": is_default,
                                                    "HasResponded": responded, "SortOrder": idx + 1})
            renames[s["Label"]] = label
            used.add(idx)
        # Pass 3: create the statuses that are still missing.
        for idx, (label, is_default, responded) in enumerate(target):
            if idx in used:
                continue
            r = sf("data", "create", "record", "-s", "CampaignMemberStatus", "-v",
                   f"CampaignId={cid} Label='{label}' IsDefault={str(is_default).lower()} "
                   f"HasResponded={str(responded).lower()} SortOrder={idx + 1}")
            print(f"   + {label}: {'ok' if r.get('status') == 0 else r.get('message')}")
        # Pass 4: members whose status text still holds an old label.
        for m in query(f"SELECT Id, Status FROM CampaignMember WHERE CampaignId = '{cid}'"):
            if m["Status"] in renames:
                patch("CampaignMember", m["Id"], {"Status": renames[m["Status"]]})
                print(f"   member {m['Id']}: {m['Status']} -> {renames[m['Status']]}")
        print(f"   renamed: {renames}")


if __name__ == "__main__":
    main()
