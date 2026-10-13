"""Generate ABA opportunity reports, dashboards and the Sales app Home page as metadata.

Source of truth: 'ABA Opportunity Reports & Dashboards - Demo Build Guide.xlsx'
(sheets 2. Report Catalog and 3. Dashboards).

Usage (from the project root):
    python scripts/aba/build_reports.py
    sf project deploy start -x manifest/aba-package.xml -o ABA_Dev
"""
import os
from xml.sax.saxutils import escape as x

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "force-app", "main", "default")
HDR = '<?xml version="1.0" encoding="UTF-8"?>\n'
NS = 'xmlns="http://soap.sforce.com/2006/04/metadata"'

RUNNING_USER = "suraj.od.885d11d47e1b@agentforce.com"
QUARTERLY_TARGET = 5000000  # manual value - quotas are kept outside Salesforce

MGMT = "ABA_Management_Reports"
SALES = "ABA_Sales_Reports"
DASH_FOLDER = "ABA_Management_Dashboards"

# Report column API names (Opportunity report type)
OPP, ACC, OWNER = "OPPORTUNITY_NAME", "ACCOUNT_NAME", "FULL_NAME"
AMT, CLOSE, STAGE = "AMOUNT", "CLOSE_DATE", "STAGE_NAME"
REASON, DETAILS = "Opportunity.Win_Loss_Reason__c", "Opportunity.Win_Loss_Details__c"
PROPOSAL, DEFERRED = "Opportunity.Proposal_Submission_Date__c", "Opportunity.Deferred_Date__c"
CLOSE_QTR = "Opportunity.Close_Quarter__c"
NOT_ACTIVE = "Deferred,Old / Archived"

written = {"Report": [], "Dashboard": []}


def write(rel, body):
    path = os.path.join(SRC, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(HDR + body)


def tag(name, value, ind):
    return f"{' ' * ind}<{name}>{x(str(value))}</{name}>"


# --------------------------------------------------------------------------- reports
def crit(column, operator, value):
    return (column, operator, value)


def report(dev, folder, name, fmt, *, columns, desc, down=(), across=(), filters=(), logic=None,
           open_status="all", interval="INTERVAL_CUSTOM", date_col=CLOSE, formula=None,
           chart=None, row_limit=None, sort=None):
    """columns: list of field or (field, aggregate). down/across: list of field or (field, granularity) or dict."""
    assert len(name) <= 40, f"report name too long ({len(name)}): {name}"
    out = [f"<Report {NS}>"]
    if formula:
        label, calc = formula
        out.append(f"""    <aggregates>
        <calculatedFormula>{x(calc)}</calculatedFormula>
        <datatype>percent</datatype>
        <developerName>FORMULA1</developerName>
        <isActive>true</isActive>
        <isCrossBlock>false</isCrossBlock>
        <masterLabel>{x(label)}</masterLabel>
        <scale>0</scale>
    </aggregates>""")
    if chart:
        out.append(chart_xml(**chart))
    for c in columns:
        field, agg = (c if isinstance(c, tuple) else (c, None))
        aggs = f"\n        <aggregateTypes>{agg}</aggregateTypes>" if agg else ""
        out.append(f"    <columns>{aggs}\n        <field>{field}</field>\n    </columns>")
    out.append(tag("description", desc, 4))
    if filters:
        items = "".join(f"""
        <criteriaItems>
            <column>{c}</column>
            <columnToColumn>false</columnToColumn>
            <isUnlocked>true</isUnlocked>
            <operator>{op}</operator>
            <value>{x(v)}</value>
        </criteriaItems>""" for c, op, v in filters)
        bl = f"\n        <booleanFilter>{logic}</booleanFilter>" if logic else ""
        out.append(f"    <filter>{bl}{items}\n        <language>en_US</language>\n    </filter>")
    out.append(tag("format", fmt, 4))
    for kind, groups in (("groupingsAcross", across), ("groupingsDown", down)):
        for g in groups:
            if isinstance(g, dict):
                gd = g
            else:
                field, gran = (g if isinstance(g, tuple) else (g, "None"))
                gd = {"field": field, "dateGranularity": gran, "sortOrder": "Asc"}
            parts = []
            if "aggregateType" in gd:
                parts.append(tag("aggregateType", gd["aggregateType"], 8))
            parts.append(tag("dateGranularity", gd.get("dateGranularity", "None"), 8))
            parts.append(tag("field", gd["field"], 8))
            if "sortByName" in gd:
                parts.append(tag("sortByName", gd["sortByName"], 8))
            parts.append(tag("sortOrder", gd.get("sortOrder", "Asc"), 8))
            if "sortType" in gd:
                parts.append(tag("sortType", gd["sortType"], 8))
            out.append(f"    <{kind}>\n" + "\n".join(parts) + f"\n    </{kind}>")
    out.append(tag("name", name, 4))
    out.append(f"    <params>\n        <name>co</name>\n        <value>1</value>\n    </params>")
    out.append(f"    <params>\n        <name>open</name>\n        <value>{open_status}</value>\n    </params>")
    out.append(tag("reportType", "Opportunity", 4))
    if row_limit:
        out.append(tag("rowLimit", row_limit, 4))
    out.append(tag("scope", "organization", 4))
    out.append(tag("showDetails", "true", 4))
    out.append(tag("showGrandTotal", "true", 4))
    out.append(tag("showSubTotals", "true", 4))
    if sort:
        out.append(tag("sortColumn", sort[0], 4))
        out.append(tag("sortOrder", sort[1], 4))
    out.append(f"""    <timeFrameFilter>
        <dateColumn>{date_col}</dateColumn>
        <interval>{interval}</interval>
    </timeFrameFilter>""")
    out.append("</Report>\n")
    write(f"reports/{folder}/{dev}.report-meta.xml", "\n".join(out))
    written["Report"].append(f"{folder}/{dev}")
    return f"{folder}/{dev}"


def chart_xml(chart_type, grouping, summary=(AMT, "Sum"), secondary=None, show_pct=False, show_total=False):
    sec = f"\n        <secondaryGroupingColumn>{secondary}</secondaryGroupingColumn>" if secondary else ""
    col, agg = summary
    agg_xml = f"\n            <aggregate>{agg}</aggregate>" if agg else ""
    # Legends only apply to multi-series charts; value labels are not allowed on stacked/grouped ones.
    legend = ("\n        <legendPosition>Right</legendPosition>"
              if secondary or chart_type in ("Donut", "Funnel", "Pie") else "")
    values = "" if secondary else "\n        <showValues>true</showValues>"
    return f"""    <chart>
        <backgroundColor1>#FFFFFF</backgroundColor1>
        <backgroundColor2>#FFFFFF</backgroundColor2>
        <backgroundFadeDir>Diagonal</backgroundFadeDir>
        <chartSummaries>{agg_xml}
            <axisBinding>y</axisBinding>
            <column>{col}</column>
        </chartSummaries>
        <chartType>{chart_type}</chartType>
        <enableHoverLabels>true</enableHoverLabels>
        <expandOthers>true</expandOthers>
        <groupingColumn>{grouping}</groupingColumn>{legend}
        <location>CHART_TOP</location>{sec}
        <showAxisLabels>true</showAxisLabels>
        <showPercentage>{str(show_pct).lower()}</showPercentage>
        <showTotal>{str(show_total).lower()}</showTotal>{values}
        <size>Medium</size>
        <summaryAxisRange>Auto</summaryAxisRange>
        <textColor>#000000</textColor>
        <textSize>12</textSize>
        <titleColor>#000000</titleColor>
        <titleSize>18</titleSize>
    </chart>"""


def build_reports():
    r = {}
    won = [crit(STAGE, "equals", "Closed Won")]
    active = [crit(STAGE, "notEqual", NOT_ACTIVE)]

    # A. Revenue
    r["R01"] = report("R01_Revenue_Won_YTD", MGMT, "R01 Revenue Won – YTD by Quarter & Month", "Summary",
        desc="Closed Won revenue this fiscal year by fiscal quarter and month.",
        columns=[OPP, ACC, OWNER, "TYPE", (AMT, "Sum")], filters=won, interval="INTERVAL_CURFY",
        down=[(CLOSE, "FiscalQuarter"), ("CLOSE_MONTH", "Month")],
        chart=dict(chart_type="VerticalColumn", grouping=CLOSE))
    r["R02"] = report("R02_Revenue_Won_MTD", MGMT, "R02 Revenue Won – This Month (MTD)", "Summary",
        desc="Closed Won revenue this month by salesperson.",
        columns=[OPP, ACC, (AMT, "Sum"), CLOSE], filters=won, interval="INTERVAL_THISMONTH", down=[OWNER])
    r["R03"] = report("R03_Revenue_Won_QTD", MGMT, "R03 Revenue Won – This Quarter (QTD)", "Summary",
        desc="Closed Won revenue this fiscal quarter by salesperson (gauge vs quarterly target).",
        columns=[OPP, ACC, (AMT, "Sum"), CLOSE], filters=won, interval="INTERVAL_CURRENT", down=[OWNER])
    r["R04"] = report("R04_Revenue_Won_TY_vs_LY", MGMT, "R04 Revenue Won – This Year vs Last Year", "Matrix",
        desc="Closed Won revenue by quarter, current vs previous fiscal year.",
        columns=[(AMT, "Sum")], filters=won, interval="INTERVAL_PREVCURFY",
        down=[CLOSE_QTR], across=[(CLOSE, "FiscalYear")],
        chart=dict(chart_type="VerticalColumnGrouped", grouping=CLOSE_QTR, secondary=CLOSE))

    # B. Pipeline
    r["R05"] = report("R05_Open_Pipeline_by_Stage", MGMT, "R05 Open Pipeline by Stage", "Summary",
        desc="Active open pipeline by stage (excludes Deferred and Old / Archived).",
        columns=[OPP, ACC, OWNER, (AMT, "Sum"), "PROBABILITY", ("EXP_AMOUNT", "Sum"), CLOSE, "NEXT_STEP"],
        open_status="open", filters=active, down=[STAGE],
        chart=dict(chart_type="Funnel", grouping=STAGE))
    r["R06"] = report("R06_Pipeline_by_Close_Quarter", MGMT, "R06 Pipeline by Close Quarter (Next 4)", "Matrix",
        desc="Active open pipeline closing this and the next 3 fiscal quarters, by forecast category.",
        columns=[(AMT, "Sum")], open_status="open", filters=active, interval="INTERVAL_CURNEXT3",
        down=[(CLOSE, "FiscalQuarter")], across=["FORECAST_CATEGORY"],
        chart=dict(chart_type="VerticalColumnStacked", grouping=CLOSE, secondary="FORECAST_CATEGORY"))

    # C. Sales team performance
    r["R07"] = report("R07_Pipeline_by_Salesperson_Stage", SALES, "R07 Pipeline by Salesperson & Stage", "Matrix",
        desc="Active open pipeline by salesperson and stage.",
        columns=[(AMT, "Sum")], open_status="open", filters=active, down=[OWNER], across=[STAGE],
        chart=dict(chart_type="HorizontalBarStacked", grouping=OWNER, secondary=STAGE))
    r["R08"] = report("R08_Revenue_Won_by_Salesperson_YTD", SALES, "R08 Revenue Won by Salesperson – YTD", "Summary",
        desc="Leaderboard: Closed Won revenue this fiscal year by salesperson.",
        columns=[OPP, ACC, (AMT, "Sum"), CLOSE], filters=won, interval="INTERVAL_CURFY",
        down=[{"aggregateType": "Sum", "field": OWNER, "sortByName": AMT, "sortOrder": "Desc", "sortType": "Aggregate"}],
        chart=dict(chart_type="HorizontalBar", grouping=OWNER))
    r["R09"] = report("R09_Win_Rate_by_Salesperson_YTD", SALES, "R09 Win Rate by Salesperson – YTD", "Summary",
        desc="Win rate (won / closed) this fiscal year by salesperson.",
        columns=[OPP, STAGE, (AMT, "Sum"), "WON", "CLOSED"], open_status="closed", interval="INTERVAL_CURFY",
        down=[OWNER], formula=("Win Rate %", "WON:SUM / CLOSED:SUM"))

    # D. Win-loss
    r["R10"] = report("R10_Win_Loss_by_Reason_YTD", SALES, "R10 Win-Loss Analysis by Reason – YTD", "Summary",
        desc="Closed opportunities this fiscal year by outcome and win/loss reason.",
        columns=[OPP, ACC, OWNER, (AMT, "Sum"), DETAILS], open_status="closed", interval="INTERVAL_CURFY",
        down=[STAGE, REASON], chart=dict(chart_type="HorizontalBarStacked", grouping=STAGE, secondary=REASON))
    r["R10A"] = report("R10A_Why_We_Win_YTD", SALES, "R10a Why We Win – YTD", "Summary",
        desc="Dashboard source: Closed Won this fiscal year by win reason.",
        columns=[OPP, ACC, OWNER, (AMT, "Sum"), DETAILS], filters=won, interval="INTERVAL_CURFY",
        down=[REASON], chart=dict(chart_type="Donut", grouping=REASON, show_pct=True, show_total=True))
    r["R10B"] = report("R10B_Why_We_Lose_YTD", SALES, "R10b Why We Lose – YTD", "Summary",
        desc="Dashboard source: Closed Lost this fiscal year by loss reason.",
        columns=[OPP, ACC, OWNER, (AMT, "Sum"), DETAILS], filters=[crit(STAGE, "equals", "Closed Lost")],
        interval="INTERVAL_CURFY", down=[REASON],
        chart=dict(chart_type="Donut", grouping=REASON, show_pct=True, show_total=True))

    # E. Action & hygiene
    r["R11"] = report("R11_Closing_Next_30_Days", SALES, "R11 Closing in Next 30 Days", "Tabular",
        desc="Open deals at Proposal Submitted or later closing in the next 30 days (top 10 by close date).",
        columns=[OPP, ACC, OWNER, STAGE, (AMT, "Sum"), CLOSE, "NEXT_STEP"], open_status="open",
        filters=[crit(STAGE, "equals", "Proposal Submitted,Negotiation,Verbal Award")],
        interval="INTERVAL_NEXT30", row_limit=10, sort=(CLOSE, "Asc"))
    r["R12"] = report("R12_Overdue_Stale_Opportunities", SALES, "R12 Overdue & Stale Opportunities", "Tabular",
        desc="Open deals with a past close date or no activity in the last 30 days.",
        columns=[OPP, OWNER, STAGE, (AMT, "Sum"), CLOSE, "LAST_ACTIVITY", "LAST_UPDATE"], open_status="open",
        filters=[crit(STAGE, "notEqual", NOT_ACTIVE), crit(CLOSE, "lessThan", "TODAY"),
                 crit("LAST_ACTIVITY", "lessThan", "LAST_N_DAYS:30")],
        logic="1 AND (2 OR 3)", row_limit=10, sort=(AMT, "Desc"))
    r["R13"] = report("R13_Deferred_Opportunities", SALES, "R13 Deferred Opportunities", "Summary",
        desc="Deferred (on hold) opportunities and the value that could come back.",
        columns=[OPP, ACC, (AMT, "Sum"), DEFERRED, DETAILS, CLOSE],
        filters=[crit(STAGE, "equals", "Deferred")], down=[OWNER])

    # F. Revenue mix
    r["R14"] = report("R14_Revenue_Pipeline_by_Type", MGMT, "R14 Revenue & Pipeline by Type", "Matrix",
        desc="Won and open (active) value this fiscal year by opportunity type.",
        columns=[(AMT, "Sum")], interval="INTERVAL_CURFY",
        filters=[crit(STAGE, "notEqual", "Closed Lost,Deferred,Old / Archived")],
        down=["TYPE"], across=["WON"], chart=dict(chart_type="Donut", grouping="TYPE", show_pct=True, show_total=True))
    r["R15"] = report("R15_Revenue_by_Lead_Source_Campaign", MGMT, "R15 Revenue by Lead Source & Campaign", "Summary",
        desc="Closed Won revenue this fiscal year by lead source and primary campaign.",
        columns=[OPP, ACC, (AMT, "Sum")], filters=won, interval="INTERVAL_CURFY",
        down=["LEAD_SOURCE", "CAMPAIGN_SOURCE"], chart=dict(chart_type="HorizontalBar", grouping="LEAD_SOURCE"))
    r["R16"] = report("R16_Revenue_by_Industry_Country", MGMT, "R16 Revenue by Industry & Country", "Matrix",
        desc="Closed Won revenue this fiscal year by account industry and billing country (with segment).",
        columns=[(AMT, "Sum"), "Account.Segment__c"], filters=won, interval="INTERVAL_CURFY",
        down=["INDUSTRY"], across=["ADDRESS1_COUNTRY_CODE"],
        chart=dict(chart_type="HorizontalBarStacked", grouping="INDUSTRY", secondary="ADDRESS1_COUNTRY_CODE"))

    # G. Bids & efficiency
    r["R17"] = report("R17_Upcoming_Proposal_Submissions", SALES, "R17 Upcoming Proposal Submissions", "Tabular",
        desc="Open deals with a proposal due in the next 30 days.",
        columns=[OPP, ACC, OWNER, STAGE, PROPOSAL, (AMT, "Sum")], open_status="open",
        date_col=PROPOSAL, interval="INTERVAL_NEXT30", sort=(PROPOSAL, "Asc"))
    r["R18"] = report("R18_Avg_Deal_Size_Sales_Cycle", SALES, "R18 Average Deal Size & Sales Cycle", "Summary",
        desc="Average deal size and age (days) of deals won in the last 365 days.",
        columns=[OPP, (AMT, "Average"), ("AGE", "Average"), "CREATED_DATE", CLOSE],
        filters=won + [crit(CLOSE, "equals", "LAST_N_DAYS:365")], down=[OWNER])
    return r


# --------------------------------------------------------------------------- dashboards
OWNERS = ["Mohammed Alburayh", "Suraj OD", "Venkatesh Rethinasamy"]
INDUSTRIES = ["Agriculture", "Banking", "Construction", "Education", "Energy", "Food & Beverage",
              "Healthcare", "Manufacturing", "Oil & Gas", "Retail", "Telecommunications", "Transportation"]


def comp(report_ref, ctype, header, *, summary=(AMT, "Sum"), groupings=(), extra=None, flex=None,
         gauge=None, metric_label=None, sort_by=None, legend="Bottom", show_values=True, show_pct=False,
         show_total=False):
    e = extra or {}
    out = ["            <dashboardComponent>",
           tag("autoselectColumnsFromReport", "false", 16)]
    if ctype not in ("Metric", "Gauge", "FlexTable"):
        out.append(tag("chartAxisRange", "Auto", 16))
    if ctype != "FlexTable":
        col, agg = summary
        agg_xml = f"\n                    <aggregate>{agg}</aggregate>" if agg else ""
        out.append(f"""                <chartSummary>{agg_xml}
                    <axisBinding>y</axisBinding>
                    <column>{col}</column>
                </chartSummary>""")
    out.append(tag("componentType", ctype, 16))
    out.append(f"                <dashboardFilterColumns>\n                    <column>{OWNER}</column>\n                </dashboardFilterColumns>")
    out.append(f"                <dashboardFilterColumns>\n                    <column>INDUSTRY</column>\n                </dashboardFilterColumns>")
    if ctype != "FlexTable":  # tables carry precision in flexComponentProperties
        out.append(tag("decimalPrecision", -1, 16))
        out.append(tag("displayUnits", "Auto", 16))
    out.append(tag("drillEnabled", "false", 16))
    out.append(tag("drillToDetailEnabled", "false", 16))
    if ctype not in ("Metric", "Gauge", "FlexTable"):
        out.append(tag("enableHover", "true", 16))
        out.append(tag("expandOthers", "false", 16))
    if flex:
        cols, sort_col, sort_order = flex
        fc = "".join(f"""
                    <flexTableColumn>
                        <reportColumn>{c}</reportColumn>
                        <showSubTotal>false</showSubTotal>
                        <showTotal>false</showTotal>
                        <type>{t}</type>
                    </flexTableColumn>""" for c, t in cols)
        out.append(f"""                <flexComponentProperties>
                    <decimalPrecision>-1</decimalPrecision>{fc}
                    <flexTableSortInfo>
                        <sortColumn>{sort_col}</sortColumn>
                        <sortOrder>{sort_order}</sortOrder>
                    </flexTableSortInfo>
                    <hideChatterPhotos>true</hideChatterPhotos>
                </flexComponentProperties>""")
    if gauge:
        out.append(tag("gaugeMax", gauge["max"], 16))
        out.append(tag("gaugeMin", 0, 16))
    for g in groupings:
        out.append(tag("groupingColumn", g, 16))
    out.append(tag("header", header, 16))
    if ctype in ("Metric", "Gauge"):
        if gauge or "bp1" in e:
            out.append(tag("indicatorBreakpoint1", gauge["bp1"] if gauge else e["bp1"], 16))
            out.append(tag("indicatorBreakpoint2", gauge["bp2"] if gauge else e["bp2"], 16))
        # Red / amber / green bands when there is a target; otherwise one neutral colour
        # (colours are required even without breakpoints).
        banded = gauge or "bp1" in e
        out.append(tag("indicatorHighColor", "#54C254" if banded else "#0B5CAB", 16))
        out.append(tag("indicatorLowColor", "#C25454" if banded else "#0B5CAB", 16))
        out.append(tag("indicatorMiddleColor", "#C2C254" if banded else "#0B5CAB", 16))
    if ctype not in ("Metric", "Gauge", "FlexTable"):
        out.append(tag("legendPosition", legend, 16))
    if metric_label:
        out.append(tag("metricLabel", metric_label, 16))
    out.append(tag("report", report_ref, 16))
    if ctype not in ("Metric", "FlexTable"):
        out.append(tag("showPercentage", str(show_pct).lower(), 16))
    if gauge:
        out.append(tag("showRange", "true", 16))
    if ctype not in ("Metric", "Gauge", "FlexTable"):
        out.append(tag("showTotal", str(show_total).lower(), 16))
        out.append(tag("showValues", str(show_values).lower(), 16))
    if ctype not in ("Metric", "Gauge", "FlexTable"):
        out.append(tag("sortBy", sort_by or "RowLabelAscending", 16))
    out.append(tag("useReportChart", "false", 16))
    out.append("            </dashboardComponent>")
    return "\n".join(out)


def grid(c, row, col, rows, cols):
    return f"""        <dashboardGridComponents>
            <colSpan>{cols}</colSpan>
            <columnIndex>{col}</columnIndex>
{c}
            <rowIndex>{row}</rowIndex>
            <rowSpan>{rows}</rowSpan>
        </dashboardGridComponents>"""


def dashboard(dev, title, desc, components):
    filters = []
    for name, values in (("Opportunity Owner", OWNERS), ("Account Industry", INDUSTRIES)):
        opts = "".join(f"""
        <dashboardFilterOptions>
            <operator>equals</operator>
            <values>{x(v)}</values>
        </dashboardFilterOptions>""" for v in values)
        filters.append(f"    <dashboardFilters>{opts}\n        <name>{x(name)}</name>\n    </dashboardFilters>")
    body = f"""<Dashboard {NS}>
    <backgroundEndColor>#FFFFFF</backgroundEndColor>
    <backgroundFadeDirection>Diagonal</backgroundFadeDirection>
    <backgroundStartColor>#FFFFFF</backgroundStartColor>
    <chartTheme>light</chartTheme>
    <colorPalette>unity</colorPalette>
    <dashboardChartTheme>light</dashboardChartTheme>
    <dashboardColorPalette>unity</dashboardColorPalette>
{chr(10).join(filters)}
    <dashboardGridLayout>
{chr(10).join(components)}
        <numberOfColumns>12</numberOfColumns>
        <rowHeight>36</rowHeight>
    </dashboardGridLayout>
    <dashboardType>SpecifiedUser</dashboardType>
    <description>{x(desc)}</description>
    <isGridLayout>true</isGridLayout>
    <runningUser>{RUNNING_USER}</runningUser>
    <textColor>#000000</textColor>
    <title>{x(title)}</title>
    <titleColor>#000000</titleColor>
    <titleSize>12</titleSize>
</Dashboard>
"""
    write(f"dashboards/{DASH_FOLDER}/{dev}.dashboard-meta.xml", body)
    written["Dashboard"].append(f"{DASH_FOLDER}/{dev}")


def build_dashboards(r):
    t = QUARTERLY_TARGET
    d1 = [
        grid(comp(r["R02"], "Metric", "Revenue Won – MTD", metric_label="Month to date",
                  extra={"bp1": round(t / 3 * 0.6), "bp2": round(t / 3 * 0.9)}), 0, 0, 4, 2),
        grid(comp(r["R03"], "Gauge", "Revenue Won – QTD vs Target",
                  gauge={"max": t, "bp1": round(t * 0.6), "bp2": round(t * 0.9)}), 0, 2, 4, 3),
        grid(comp(r["R01"], "Metric", "Revenue Won – YTD", metric_label="Year to date"), 0, 5, 4, 3),
        grid(comp(r["R05"], "Metric", "Open Pipeline Value", metric_label="Active pipeline"), 0, 8, 4, 2),
        grid(comp(r["R09"], "Metric", "Win Rate YTD", summary=("FORMULA1", None), metric_label="Won / closed"),
             0, 10, 4, 2),
        grid(comp(r["R04"], "ColumnGrouped", "Revenue by Quarter – This Year vs Last Year",
                  groupings=[CLOSE_QTR, CLOSE], sort_by="RowLabelAscending"), 4, 0, 8, 6),
        grid(comp(r["R05"], "Funnel", "Pipeline by Stage", groupings=[STAGE], legend="Right"), 4, 6, 8, 6),
        grid(comp(r["R06"], "ColumnStacked", "Pipeline by Close Quarter",
                  groupings=[CLOSE, "FORECAST_CATEGORY"], sort_by="RowLabelAscending"), 12, 0, 8, 6),
        grid(comp(r["R11"], "FlexTable", "Top Deals Closing in 30 Days",
                  flex=([(OPP, "detail"), (ACC, "detail"), (OWNER, "detail"), (STAGE, "detail"),
                         (AMT, "detail"), (CLOSE, "detail")], CLOSE, "1")), 12, 6, 8, 6),
    ]
    dashboard("ABA_Management_Revenue_Pipeline", "ABA Management – Revenue & Pipeline",
              "D1: revenue won (MTD/QTD/YTD), year-on-year trend, pipeline and deals to push now.", d1)

    d2 = [
        grid(comp(r["R08"], "Bar", "Revenue Won by Salesperson", groupings=[OWNER], sort_by="RowValueDescending"),
             0, 0, 8, 4),
        grid(comp(r["R07"], "BarStacked", "Pipeline by Salesperson & Stage", groupings=[OWNER, STAGE]), 0, 4, 8, 4),
        grid(comp(r["R09"], "FlexTable", "Win Rate by Salesperson",
                  flex=([(OWNER, "grouping"), ("FORMULA1", "aggregate"), ("RowCount", "aggregate")],
                        "FORMULA1", "2")), 0, 8, 8, 4),
        grid(comp(r["R10A"], "Donut", "Why We Win", groupings=[REASON], legend="Right", show_total=True),
             8, 0, 8, 4),
        grid(comp(r["R10B"], "Donut", "Why We Lose", groupings=[REASON], legend="Right", show_total=True),
             8, 4, 8, 4),
        grid(comp(r["R14"], "Donut", "Revenue by Type (New vs Existing)", groupings=["TYPE"], legend="Right",
                  show_total=True), 8, 8, 8, 4),
        grid(comp(r["R15"], "Bar", "Revenue by Lead Source", groupings=["LEAD_SOURCE"],
                  sort_by="RowValueDescending"), 16, 0, 8, 4),
        grid(comp(r["R13"], "Metric", "Deferred Value", metric_label="Revenue on hold"), 16, 4, 8, 4),
        grid(comp(r["R12"], "FlexTable", "Overdue & Stale Deals",
                  flex=([(OPP, "detail"), (OWNER, "detail"), (STAGE, "detail"), (AMT, "detail"),
                         (CLOSE, "detail")], AMT, "2")), 16, 8, 8, 4),
    ]
    dashboard("ABA_Sales_Performance_Win_Loss", "ABA Sales Performance & Win-Loss",
              "D2: salesperson leaderboard, pipeline coverage, win rate, win/loss reasons, revenue mix and hygiene.", d2)


# --------------------------------------------------------------------------- folders, home page, app
def build_folders():
    def report_folder(dev, name, shares):
        s = "".join(f"""
    <folderShares>
        <accessLevel>View</accessLevel>
        <sharedTo>{to}</sharedTo>
        <sharedToType>{typ}</sharedToType>
    </folderShares>""" for to, typ in shares)
        write(f"reports/{dev}.reportFolder-meta.xml", f"<ReportFolder {NS}>{s}\n    <name>{x(name)}</name>\n</ReportFolder>\n")

    mgmt_share = [("CEO", "RoleAndSubordinatesInternal")]
    report_folder(MGMT, "ABA Management Reports", mgmt_share)
    report_folder(SALES, "ABA Sales Reports", [("AllInternalUsers", "Organization")])
    s = "".join(f"""
    <folderShares>
        <accessLevel>View</accessLevel>
        <sharedTo>{to}</sharedTo>
        <sharedToType>{typ}</sharedToType>
    </folderShares>""" for to, typ in mgmt_share)
    write(f"dashboards/{DASH_FOLDER}.dashboardFolder-meta.xml",
          f"<DashboardFolder {NS}>{s}\n    <name>ABA Management Dashboards</name>\n</DashboardFolder>\n")


def prop(name, value):
    return f"""                <componentInstanceProperties>
                    <name>{name}</name>
                    <value>{x(str(value))}</value>
                </componentInstanceProperties>"""


def component(name, ident, props):
    return f"""        <itemInstances>
            <componentInstance>
{chr(10).join(prop(k, v) for k, v in props)}
                <componentName>{name}</componentName>
                <identifier>{ident}</identifier>
            </componentInstance>
        </itemInstances>"""


def build_home_page():
    def dash(dev, ident, height):
        return component("desktopDashboards:embeddedDashboard", ident, [
            ("dashboardName", dev), ("height", height), ("hideOnError", "false")])

    def chart(report_dev, label, ident):
        return component("flexipage:reportChart", ident, [
            ("cacheAge", "1440"), ("label", label), ("reportName", report_dev),
            ("showRefreshButton", "true")])

    regions = {
        "top": [dash("ABA_Management_Revenue_Pipeline", "aba_dashboard_mgmt", 900),
                dash("ABA_Sales_Performance_Win_Loss", "aba_dashboard_sales", 1050)],
        "bottomLeft": [chart("R05_Open_Pipeline_by_Stage", "Open Pipeline by Stage", "aba_chart_pipeline")],
        "bottomRight": [chart("R10A_Why_We_Win_YTD", "Why We Win – YTD", "aba_chart_win")],
        "sidebar": [chart("R08_Revenue_Won_by_Salesperson_YTD", "Revenue Won by Salesperson – YTD",
                          "aba_chart_leaderboard"),
                    chart("R01_Revenue_Won_YTD", "Revenue Won – YTD", "aba_chart_ytd")],
    }
    body = "\n".join(f"""    <flexiPageRegions>
{chr(10).join(items)}
        <name>{name}</name>
        <type>Region</type>
    </flexiPageRegions>""" for name, items in regions.items())
    write("flexipages/ABA_Sales_Home_Page.flexipage-meta.xml", f"""<FlexiPage {NS}>
{body}
    <description>ABA Sales app Home page: management and sales performance dashboards plus key report charts.</description>
    <masterLabel>ABA Sales Home Page</masterLabel>
    <template>
        <name>home:desktopTemplate</name>
    </template>
    <type>HomePage</type>
</FlexiPage>
""")


def assign_home_to_sales_app():
    path = os.path.join(SRC, "applications", "standard__LightningSales.app-meta.xml")
    with open(path, encoding="utf-8") as f:
        xml = f.read()
    if "ABA_Sales_Home_Page" in xml:
        return
    override = """    <actionOverrides>
        <actionName>Tab</actionName>
        <comment>ABA management and sales performance home page</comment>
        <content>ABA_Sales_Home_Page</content>
        <formFactor>Large</formFactor>
        <skipRecordTypeSelect>false</skipRecordTypeSelect>
        <type>Flexipage</type>
        <pageOrSobjectType>standard-home</pageOrSobjectType>
    </actionOverrides>
"""
    marker = '<CustomApplication xmlns="http://soap.sforce.com/2006/04/metadata">\n'
    xml = xml.replace(marker, marker + override, 1)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)


def build_manifest():
    types = {
        "StandardValueSet": ["Industry", "LeadSource", "OpportunityStage", "OpportunityType"],
        "CustomField": ["Account.Segment__c", "Opportunity.Close_Quarter__c", "Opportunity.Deferred_Date__c",
                        "Opportunity.Offering__c", "Opportunity.Proposal_Submission_Date__c",
                        "Opportunity.Win_Loss_Details__c", "Opportunity.Win_Loss_Reason__c"],
        "ValidationRule": ["Opportunity.Win_Loss_Reason_Required"],
        "Flow": ["ABA_Opportunity_Set_Deferred_Date"],
        "PermissionSet": ["ABA_Historical_Data_Load", "ABA_Opportunity_Reporting"],
        "Layout": ["Account-Account Layout", "Opportunity-Opportunity Layout"],
        "Report": [MGMT, SALES] + written["Report"],  # report folders are listed under Report
        "Dashboard": [DASH_FOLDER] + written["Dashboard"],
        "FlexiPage": ["ABA_Sales_Home_Page"],
        "CustomApplication": ["standard__LightningSales"],
    }
    blocks = "".join(
        f"    <types>\n" + "".join(f"        <members>{x(m)}</members>\n" for m in members)
        + f"        <name>{t}</name>\n    </types>\n" for t, members in types.items())
    with open(os.path.join(ROOT, "manifest", "aba-package.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(HDR + f"<Package {NS}>\n{blocks}    <version>67.0</version>\n</Package>\n")


if __name__ == "__main__":
    build_folders()
    reps = build_reports()
    build_dashboards(reps)
    build_home_page()
    assign_home_to_sales_app()
    build_manifest()
    print(f"{len(written['Report'])} reports, {len(written['Dashboard'])} dashboards, home page + app override")
