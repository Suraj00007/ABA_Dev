# ABA Campaign Management – Implementation Plan

| | |
|---|---|
| **Org** | ABA_Dev (`00DgK00000bWvvVUAS`), Developer Edition, API v67.0 |
| **Author** | Suraj OD (Salesforce Technical Architect) |
| **Date** | 11 Oct 2026 |
| **Status** | **Built and deployed 11 Oct 2026** – approved with the constraint *configuration only (no Apex, no LWC)*. See **section 10 – As built** for what changed from this plan. |
| **Source** | ABA workshop decisions on campaign types, event mapping and campaign members |

---

## 1. Requirements

Three decisions came out of the workshop. Each is restated here with the interpretation this plan is built on.

| # | Workshop decision | Interpretation used in this plan |
|---|---|---|
| **R1** | Final campaign types: **Event, Social Media, Sales Outreach, Website, Partner Portal, Email, Webinar**. "Anything else?" | The standard `Campaign.Type` picklist is replaced with exactly these seven values. The 12 Salesforce default values are deactivated (never deleted). See decision **D1** on whether to add an *Other* value. |
| **R2** | "Only for the Event type geographically maps" | An **Event** campaign happens at a physical place, so it carries a venue and address and is **shown on a map** on the campaign record. The other six types are not location-bound, so the location fields and the map are hidden for them, and a rule stops location data being entered on them. The country and city also make events reportable by geography (Saudi Arabia / UAE / Bahrain). See **D2** if the intent was only regional reporting with no map. |
| **R3** | Campaign members are identified **based on either Lead or Contact** | This is standard Salesforce behaviour: a Campaign Member record links to **one** Lead *or* **one** Contact, and the standard **Member Type** field shows which. No new object or field is needed. The work is to make it usable: member statuses that fit each campaign type, the right permissions, and the member list showing Lead/Contact clearly. |

### Out of scope
- Campaign Influence (multi-touch attribution). Primary Campaign Source on Opportunity is standard and already feeds report R15.
- Marketing automation / email sending (Account Engagement, Marketing Cloud).
- Automatic geocoding of event addresses by Salesforce (Salesforce only geocodes standard Account/Contact/Lead addresses). The map geocodes the address itself when it renders; exact coordinates can optionally be typed in.

---

## 2. Current state of the org (findings)

| Area | Finding | Impact |
|---|---|---|
| `Campaign.Type` | 12 default values active: Conference, Webinar, Trade Show, Public Relations, Partners, Referral Program, Advertisement, Banner Ads, Direct Mail, Email, Telemarketing, Other | Replace with the 7 ABA values. *Webinar* and *Email* already exist and are kept. |
| Existing campaigns | 5 records: 4 Salesforce samples (Webinar, Conference, Direct Mail, Trade Show) + "test" (Conference) | Their Type must be migrated before old values are deactivated (section 6). |
| Campaign fields | No custom fields | Event location fields must be created. |
| Campaign page | No Lightning record page; the classic "Campaign Layout" is used | A Lightning record page is needed to show the map conditionally. |
| Campaign Member | Standard object with `LeadId`, `ContactId`, `Type` (Lead/Contact), `Status`. 2 members exist, both leads. 23 leads, 20 contacts in the org | Nothing missing. Configure statuses, permissions and related-list columns. |
| Member statuses | Default per campaign: Sent (default), Responded. Value set also has Planned, Received | Statuses are generic; an event needs Invited / Registered / Attended / No Show. |
| Sharing | Campaign org-wide default: Public Full Access | Fine for ABA's small team; unchanged. |
| Permissions | Standard User profile (Venkatesh, Alburayh): **Read only** on Campaign. **Marketing User** checkbox off for both | They cannot create campaigns or add members. Needs **D3**. |
| Custom Address Field setting | Disabled (beta) | Build the event address from individual fields, not a compound address. |
| Campaign Influence | Off | Stays off. |

---

## 3. Solution design

### 3.1 Data model

No new objects. All changes are on the standard **Campaign** object; **Campaign Member** is used as-is.

```
Lead ──────┐
           ├── Campaign Member ──── Campaign ──── (Event fields + map, only when Type = Event)
Contact ───┘        │                   │
                    │                   └── Opportunity.Primary Campaign Source  (standard, already used by R15)
                    └── Member Type = Lead | Contact  (standard field)
```

#### Campaign Type (standard picklist, `CampaignType` value set) – R1

| Value | Action | Note |
|---|---|---|
| Event | **Add** | Physical event – conference, seminar, trade show, customer day. Only type that is mapped. |
| Social Media | **Add** | |
| Sales Outreach | **Add** | Matches the *Sales Outreach* lead source already configured. |
| Website | **Add** | |
| Partner Portal | **Add** | SAP / partner-sourced campaigns. |
| Email | Keep | |
| Webinar | Keep | Online; not mapped. |
| Conference, Trade Show, Public Relations, Partners, Referral Program, Advertisement, Banner Ads, Direct Mail, Telemarketing, Other | **Deactivate** | Deactivated, not deleted, so history is preserved. |

#### New fields on Campaign – R2 (Event location)

| Field label | API name | Type | Details | Purpose |
|---|---|---|---|---|
| Event Venue | `Event_Venue__c` | Text (255) | e.g. "Riyadh International Convention & Exhibition Center" | Shown as the map marker title |
| Event Street | `Event_Street__c` | Text (255) | | Address line for the map |
| Event City | `Event_City__c` | Text (80) | | Required for Event (validation rule) |
| Event State/Province | `Event_State__c` | Text (80) | Optional | |
| Event Country | `Event_Country__c` | Picklist (restricted) | Saudi Arabia, United Arab Emirates, Bahrain, Qatar, Kuwait, Oman, Egypt, Jordan, India, United Kingdom, United States. Admin can add values. | Required for Event; groups events by geography in reports. See **D4**. |
| Event Postal Code | `Event_Postal_Code__c` | Text (20) | Optional | |
| Event Coordinates | `Event_Location__c` | Geolocation (6 decimals) | Optional latitude/longitude | If filled, the map pins the exact point instead of geocoding the address |
| Event Address | `Event_Full_Address__c` | Formula (Text) | `Venue, Street, City, State, Postal Code, Country` – blanks skipped | One-line address for list views, reports and the map label |
| Event Map Link | `Event_Map_Link__c` | Formula (Text, hyperlink) | `HYPERLINK("https://www.google.com/maps/search/?api=1&query=" & URLENCODE(address), "Open in Google Maps")`. Blank unless Type = Event. | Works on mobile, in reports and in emails, with no code |

Field-level security: granted through a new permission set (3.4). Fields are added to the page layout and the Lightning record page (3.3).

#### Validation rules on Campaign

| Rule | API name | Condition (error shown when true) | Message |
|---|---|---|---|
| Event location required | `Event_Location_Required` | `ISPICKVAL(Type,"Event") && (ISBLANK(Event_City__c) \|\| ISPICKVAL(Event_Country__c,""))` | "An Event campaign needs at least a city and country so it can be shown on the map." |
| Location only for events | `Event_Fields_Only_For_Events` | `NOT(ISPICKVAL(Type,"Event")) && (any Event field is filled)` | "Event location fields can only be used when the campaign type is Event. Clear them or change the type." |

Both rules are active from go-live. Rule 1 can be deactivated if ABA prefers soft guidance.

### 3.2 Map component – R2

A small Lightning Web Component, **`campaignEventMap`**, placed on the Campaign record page.

- Uses the standard `lightning-map` base component (Google Maps rendered by Salesforce; no API key, no external integration, no Remote Site Setting).
- Reads the Campaign record with `getRecord` (Lightning Data Service), so no Apex and no SOQL.
- Marker: title = Event Venue, location = `Event_Location__c` latitude/longitude when filled, otherwise the street / city / state / postal code / country fields (Google geocodes them when the map renders).
- Shows a friendly empty state ("Add a venue and address to see this event on the map") when the address is incomplete.
- **Visibility:** component visibility rule on the record page `Record > Type equals Event`, so the map only exists on Event campaigns. The component also checks the type itself as a second guard.
- Works in Lightning Experience and the Salesforce mobile app. Requires internet access to Google Maps from the browser.
- Jest test for the LWC is included in the project (the project already has Jest configured).

### 3.3 Campaign record page and layout

| Item | Change |
|---|---|
| **Campaign Layout** (page layout) | New section **Event Location** with the 9 event fields (coordinates read-only on mobile, map link read-only). Campaign Members related list columns: Name, **Member Type (Lead/Contact)**, Status, Company/Account, Title, Email, Phone. |
| **ABA Campaign Record Page** (new Lightning record page, `ABA_Campaign_Record_Page`) | Header: highlights panel (Type, Status, Start Date, End Date, Event City/Country). Left: Details tab (record detail) and Related tab (Campaign Members, Opportunities, Campaign Hierarchy). Right: **Event Map** (visible only when Type = Event), then Activity and Chatter. Assigned as the **org default** for Campaign so every app uses it. If Dynamic Forms is available for Campaign in this org, the Event Location section itself is also made visible only when Type = Event; otherwise the layout section stays visible and the validation rule enforces the restriction. |
| **Campaign Member Page Layout** | Member Type field added to the first section. |
| **Campaign list views** | New list view **Event Campaigns** (Type = Event) with Event City, Event Country, Start Date. Existing views untouched. |

### 3.4 Campaign members – R3

| Item | Design |
|---|---|
| Lead or Contact | Standard. A member is **either** a Lead **or** a Contact; the standard **Member Type** field says which. Members are added with the standard *Add Leads* / *Add Contacts* buttons on the campaign, from Lead/Contact list views, or from a report. |
| Lead conversion | Standard: when a Lead that is a campaign member is converted, its membership moves to the new Contact automatically. |
| Member statuses by campaign type | A record-triggered flow **`ABA Campaign – Set Member Statuses`** (after create, asynchronous path) renames the two system-created statuses and adds the rest, so each campaign starts with statuses that fit its type: |

| Campaign type | Statuses (default marked *, "responded" marked ✓) |
|---|---|
| Event | Invited*, Registered, Attended ✓, No Show |
| Webinar | Invited*, Registered, Attended ✓, No Show |
| Email | Sent*, Opened, Clicked ✓, Unsubscribed |
| Social Media | Reached*, Engaged ✓ |
| Website | Visited*, Form Submitted ✓ |
| Sales Outreach | Contacted*, Meeting Booked ✓, Not Interested |
| Partner Portal | Referred*, Qualified ✓, Rejected |

Statuses remain editable per campaign in the standard *Campaign Member Statuses* related list. Existing campaigns are not changed by the flow (create-only trigger); their statuses are migrated by script in section 6.

| Item | Design |
|---|---|
| Permission set **ABA Campaign Manager** | Create/Read/Edit on Campaign and Campaign Member; Read on Lead and Contact (already granted); edit on all event fields. Assigned per **D3**. |
| Marketing User checkbox | Salesforce also requires the user-level **Marketing User** checkbox to create campaigns and add members. It cannot be granted by a permission set; it is ticked on the users chosen in **D3**. |
| Reporting | Two reports added to *ABA Sales Reports*: **C01 Campaign Members by Campaign & Member Type** (Lead vs Contact, by status) and **C02 Event Campaigns by Country** (Event campaigns grouped by Event Country and City with members and won revenue). Existing R15 (Revenue by Lead Source & Campaign) starts showing data once opportunities carry a Primary Campaign Source (section 6). |

### 3.5 Components summary

| # | Type | API name | Action |
|---|---|---|---|
| 1 | StandardValueSet | `CampaignType` | Changed |
| 2–10 | CustomField ×9 | `Campaign.Event_*__c` | Created |
| 11–12 | ValidationRule ×2 | `Campaign.Event_Location_Required`, `Campaign.Event_Fields_Only_For_Events` | Created |
| 13 | LightningComponentBundle | `campaignEventMap` (+ Jest test) | Created |
| 14 | FlexiPage | `ABA_Campaign_Record_Page` | Created |
| 15 | Layout | `Campaign-Campaign Layout` | Changed |
| 16 | Layout | `CampaignMember-Campaign Member Page Layout` | Changed |
| 17 | ListView | `Campaign.Event_Campaigns` | Created |
| 18 | Flow | `ABA_Campaign_Set_Member_Statuses` | Created |
| 19 | PermissionSet | `ABA_Campaign_Manager` | Created |
| 20–21 | Report ×2 | `ABA_Sales_Reports/C01_…`, `C02_…` | Created |
| 22 | CustomObject (page assignment) | Campaign org-default record page | Changed |

All source is kept in this SFDX project and listed in `manifest/campaign-package.xml`.

---

## 4. Decisions needed before build

| # | Decision | Recommendation |
|---|---|---|
| **D1** | Add an **Other** campaign type? | **No.** Seven clear types keep campaign reporting clean. If a campaign does not fit, ABA raises it and a value is added (a two-minute admin change). |
| **D2** | Does "geographically maps" mean a **map on the record** (this plan), or only **regional reporting** with no map? | Build the map. The country/city fields give the regional reporting either way; the map adds the visual for event planning. If no map is wanted, component #13 is dropped and everything else stays. |
| **D3** | Who can **create campaigns and add members**? | Assign *ABA Campaign Manager* + Marketing User to **Suraj OD** and **Venkatesh Rethinasamy** (sales lead) now; Alburayh read-only. In ABA's own org this becomes the marketing/sales-ops users. |
| **D4** | Event Country as a **restricted picklist** (GCC + common countries, listed in 3.1) or **free text**? | Restricted picklist, for clean grouping in reports. Admins add values as needed. |
| **D5** | **Member status sets** per type (table in 3.4) – confirm wording. | As proposed; placeholder until ABA confirms. |
| **D6** | Load **sample campaign data** for the demo (section 6)? | Yes – 3 campaigns, ~12 members from existing leads/contacts, 6 ABA opportunities linked to campaigns so R15 and C01/C02 show data. |
| **D7** | Migration of the **5 existing campaigns** (section 6) – confirm mapping or delete them. | Map them; they are harmless demo records. |

---

## 5. Build and deployment sequence

Deployed in order so each step can be verified before the next. Each step is a separate `sf project deploy start`.

| Step | What | Verify |
|---|---|---|
| 0 | Retrieve current Campaign metadata into the project; back up the 5 campaigns and 2 members to `data/backup/` | Backup CSVs exist |
| 1 | Custom fields, formula fields, permission set | Fields visible in Object Manager; FLS granted |
| 2 | Migrate existing campaign Type values (section 6) | No campaign still on an old value |
| 3 | `CampaignType` value set (add 5, deactivate 10) | Picklist shows 7 values |
| 4 | Validation rules | Save an Event without a city → blocked; save an Email with a venue → blocked |
| 5 | Member-status flow (active) | Create an Event campaign → statuses Invited/Registered/Attended/No Show |
| 6 | LWC `campaignEventMap` + Jest tests passing locally | `npm test` green |
| 7 | Page layouts, Campaign Member layout, list view, Lightning record page + org-default assignment | Open an Event campaign → map shows the venue; open a Webinar → no map |
| 8 | Reports C01, C02 | Both run without error |
| 9 | Sample data (D6) and member-status migration for existing campaigns | Reports and R15 show campaign data |
| 10 | Permission set + Marketing User assignment (D3) | Venkatesh can create a campaign and add a lead and a contact |
| 11 | Deploy validation of `manifest/campaign-package.xml` (`--dry-run`) | All components succeed |

Estimated effort: about one working day including testing and documentation.

---

## 6. Data migration and sample data

**Existing campaigns (5) – Type mapping**

| Campaign | Current type | New type |
|---|---|---|
| GC Product Webinar – Jan 7, 2002 | Webinar | Webinar (unchanged) |
| User Conference – Jun 17-19, 2002 | Conference | Event |
| DM Campaign to Top Customers – Nov 12-23, 2001 | Direct Mail | Email |
| International Electrical Engineers Association Trade Show – Mar 4-5, 2002 | Trade Show | Event |
| test | Conference | Event |

Their member statuses are migrated by script to the type's status set (existing members keep a valid status: *Sent* → default, *Responded/Received* → responded status).

**Sample ABA campaigns (D6)**

| Campaign | Type | Location | Members | Linked opportunities |
|---|---|---|---|---|
| SAP Innovation Day Riyadh 2026 | Event | Riyadh International Convention & Exhibition Center, Riyadh, Saudi Arabia (with coordinates) | 4 contacts, 3 leads: Invited / Registered / Attended | 3 (Lead Source = Events & Campaigns) |
| SuccessFactors Webinar – Oct 2026 | Webinar | – | 3 contacts, 2 leads | 2 |
| Q4 Partner Portal – SAP Referrals | Partner Portal | – | 2 contacts | 1 |

Members come from the existing 20 contacts and 23 leads; no new people are created. The 6 opportunities are existing ABA records whose Lead Source is already *Events & Campaigns* or *Partner Referral*.

---

## 7. Test plan

| # | Test | Expected |
|---|---|---|
| T1 | Create campaign, Type = Event, no city | Blocked by `Event_Location_Required` |
| T2 | Create campaign, Type = Event, venue + city + country | Saved; map shows a marker at the venue; Event Map Link opens Google Maps |
| T3 | Same campaign, add latitude/longitude | Marker moves to the exact coordinates |
| T4 | Create campaign, Type = Email, fill Event Venue | Blocked by `Event_Fields_Only_For_Events` |
| T5 | Change an Event campaign to Webinar with location filled | Blocked until location is cleared; after clearing, the map disappears |
| T6 | Create one campaign per type | Member statuses match the table in 3.4 |
| T7 | Add a Lead and a Contact to the same campaign | Two members; Member Type shows Lead and Contact |
| T8 | Convert that Lead | Membership now points to the new Contact |
| T9 | Log in as Venkatesh (after D3) | Can create a campaign and add members; Alburayh can view only |
| T10 | Run C01, C02, R15 | Data returned, no errors |
| T11 | Mobile app: open Event campaign | Map renders; Event Map Link opens Google Maps |
| T12 | Jest: `npm test` | `campaignEventMap` tests pass |

---

## 8. Risks and notes

| Risk / note | Mitigation |
|---|---|
| Deactivating Type values while campaigns still use them | Migrate first (step 2), deactivate after (step 3). Deactivated values remain visible on old records. |
| System-created member statuses may not yet exist when the flow runs | Flow uses an **asynchronous** path, which runs after the campaign and its default statuses are committed. Verified in step 5. |
| Google Maps geocoding of a vague address can land on the wrong spot | Venue + street + city + country gives a good result; coordinates can be typed in for precision. |
| Marketing User is a user checkbox, not a permission set | Documented in D3; must be ticked for each campaign user in ABA's org too. |
| Dynamic Forms support for Campaign depends on the release | Checked during step 7; the layout section + validation rule is the fallback and gives the same behaviour. |
| Developer Edition licence limit | No new users needed for this feature. |

**Rollback:** deactivate the flow and validation rules, reassign the default Campaign page, reactivate the old Type values, restore campaign Types from the backup CSV. Fields can be deleted (restorable for 15 days).

---

## 9. Open questions carried from the workshop

1. "Anything else?" on campaign types – see **D1**.
2. Does ABA run virtual or hybrid events? If yes, an *Event Format* (In Person / Virtual / Hybrid) field can be added later and the map hidden for virtual events.
3. Should event attendance feed Lead Status (e.g. Attended → Working – Contacted)? Not in scope; can be a follow-up flow.

---

## 10. As built (11 Oct 2026)

Approval received with one constraint: **configuration only – no Apex and no LWC**. Decisions D1–D7 were applied as recommended; the map approach was chosen separately (no permanent org setting).

### 10.1 Changes from the plan

| Plan item | As built | Why |
|---|---|---|
| LWC `campaignEventMap` showing an inline map | **Removed.** Replaced by the formula field **Event Map** (`Event_Map_Link__c`) – an "Open in Google Maps" link – shown in an **Event Map** card in the record-page sidebar and in the Event Location section. | No-code constraint. The inline map for address fields would need the permanent *Custom Address Fields* setting; you chose the link instead. |
| New field `Event_Location__c` (Geolocation) | **Reused your existing field `Location_Event__c`** (Geolocation, 4 decimals, created 11 Oct 2026). | Avoids a duplicate field. When it is filled, the map link pins the exact coordinates; otherwise it searches the address. |
| `URLENCODE` in the map link formula | `SUBSTITUTE` escapes `&`, `#` and spaces. | `URLENCODE` is not allowed in formula fields. |
| Permission set ABA Campaign Manager only | Added **ABA Campaign Viewer** (read-only on event fields) for Mohammed Alburayh. | He needs field access to see event locations (D3: read-only). |
| Jest tests (T12) | Not applicable. | No code was written. |
| Dynamic Forms fallback | Not needed – Campaign supports Dynamic Forms in this org. | The Event Location section and Event Map card are hidden unless Type = Event. |

### 10.2 Components deployed

| Type | API name | Action |
|---|---|---|
| StandardValueSet | `CampaignType` | Changed – 7 active values; 10 old values deactivated |
| CustomField ×8 | `Campaign.Event_Venue__c`, `Event_Street__c`, `Event_City__c`, `Event_State__c`, `Event_Postal_Code__c`, `Event_Country__c` (restricted picklist, 11 countries), `Event_Full_Address__c` (formula), `Event_Map_Link__c` (formula hyperlink) | Created |
| CustomField | `Campaign.Location_Event__c` | Existing – reused, added to the Event Location section |
| ValidationRule ×2 | `Campaign.Event_Location_Required`, `Campaign.Event_Fields_Only_For_Events` | Created, active |
| Flow | `ABA_Campaign_Set_Member_Statuses` (record-triggered, after create, asynchronous path) | Created, active |
| PermissionSet ×2 | `ABA_Campaign_Manager`, `ABA_Campaign_Viewer` | Created |
| FlexiPage | `ABA_Campaign_Record_Page` (Dynamic Forms) | Created; org default for Campaign on desktop and phone |
| Layout | `Campaign-Campaign Layout` | Changed – Event Location section (used by the New Campaign form); `Location_Event__c` moved into it |
| ListView | `Campaign.Event_Campaigns` | Created |
| Report ×2 | `ABA_Sales_Reports/C01_Campaign_Members_by_Member_Type`, `C02_Event_Campaigns_by_Country` | Created |

Manifest: `manifest/campaign-package.xml` (validated: 20/20 components, 0 errors). The page assignment lives in `objects/Campaign/Campaign.object-meta.xml` (View overrides, Large and Small).
Generators: `scripts/aba/build_campaign_model.py`, `build_campaign_flow.py`, `build_campaign_page.py`.

### 10.3 Data changes

| Change | Detail |
|---|---|
| Backup | `data/backup/campaigns_backup_2026-10-11.csv`, `campaign_members_backup_2026-10-11.csv`, `campaign_member_status_backup_2026-10-11.csv` |
| Existing campaigns – Type | User Conference → Event; DM Campaign → Email; IEEA Trade Show → Event; test → Event; GC Product Webinar unchanged |
| Existing campaigns – member statuses | Migrated to each type's status set (`scripts/aba/migrate_campaign_statuses.py`); the 2 existing members moved Sent → Invited and Received → Registered |
| Sample campaigns | **SAP Innovation Day Riyadh 2026** (Event, Riyadh, 7 members, 3 opportunities); **SuccessFactors Webinar – Oct 2026** (Webinar, 5 members, 1 opportunity); **SAP Partner Portal Referrals 2026** (Partner Portal, 2 members, 4 opportunities incl. 3 won = 2.85M) – `scripts/aba/load_campaign_sample_data.py` |
| Opportunities | 8 existing ABA opportunities now have a Primary Campaign Source (lead source matches the campaign type). Report R15 now shows the Partner Portal campaign under *Partner Referral*. |
| Users | Venkatesh + Suraj: ABA Campaign Manager. Alburayh: ABA Campaign Viewer. |

### 10.4 Test results

| # | Result |
|---|---|
| T1 Event without city/country | **Pass** – blocked |
| T2 Event with address → address + map link | **Pass** (after fixing blank-coordinate handling) |
| T3 Coordinates → exact pin | **Pass** |
| T4 Email with a venue | **Pass** – blocked |
| T5 Event → Webinar with location filled | **Pass** – blocked |
| T6 Member statuses for all 7 types | **Pass** – all 7 match section 3.4 |
| T7 Lead and Contact on the same campaign | **Pass** – Member Type Lead / Contact; default status applied; Attended counts as a response |
| T8 Lead conversion moves membership | **Not run** – standard Salesforce behaviour; verify by converting a lead in the UI |
| T9 Venkatesh can create campaigns | **Blocked** – see 10.5 |
| T10 Reports C01, C02, R15 | **Pass** |
| T11 Mobile | **Not run** – page is assigned to phone; verify in the Salesforce mobile app |
| UI check (browser) | **Pass** – Event campaign shows the Event Location section and Event Map card; Webinar shows neither; Campaign Members list shows Type (Lead/Contact) and Status |

### 10.5 Open items

1. **Marketing User licence (blocks T9).** Ticking *Marketing User* on Venkatesh failed with *License Limit Exceeded*. Both Marketing User licences in this Developer Edition are used (Suraj OD and OrgFarm EPIC). To let Venkatesh create campaigns, untick Marketing User on OrgFarm EPIC (Setup → Users) and tick it on Venkatesh. In ABA's own org this depends on its licence count.
2. **Three older Event campaigns have no location** (User Conference, IEEA Trade Show, test). They show under "–" in C02 and must get an Event City and Event Country the next time they are edited (validation rule).
3. **Event Country values** (11 countries) and **member status wording** remain placeholders until ABA confirms.
