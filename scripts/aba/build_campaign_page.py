"""Generate the Campaign Lightning record page (Dynamic Forms), the Event Campaigns list view, the
page-layout Event Location section, and the org-default page assignment. Configuration only.

Usage (from the project root):
    python scripts/aba/build_campaign_page.py
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "force-app", "main", "default")
HDR = '<?xml version="1.0" encoding="UTF-8"?>\n'
NS = 'xmlns="http://soap.sforce.com/2006/04/metadata"'
PAGE = "ABA_Campaign_Record_Page"

EVENT_FIELDS_LEFT = ["Event_Venue__c", "Event_Street__c", "Event_City__c", "Event_State__c"]
EVENT_FIELDS_RIGHT = ["Event_Postal_Code__c", "Event_Country__c", "Location_Event__c", "Event_Map_Link__c"]

# section key -> (label, left column, right column, visible only for Event?)
SECTIONS = [
    ("info", "Campaign Information",
     [("Name", "required"), ("Type", "none"), ("Status", "none"), ("IsActive", "none"), ("ParentId", "none"), ("OwnerId", "none")],
     [("StartDate", "none"), ("EndDate", "none"), ("ExpectedRevenue", "none"), ("BudgetedCost", "none"),
      ("ActualCost", "none"), ("ExpectedResponse", "none"), ("NumberSent", "none")], False),
    ("event", "Event Location",
     [(f, "none") for f in EVENT_FIELDS_LEFT], [(f, "readonly" if f == "Event_Map_Link__c" else "none") for f in EVENT_FIELDS_RIGHT], True),
    ("results", "Campaign Results",
     [("NumberOfLeads", "readonly"), ("NumberOfConvertedLeads", "readonly"), ("NumberOfContacts", "readonly"), ("NumberOfResponses", "readonly")],
     [("NumberOfOpportunities", "readonly"), ("NumberOfWonOpportunities", "readonly"), ("AmountAllOpportunities", "readonly"),
      ("AmountWonOpportunities", "readonly")], False),
    ("desc", "Description", [("Description", "none")], [], False),
    ("system", "System Information", [("CreatedById", "readonly")], [("LastModifiedById", "readonly")], False),
]
SIDEBAR_EVENT = ("map", "Event Map", [("Event_Full_Address__c", "readonly"), ("Event_Map_Link__c", "readonly")], [], True)

EVENT_RULE = """
                <visibilityRule>
                    <criteria>
                        <leftValue>{!Record.Type}</leftValue>
                        <operator>EQUAL</operator>
                        <rightValue>Event</rightValue>
                    </criteria>
                </visibilityRule>"""


def prop(name, value):
    return f"""                <componentInstanceProperties>
                    <name>{name}</name>
                    <value>{value}</value>
                </componentInstanceProperties>"""


def region(name, items, rtype="Facet"):
    return f"""    <flexiPageRegions>
{chr(10).join(items)}
        <name>{name}</name>
        <type>{rtype}</type>
    </flexiPageRegions>"""


def component(name, ident, props, rule=""):
    return f"""        <itemInstances>
            <componentInstance>
{chr(10).join(prop(k, v) for k, v in props)}
                <componentName>{name}</componentName>
                <identifier>{ident}</identifier>{rule}
            </componentInstance>
        </itemInstances>"""


def field(api, behavior, key):
    return f"""        <itemInstances>
            <fieldInstance>
                <fieldInstanceProperties>
                    <name>uiBehavior</name>
                    <value>{behavior}</value>
                </fieldInstanceProperties>
                <fieldItem>Record.{api}</fieldItem>
                <identifier>RecordField_{key}_{api.replace('__c', '')}</identifier>
            </fieldInstance>
        </itemInstances>"""


def field_section(key, label, left, right, event_only, regions):
    """Append the facets for one Dynamic Forms section; return the section component XML."""
    cols = []
    for i, fields in enumerate([left, right] if right else [left], 1):
        facet = f"Facet-{key}-col{i}"
        regions.append(region(facet, [field(f, b, key) for f, b in fields]))
        cols.append(component("flexipage:column", f"flexipage_column_{key}_{i}", [("body", facet)]))
    regions.append(region(f"Facet-{key}-columns", cols))
    return component("flexipage:fieldSection", f"flexipage_fieldSection_{key}",
                     [("columns", f"Facet-{key}-columns"), ("horizontalAlignment", "false"), ("label", label)],
                     EVENT_RULE if event_only else "")


def build_page():
    regions = []
    header = region("header", [component("force:highlightsPanel", "force_highlightsPanel", [
        ("collapsed", "false"), ("enableActionsConfiguration", "false"), ("enableActionsInNative", "false"),
        ("hideChatterActions", "false"), ("numVisibleActions", "3")])], "Region")

    detail_sections = [field_section(*s, regions) for s in SECTIONS]
    regions.append(region("detailTabContent", detail_sections))
    regions.append(region("relatedTabContent", [component("force:relatedListContainer", "force_relatedListContainer", [
        ("relatedListComponentOverride", "NONE"), ("rowsToDisplay", "10"), ("showActionBar", "true")])]))
    regions.append(region("maintabs", [
        component("flexipage:tab", "detailTab", [("active", "true"), ("body", "detailTabContent"), ("title", "Standard.Tab.detail")]),
        component("flexipage:tab", "relatedListsTab", [("body", "relatedTabContent"), ("title", "Standard.Tab.relatedLists")]),
    ]))
    main = region("main", [component("flexipage:tabset", "flexipage_tabset", [("label", "Tabs"), ("tabs", "maintabs")])], "Region")

    map_section = field_section(*SIDEBAR_EVENT, regions)
    regions.append(region("activityTabContent", [component("runtime_sales_activities:activityPanel",
                                                           "runtime_sales_activities_activityPanel",
                                                           [("showLegacyActivityComposer", "false")])]))
    regions.append(region("feedTabContent", [component("forceChatter:recordFeedContainer", "forceChatter_recordFeedContainer", [])]))
    regions.append(region("sidebartabs", [
        component("flexipage:tab", "activityTab", [("active", "true"), ("body", "activityTabContent"), ("title", "Standard.Tab.activity")]),
        component("flexipage:tab", "collaborateTab", [("body", "feedTabContent"), ("title", "Standard.Tab.collaborate")]),
    ]))
    sidebar = region("sidebar", [map_section, component("flexipage:tabset", "flexipage_tabset2",
                                                        [("label", "Tabs"), ("tabs", "sidebartabs")])], "Region")

    body = "\n".join([header] + regions + [main, sidebar])
    with open(os.path.join(SRC, "flexipages", f"{PAGE}.flexipage-meta.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(HDR + f"""<FlexiPage {NS}>
{body}
    <description>ABA Campaign record page (Dynamic Forms). The Event Location section and the Event Map card are shown only when Type = Event.</description>
    <masterLabel>ABA Campaign Record Page</masterLabel>
    <sobjectType>Campaign</sobjectType>
    <template>
        <name>flexipage:recordHomeTemplateDesktop</name>
    </template>
    <type>RecordPage</type>
</FlexiPage>
""")
    print("wrote flexipage", PAGE)


def build_list_view():
    cols = ["CAMPAIGN.NAME", "CAMPAIGN.START_DATE", "CAMPAIGN.STATUS", "Event_Venue__c", "Event_City__c",
            "Event_Country__c", "CAMPAIGN.NUM_LEADS", "CAMPAIGN.NUM_CONTACTS", "Event_Map_Link__c"]
    c = "\n".join(f"    <columns>{col}</columns>" for col in cols)
    with open(os.path.join(SRC, "objects", "Campaign", "listViews", "Event_Campaigns.listView-meta.xml"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(HDR + f"""<ListView {NS}>
    <fullName>Event_Campaigns</fullName>
{c}
    <filterScope>Everything</filterScope>
    <filters>
        <field>CAMPAIGN.CAMPAIGN_TYPE</field>
        <operation>equals</operation>
        <value>Event</value>
    </filters>
    <label>Event Campaigns</label>
</ListView>
""")
    print("wrote list view Event_Campaigns")


def update_layout():
    path = os.path.join(SRC, "layouts", "Campaign-Campaign Layout.layout-meta.xml")
    with open(path, encoding="utf-8") as f:
        xml = f.read()
    if "Event_Venue__c" in xml:
        return

    def items(fields, readonly=()):
        return "".join(f"""
            <layoutItems>
                <behavior>{'Readonly' if f in readonly else 'Edit'}</behavior>
                <field>{f}</field>
            </layoutItems>""" for f in fields)
    section = f"""    <layoutSections>
        <customLabel>true</customLabel>
        <detailHeading>true</detailHeading>
        <editHeading>true</editHeading>
        <label>Event Location (Event campaigns only)</label>
        <layoutColumns>{items(EVENT_FIELDS_LEFT)}
        </layoutColumns>
        <layoutColumns>{items(EVENT_FIELDS_RIGHT, readonly=("Event_Map_Link__c",))}
        </layoutColumns>
        <style>TwoColumnsTopToBottom</style>
    </layoutSections>
"""
    # Insert right after the first section (Campaign Information).
    idx = xml.index("</layoutSections>") + len("</layoutSections>\n")
    xml = xml[:idx] + section + xml[idx:]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    print("updated Campaign Layout")


def assign_org_default():
    path = os.path.join(SRC, "objects", "Campaign", "Campaign.object-meta.xml")
    with open(path, encoding="utf-8") as f:
        xml = f.read()
    if PAGE in xml:
        return
    # Replace the existing View override(s) (one per form factor) with the Flexipage.
    def repl(m):
        block = m.group(0)
        if "<actionName>View</actionName>" not in block:
            return block
        form = re.search(r"<formFactor>(\w+)</formFactor>", block)
        if not form:  # the Classic override cannot use a Lightning page
            return block
        ff = f"\n        <formFactor>{form.group(1)}</formFactor>"
        return f"""<actionOverrides>
        <actionName>View</actionName>
        <comment>ABA Campaign record page (org default)</comment>
        <content>{PAGE}</content>{ff}
        <skipRecordTypeSelect>false</skipRecordTypeSelect>
        <type>Flexipage</type>
    </actionOverrides>"""
    new = re.sub(r"<actionOverrides>[\s\S]*?</actionOverrides>", repl, xml)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print("assigned org default View override")


if __name__ == "__main__":
    build_page()
    build_list_view()
    update_layout()
    assign_org_default()
