"""Generate the record-triggered flow that sets Campaign Member Statuses by Campaign Type.

Salesforce creates two statuses on every new campaign: 'Sent' (default, sort 1) and 'Responded'
(responded, sort 2). The flow renames them for the campaign's type, moves the responded status to
sort 3, and adds up to two more statuses (sort 2 = before the response, sort 4 = after it).

Usage (from the project root):
    python scripts/aba/build_campaign_flow.py
"""
import os
from xml.sax.saxutils import escape as x

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "force-app", "main", "default", "flows", "ABA_Campaign_Set_Member_Statuses.flow-meta.xml")

# type(s) -> (default status, responded status, extra before response, extra after response)
STATUS_SETS = [
    ("Event_or_Webinar", "Event or Webinar", ["Event", "Webinar"], ("Invited", "Attended", "Registered", "No Show")),
    ("Email", "Email", ["Email"], ("Sent", "Clicked", "Opened", "Unsubscribed")),
    ("Social_Media", "Social Media", ["Social Media"], ("Reached", "Engaged", None, None)),
    ("Website", "Website", ["Website"], ("Visited", "Form Submitted", None, None)),
    ("Sales_Outreach", "Sales Outreach", ["Sales Outreach"], ("Contacted", "Meeting Booked", None, "Not Interested")),
    ("Partner_Portal", "Partner Portal", ["Partner Portal"], ("Referred", "Qualified", None, "Rejected")),
]
VARS = ["varDefaultLabel", "varRespondedLabel", "varExtraBeforeLabel", "varExtraAfterLabel"]


def value(v):
    return f"<value>\n                <stringValue>{x(v)}</stringValue>\n            </value>"


def main():
    assignments, rules = [], []
    for api, lbl, types, labels in STATUS_SETS:
        conds = "".join(f"""
            <conditions>
                <leftValueReference>$Record.Type</leftValueReference>
                <operator>EqualTo</operator>
                <rightValue>
                    <stringValue>{x(t)}</stringValue>
                </rightValue>
            </conditions>""" for t in types)
        rules.append(f"""        <rules>
            <name>{api}</name>
            <conditionLogic>or</conditionLogic>{conds}
            <connector>
                <targetReference>Set_Labels_{api}</targetReference>
            </connector>
            <label>{x(lbl)}</label>
        </rules>""")
        items = "".join(f"""
        <assignmentItems>
            <assignToReference>{var}</assignToReference>
            <operator>Assign</operator>
            {value(v)}
        </assignmentItems>""" for var, v in zip(VARS, labels) if v)
        assignments.append(f"""    <assignments>
        <name>Set_Labels_{api}</name>
        <label>Set Labels – {x(lbl)}</label>
        <locationX>0</locationX>
        <locationY>0</locationY>{items}
        <connector>
            <targetReference>Rename_Default_Status</targetReference>
        </connector>
    </assignments>""")

    def create(name, label, var, sort, nxt):
        conn = f"""
        <connector>
            <targetReference>{nxt}</targetReference>
        </connector>""" if nxt else ""
        return f"""    <recordCreates>
        <name>{name}</name>
        <label>{label}</label>
        <locationX>0</locationX>
        <locationY>0</locationY>{conn}
        <inputAssignments>
            <field>CampaignId</field>
            <value>
                <elementReference>$Record.Id</elementReference>
            </value>
        </inputAssignments>
        <inputAssignments>
            <field>HasResponded</field>
            <value>
                <booleanValue>false</booleanValue>
            </value>
        </inputAssignments>
        <inputAssignments>
            <field>IsDefault</field>
            <value>
                <booleanValue>false</booleanValue>
            </value>
        </inputAssignments>
        <inputAssignments>
            <field>Label</field>
            <value>
                <elementReference>{var}</elementReference>
            </value>
        </inputAssignments>
        <inputAssignments>
            <field>SortOrder</field>
            <value>
                <numberValue>{sort}</numberValue>
            </value>
        </inputAssignments>
        <object>CampaignMemberStatus</object>
        <storeOutputAutomatically>true</storeOutputAutomatically>
    </recordCreates>"""

    def has_value(name, label, var, yes, no):
        no_conn = f"""
        <defaultConnector>
            <targetReference>{no}</targetReference>
        </defaultConnector>""" if no else ""
        return f"""    <decisions>
        <name>{name}</name>
        <label>{label}</label>
        <locationX>0</locationX>
        <locationY>0</locationY>{no_conn}
        <defaultConnectorLabel>No</defaultConnectorLabel>
        <rules>
            <name>{name}_Yes</name>
            <conditionLogic>and</conditionLogic>
            <conditions>
                <leftValueReference>{var}</leftValueReference>
                <operator>IsNull</operator>
                <rightValue>
                    <booleanValue>false</booleanValue>
                </rightValue>
            </conditions>
            <connector>
                <targetReference>{yes}</targetReference>
            </connector>
            <label>Yes</label>
        </rules>
    </decisions>"""

    variables = "\n".join(f"""    <variables>
        <name>{v}</name>
        <dataType>String</dataType>
        <isCollection>false</isCollection>
        <isInput>false</isInput>
        <isOutput>false</isOutput>
    </variables>""" for v in VARS)

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>67.0</apiVersion>
{chr(10).join(assignments)}
    <decisions>
        <name>Campaign_Type</name>
        <label>Campaign Type</label>
        <locationX>0</locationX>
        <locationY>0</locationY>
        <defaultConnectorLabel>Other type</defaultConnectorLabel>
{chr(10).join(rules)}
    </decisions>
{has_value("Has_Extra_Before", "Has a status before the response?", "varExtraBeforeLabel", "Create_Extra_Before_Status", "Has_Extra_After")}
{has_value("Has_Extra_After", "Has a status after the response?", "varExtraAfterLabel", "Create_Extra_After_Status", None)}
    <description>Sets the Campaign Member Statuses of a new campaign to fit its Type (configuration only). Event/Webinar: Invited*, Registered, Attended (responded), No Show. Email: Sent*, Opened, Clicked (responded), Unsubscribed. Social Media: Reached*, Engaged (responded). Website: Visited*, Form Submitted (responded). Sales Outreach: Contacted*, Meeting Booked (responded), Not Interested. Partner Portal: Referred*, Qualified (responded), Rejected. Runs on the asynchronous path so the two system-created statuses already exist.</description>
    <environments>Default</environments>
    <interviewLabel>ABA Campaign - Set Member Statuses {{!$Flow.CurrentDateTime}}</interviewLabel>
    <label>ABA Campaign - Set Member Statuses</label>
    <processMetadataValues>
        <name>BuilderType</name>
        <value>
            <stringValue>LightningFlowBuilder</stringValue>
        </value>
    </processMetadataValues>
    <processMetadataValues>
        <name>CanvasMode</name>
        <value>
            <stringValue>AUTO_LAYOUT_CANVAS</stringValue>
        </value>
    </processMetadataValues>
    <processMetadataValues>
        <name>OriginBuilderType</name>
        <value>
            <stringValue>LightningFlowBuilder</stringValue>
        </value>
    </processMetadataValues>
    <processType>AutoLaunchedFlow</processType>
{create("Create_Extra_Before_Status", "Create Status Before Response", "varExtraBeforeLabel", 2, "Has_Extra_After")}
{create("Create_Extra_After_Status", "Create Status After Response", "varExtraAfterLabel", 4, None)}
    <recordUpdates>
        <name>Rename_Default_Status</name>
        <label>Rename Default Status</label>
        <locationX>0</locationX>
        <locationY>0</locationY>
        <connector>
            <targetReference>Rename_Responded_Status</targetReference>
        </connector>
        <filterLogic>and</filterLogic>
        <filters>
            <field>CampaignId</field>
            <operator>EqualTo</operator>
            <value>
                <elementReference>$Record.Id</elementReference>
            </value>
        </filters>
        <filters>
            <field>IsDefault</field>
            <operator>EqualTo</operator>
            <value>
                <booleanValue>true</booleanValue>
            </value>
        </filters>
        <inputAssignments>
            <field>Label</field>
            <value>
                <elementReference>varDefaultLabel</elementReference>
            </value>
        </inputAssignments>
        <object>CampaignMemberStatus</object>
    </recordUpdates>
    <recordUpdates>
        <name>Rename_Responded_Status</name>
        <label>Rename Responded Status</label>
        <locationX>0</locationX>
        <locationY>0</locationY>
        <connector>
            <targetReference>Has_Extra_Before</targetReference>
        </connector>
        <filterLogic>and</filterLogic>
        <filters>
            <field>CampaignId</field>
            <operator>EqualTo</operator>
            <value>
                <elementReference>$Record.Id</elementReference>
            </value>
        </filters>
        <filters>
            <field>HasResponded</field>
            <operator>EqualTo</operator>
            <value>
                <booleanValue>true</booleanValue>
            </value>
        </filters>
        <inputAssignments>
            <field>Label</field>
            <value>
                <elementReference>varRespondedLabel</elementReference>
            </value>
        </inputAssignments>
        <inputAssignments>
            <field>SortOrder</field>
            <value>
                <numberValue>3</numberValue>
            </value>
        </inputAssignments>
        <object>CampaignMemberStatus</object>
    </recordUpdates>
    <start>
        <locationX>0</locationX>
        <locationY>0</locationY>
        <filterLogic>and</filterLogic>
        <filters>
            <field>Type</field>
            <operator>IsNull</operator>
            <value>
                <booleanValue>false</booleanValue>
            </value>
        </filters>
        <object>Campaign</object>
        <recordTriggerType>Create</recordTriggerType>
        <scheduledPaths>
            <name>Set_Statuses_After_Commit</name>
            <connector>
                <targetReference>Campaign_Type</targetReference>
            </connector>
            <pathType>AsyncAfterCommit</pathType>
        </scheduledPaths>
        <triggerType>RecordAfterSave</triggerType>
    </start>
    <status>Active</status>
{variables}
</Flow>
"""
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
