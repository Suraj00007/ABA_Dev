"""Generate the ABA Campaign configuration metadata (fields, validation rules, permission set,
Campaign Type values). Configuration only - no Apex, no LWC.

Usage (from the project root):
    python scripts/aba/build_campaign_model.py
"""
import os
from xml.sax.saxutils import escape as x

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "force-app", "main", "default")
HDR = '<?xml version="1.0" encoding="UTF-8"?>\n'
NS = 'xmlns="http://soap.sforce.com/2006/04/metadata"'

CAMPAIGN_TYPES = ["Event", "Social Media", "Sales Outreach", "Website", "Partner Portal", "Email", "Webinar"]
EVENT_COUNTRIES = ["Saudi Arabia", "United Arab Emirates", "Bahrain", "Qatar", "Kuwait", "Oman", "Egypt",
                   "Jordan", "India", "United Kingdom", "United States"]
MAPS_URL = "https://www.google.com/maps/search/?api=1&amp;query="


def write(rel, body):
    path = os.path.join(SRC, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HDR + body)
    print("wrote", rel)


def text_field(api, label, length, help_text):
    write(f"objects/Campaign/fields/{api}.field-meta.xml", f"""<CustomField {NS}>
    <fullName>{api}</fullName>
    <description>{x(help_text)} Used only when Type = Event.</description>
    <externalId>false</externalId>
    <inlineHelpText>{x(help_text)}</inlineHelpText>
    <label>{x(label)}</label>
    <length>{length}</length>
    <required>false</required>
    <trackHistory>false</trackHistory>
    <trackTrending>false</trackTrending>
    <type>Text</type>
    <unique>false</unique>
</CustomField>
""")


def formula_field(api, label, formula, help_text):
    write(f"objects/Campaign/fields/{api}.field-meta.xml", f"""<CustomField {NS}>
    <fullName>{api}</fullName>
    <description>{x(help_text)}</description>
    <externalId>false</externalId>
    <formula>{formula}</formula>
    <formulaTreatBlanksAs>BlankAsBlank</formulaTreatBlanksAs>
    <inlineHelpText>{x(help_text)}</inlineHelpText>
    <label>{x(label)}</label>
    <required>false</required>
    <trackHistory>false</trackHistory>
    <trackTrending>false</trackTrending>
    <type>Text</type>
    <unique>false</unique>
</CustomField>
""")


def main():
    # ---------------------------------------------------------------- fields
    text_field("Event_Venue__c", "Event Venue", 255, "Name of the venue, e.g. Riyadh International Convention & Exhibition Center.")
    text_field("Event_Street__c", "Event Street", 255, "Street address of the venue.")
    text_field("Event_City__c", "Event City", 80, "City where the event takes place. Required for Event campaigns.")
    text_field("Event_State__c", "Event State/Province", 80, "State, province or region (optional).")
    text_field("Event_Postal_Code__c", "Event Postal Code", 20, "Postal code (optional).")

    values = "\n".join(f"""            <value>
                <fullName>{x(v)}</fullName>
                <default>false</default>
                <label>{x(v)}</label>
            </value>""" for v in EVENT_COUNTRIES)
    write("objects/Campaign/fields/Event_Country__c.field-meta.xml", f"""<CustomField {NS}>
    <fullName>Event_Country__c</fullName>
    <description>Country where the event takes place. Required for Event campaigns; used to group events by geography in reports.</description>
    <externalId>false</externalId>
    <inlineHelpText>Country where the event takes place. Required for Event campaigns.</inlineHelpText>
    <label>Event Country</label>
    <required>false</required>
    <trackHistory>false</trackHistory>
    <trackTrending>false</trackTrending>
    <type>Picklist</type>
    <valueSet>
        <restricted>true</restricted>
        <valueSetDefinition>
            <sorted>false</sorted>
{values}
        </valueSetDefinition>
    </valueSet>
</CustomField>
""")

    # One-line address: each part followed by ", " when filled; country last (required for events).
    address = ("IF(ISPICKVAL(Type, &quot;Event&quot;),\n"
               "    IF(ISBLANK(Event_Venue__c), &quot;&quot;, Event_Venue__c &amp; &quot;, &quot;) &amp;\n"
               "    IF(ISBLANK(Event_Street__c), &quot;&quot;, Event_Street__c &amp; &quot;, &quot;) &amp;\n"
               "    IF(ISBLANK(Event_City__c), &quot;&quot;, Event_City__c &amp; &quot;, &quot;) &amp;\n"
               "    IF(ISBLANK(Event_State__c), &quot;&quot;, Event_State__c &amp; &quot;, &quot;) &amp;\n"
               "    IF(ISBLANK(Event_Postal_Code__c), &quot;&quot;, Event_Postal_Code__c &amp; &quot;, &quot;) &amp;\n"
               "    TEXT(Event_Country__c),\n"
               "    NULL\n)")
    formula_field("Event_Full_Address__c", "Event Address", address,
                  "Full event address on one line, built from the Event location fields. Blank unless Type = Event.")

    # Map link: exact pin from Location_Event__c when filled, otherwise a search on the address.
    link = ("IF(ISPICKVAL(Type, &quot;Event&quot;),\n"
            "    IF(NOT(ISBLANK(Location_Event__Latitude__s)),\n"
            f"        HYPERLINK(&quot;{MAPS_URL}&quot; &amp; TEXT(Location_Event__Latitude__s) &amp; &quot;,&quot; &amp; TEXT(Location_Event__Longitude__s), &quot;Open in Google Maps&quot;, &quot;_blank&quot;),\n"
            "        IF(ISBLANK(Event_City__c), NULL,\n"
            # URLENCODE is not allowed in formula fields: escape the characters that break a query string.
            f"            HYPERLINK(&quot;{MAPS_URL}&quot; &amp; SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(Event_Full_Address__c, &quot;&amp;&quot;, &quot;%26&quot;), &quot;#&quot;, &quot;%23&quot;), &quot; &quot;, &quot;+&quot;), &quot;Open in Google Maps&quot;, &quot;_blank&quot;))\n"
            "    ),\n"
            "    NULL\n)")
    formula_field("Event_Map_Link__c", "Event Map", link,
                  "Opens the event location in Google Maps: the exact pin when Location Event coordinates are filled, otherwise the address.")

    # ---------------------------------------------------------------- validation rules
    write("objects/Campaign/validationRules/Event_Location_Required.validationRule-meta.xml", f"""<ValidationRule {NS}>
    <fullName>Event_Location_Required</fullName>
    <active>true</active>
    <description>Event campaigns must have at least a city and a country so they can be mapped and reported by geography.</description>
    <errorConditionFormula>AND(
    ISPICKVAL(Type, &quot;Event&quot;),
    OR(
        ISBLANK(Event_City__c),
        ISPICKVAL(Event_Country__c, &quot;&quot;)
    )
)</errorConditionFormula>
    <errorMessage>An Event campaign needs at least an Event City and Event Country so it can be shown on the map.</errorMessage>
</ValidationRule>
""")
    write("objects/Campaign/validationRules/Event_Fields_Only_For_Events.validationRule-meta.xml", f"""<ValidationRule {NS}>
    <fullName>Event_Fields_Only_For_Events</fullName>
    <active>true</active>
    <description>Only Event campaigns are mapped geographically, so the event location fields must stay empty for every other type.</description>
    <errorConditionFormula>AND(
    NOT(ISPICKVAL(Type, &quot;Event&quot;)),
    OR(
        NOT(ISBLANK(Event_Venue__c)),
        NOT(ISBLANK(Event_Street__c)),
        NOT(ISBLANK(Event_City__c)),
        NOT(ISBLANK(Event_State__c)),
        NOT(ISBLANK(Event_Postal_Code__c)),
        NOT(ISPICKVAL(Event_Country__c, &quot;&quot;)),
        NOT(ISBLANK(Location_Event__Latitude__s))
    )
)</errorConditionFormula>
    <errorMessage>Event location fields can only be used when the campaign Type is Event. Clear them or change the Type to Event.</errorMessage>
</ValidationRule>
""")

    # ---------------------------------------------------------------- permission set
    editable = ["Event_Venue__c", "Event_Street__c", "Event_City__c", "Event_State__c", "Event_Postal_Code__c",
                "Event_Country__c", "Location_Event__c"]
    readonly = ["Event_Full_Address__c", "Event_Map_Link__c"]
    fls = "\n".join(f"""    <fieldPermissions>
        <editable>{'true' if f in editable else 'false'}</editable>
        <field>Campaign.{f}</field>
        <readable>true</readable>
    </fieldPermissions>""" for f in sorted(editable + readonly))
    write("permissionsets/ABA_Campaign_Manager.permissionset-meta.xml", f"""<PermissionSet {NS}>
    <description>Create and manage ABA campaigns and campaign members, including event location fields. Users also need the Marketing User checkbox on their user record.</description>
{fls}
    <hasActivationRequired>false</hasActivationRequired>
    <label>ABA Campaign Manager</label>
    <objectPermissions>
        <allowCreate>true</allowCreate>
        <allowDelete>false</allowDelete>
        <allowEdit>true</allowEdit>
        <allowRead>true</allowRead>
        <modifyAllRecords>false</modifyAllRecords>
        <object>Campaign</object>
        <viewAllRecords>false</viewAllRecords>
    </objectPermissions>
</PermissionSet>
""")
    write("permissionsets/ABA_Campaign_Viewer.permissionset-meta.xml", f"""<PermissionSet {NS}>
    <description>Read access to ABA campaign event location fields.</description>
{fls.replace('<editable>true</editable>', '<editable>false</editable>')}
    <hasActivationRequired>false</hasActivationRequired>
    <label>ABA Campaign Viewer</label>
</PermissionSet>
""")

    # ---------------------------------------------------------------- Campaign Type values
    vals = "\n".join(f"""    <standardValue>
        <fullName>{x(v)}</fullName>
        <default>false</default>
        <label>{x(v)}</label>
    </standardValue>""" for v in CAMPAIGN_TYPES)
    write("standardValueSets/CampaignType.standardValueSet-meta.xml", f"""<StandardValueSet {NS}>
    <sorted>false</sorted>
{vals}
</StandardValueSet>
""")


if __name__ == "__main__":
    main()
