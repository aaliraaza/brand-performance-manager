# Databricks notebook source
# MAGIC %md
# MAGIC # Brand Performance Manager — Step 2: Generate Knowledge Assistant Documents
# MAGIC
# MAGIC Generates 10 CPG-domain PDF documents uploaded to Unity Catalog Volumes:
# MAGIC
# MAGIC **Brand Analytics Framework KA** → `.../raw_data/analytics_docs/`
# MAGIC - brand_share_decomposition_framework.pdf
# MAGIC - nielsen_iri_glossary_cpg.pdf
# MAGIC - brand_equity_measurement_guide.pdf
# MAGIC - cpg_competitive_response_playbook.pdf
# MAGIC - promotional_roi_framework.pdf
# MAGIC - category_management_handbook.pdf
# MAGIC
# MAGIC **CPG Market Intelligence KA** → `.../raw_data/market_docs/`
# MAGIC - cpg_market_trends_2024_2025.pdf
# MAGIC - private_label_threat_assessment.pdf
# MAGIC - omnichannel_distribution_dynamics.pdf
# MAGIC - retailer_power_dynamics_walmart_target.pdf

# COMMAND ----------

# MAGIC %md ## Configuration

# COMMAND ----------

CATALOG = "ar_dpcatalog"   # Update to your catalog
SCHEMA  = "brand_performance"
VOLUME  = "raw_data"

ANALYTICS_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/analytics_docs"
MARKET_PATH    = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/market_docs"

# Create volume and subdirectories
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")
dbutils.fs.mkdirs(ANALYTICS_PATH)
dbutils.fs.mkdirs(MARKET_PATH)
print(f"Volume paths ready:\n  {ANALYTICS_PATH}\n  {MARKET_PATH}")

# COMMAND ----------

# MAGIC %md ## PDF Generation Helpers

# COMMAND ----------

# MAGIC %pip install reportlab --quiet

# COMMAND ----------

import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

NAVY   = colors.HexColor("#003087")
ORANGE = colors.HexColor("#E87722")
GRAY   = colors.HexColor("#4A4A4A")
LGRAY  = colors.HexColor("#F4F6F9")
WHITE  = colors.white

base_styles = getSampleStyleSheet()
S = {
    "title":  ParagraphStyle("t",  parent=base_styles["Title"],   fontSize=18, textColor=NAVY,   alignment=TA_CENTER, spaceAfter=6),
    "sub":    ParagraphStyle("s",  parent=base_styles["Normal"],  fontSize=10, textColor=GRAY,   alignment=TA_CENTER, spaceAfter=14),
    "h1":     ParagraphStyle("h1", parent=base_styles["Heading1"],fontSize=13, textColor=NAVY,   spaceBefore=12, spaceAfter=5),
    "h2":     ParagraphStyle("h2", parent=base_styles["Heading2"],fontSize=11, textColor=GRAY,   spaceBefore=9,  spaceAfter=4),
    "body":   ParagraphStyle("b",  parent=base_styles["Normal"],  fontSize=9.5, leading=15, spaceAfter=8, alignment=TA_JUSTIFY),
    "bullet": ParagraphStyle("bl", parent=base_styles["Normal"],  fontSize=9.5, leading=14, spaceAfter=4, leftIndent=16),
    "alert":  ParagraphStyle("al", parent=base_styles["Normal"],  fontSize=9.5, leading=14, spaceAfter=8,
                              backColor=colors.HexColor("#EEF4FF"), borderPadding=8, textColor=NAVY),
    "formula":ParagraphStyle("f",  parent=base_styles["Normal"],  fontSize=9,   leading=14, spaceAfter=8,
                              fontName="Courier", backColor=LGRAY, borderPadding=6, textColor=GRAY),
    "footer": ParagraphStyle("ft", parent=base_styles["Normal"],  fontSize=8, textColor=colors.gray, alignment=TA_CENTER),
}


def tbl(data, col_widths, hdr_color=NAVY):
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), hdr_color),
        ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGRAY]),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    return t


def to_bytes(elements):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.75*inch,   bottomMargin=0.75*inch)
    doc.build(elements)
    return buf.getvalue()


def header(title, subtitle, org="NovaLife Nutrition — Analytics Center of Excellence"):
    return [
        Paragraph(org, S["sub"]),
        Paragraph(title, S["title"]),
        Paragraph(subtitle, S["sub"]),
        HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=10),
        Spacer(1, 6),
    ]


def footer_elem(text="Internal Document — For Commercial Use Only"):
    return [Spacer(1, 20), HRFlowable(width="100%", thickness=1, color=colors.lightgrey), Paragraph(text, S["footer"])]


def upload_pdf(pdf_bytes, filename, path):
    full_path = f"{path}/{filename}"
    with open(f"/tmp/{filename}", "wb") as f:
        f.write(pdf_bytes)
    dbutils.fs.cp(f"file:/tmp/{filename}", full_path)
    size = dbutils.fs.ls(path)
    return full_path

# COMMAND ----------

# MAGIC %md ## Analytics Docs — Brand Analytics Framework KA

# COMMAND ----------

uploaded = []

# ── Doc 1: Brand Share Decomposition Framework ────────────────────────────────

e = header("Brand Share Decomposition Framework", "Rate vs. Distribution Driver Analysis — Methodology & Worked Examples") + [
    Paragraph("1. Introduction", S["h1"]),
    Paragraph("Brand share decomposition separates total share change into its underlying drivers, enabling commercial teams to identify whether share gains or losses are primarily driven by distribution changes (gaining or losing shelf space and ACV coverage) or rate effects (pricing, mix, and promotional intensity changes). This framework is the foundation of the NovaBaby Performance Intelligence System.", S["body"]),

    Paragraph("2. The Five Drivers", S["h1"]),
    Paragraph("Total share change (ΔShare) is decomposed as:", S["body"]),
    Paragraph("ΔShare = ΔDistribution + ΔRate + ΔPenetration + ΔFrequency + ΔBasket Size", S["formula"]),
    tbl([
        ["Driver",                "Definition",                                         "Typical Range",   "Sign Interpretation"],
        ["Distribution (ΔDist)",  "Change in ACV-weighted distribution coverage",       "−1.5 to +1.5 ppt","+ = gained shelf space"],
        ["Rate (ΔRate)",          "Price/mix effect — premium vs. value shift",         "−1.2 to +1.2 ppt","+ = favorable mix"],
        ["Penetration (ΔPen)",    "Change in % of households buying the brand",         "−0.8 to +0.8 ppt","+ = more households"],
        ["Frequency (ΔFreq)",     "Change in average purchase occasions per buyer",     "−0.6 to +0.6 ppt","+ = more trips"],
        ["Basket Size (ΔBasket)", "Change in average units per shopping trip",          "−0.4 to +0.4 ppt","+ = larger baskets"],
    ], [1.5*inch, 2.4*inch, 1.2*inch, 1.4*inch]),
    Spacer(1, 10),

    Paragraph("3. Calculation Methodology", S["h1"]),
    Paragraph("Step 1 — Establish baseline period (prior 12-week avg) and current period (latest 12-week avg).", S["body"]),
    Paragraph("Step 2 — Compute ACV-weighted distribution index:", S["body"]),
    Paragraph("ACV Index = (Brand ACV%) / (Category avg ACV%) × 100", S["formula"]),
    Paragraph("Step 3 — Compute rate index:", S["body"]),
    Paragraph("Rate Index = (Brand avg price) / (Category avg price) × 100", S["formula"]),
    Paragraph("Step 4 — Apply the attribution model using Nielsen/Circana multi-factor regression.", S["body"]),

    Paragraph("4. Worked Example — NovaBaby Infant Formula, Walmart, Last 4 Weeks", S["h1"]),
    tbl([
        ["Driver",         "Change (ppt)", "Interpretation"],
        ["Distribution",   "−0.8",         "ACV declined from 86% → 83% at Walmart — lost 2 bays in Southeast"],
        ["Rate",           "−0.3",         "Price index rose vs. category (less promo support) — some trade-down"],
        ["Penetration",    "−0.2",         "Fewer new buyers — insurgent brands capturing first-time buyers"],
        ["Frequency",      "−0.1",         "Marginally fewer shopping trips from brand buyers"],
        ["Basket Size",    "+0.1",          "Loyal buyers purchasing slightly larger sizes"],
        ["TOTAL",          "−1.3",         "Net share loss of 1.3 ppt vs. prior 4-week period"],
    ], [1.4*inch, 1.2*inch, 3.9*inch]),
    Spacer(1, 10),
    Paragraph("Interpretation: The primary driver is distribution loss (61% of total decline), followed by rate effects (23%). The recommended response is to address the ACV gap at Walmart Southeast before initiating pricing corrections.", S["alert"]),

    Paragraph("5. Benchmark Ranges", S["h1"]),
    Paragraph("For a market-leading brand in Infant Formula (35% share), a quarterly share change of ±0.5 ppt is within normal variance. Changes exceeding ±1.0 ppt in a single 4-week period require root-cause investigation.", S["body"]),
] + footer_elem()

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "brand_share_decomposition_framework.pdf", ANALYTICS_PATH)
uploaded.append(("brand_share_decomposition_framework.pdf", ANALYTICS_PATH, len(pdf_bytes)))
print("✅ brand_share_decomposition_framework.pdf")

# COMMAND ----------

# ── Doc 2: Nielsen/IRI CPG Glossary ──────────────────────────────────────────

e = header("Nielsen / Circana (IRI) CPG Data Glossary", "Key Metrics, Definitions & Calculation Methods") + [
    Paragraph("1. Distribution Metrics", S["h1"]),
    tbl([
        ["Metric",                       "Definition",                                                             "Formula"],
        ["ACV %",                         "% of all commodity volume sold through stores carrying the brand",       "Σ(Store Sales × Carrying?) / Σ(All Store Sales)"],
        ["Weighted ACV %",               "ACV distribution weighted by store volume",                              "Same as ACV — Nielsen standard"],
        ["Stores Selling",               "Count of stores that scanned at least 1 unit in the period",             "Count(stores with unit_sales > 0)"],
        ["% Any Promo ACV",              "% ACV where brand was on promotion",                                     "ACV on promo / Total ACV"],
        ["Avg Items Carrying",           "Average number of SKUs per store carrying brand",                        "Σ SKUs per store / Stores Selling"],
    ], [1.3*inch, 3.2*inch, 2.0*inch]),
    Spacer(1, 8),

    Paragraph("2. Velocity Metrics", S["h1"]),
    tbl([
        ["Metric",                       "Definition",                                                             "Typical Range (IF category)"],
        ["Velocity ($/MM ACV)",          "Dollar sales per million dollars of ACV distribution",                   "$800 — $6,500"],
        ["Units/Store/Week (U/S/W)",     "Average unit sales per carrying store per week",                         "4 — 45 units"],
        ["Turns",                        "Rate at which shelf inventory sells through",                             "0.5 — 3.5× per week"],
        ["$ Sales / Point of Dist",      "Dollar volume attributable to each 1% ACV",                              "$5,000 — $50,000"],
    ], [1.8*inch, 3.2*inch, 1.5*inch]),
    Spacer(1, 8),

    Paragraph("3. Share Metrics", S["h1"]),
    Paragraph("All share metrics are calculated within a defined category boundary (e.g. 'Infant Formula — Total US — All Channels'):", S["body"]),
    tbl([
        ["Metric",                       "Definition",                                                             "Notes"],
        ["Dollar Share %",               "Brand dollar sales / Total category dollar sales × 100",                 "Primary share metric"],
        ["Unit Share %",                 "Brand unit sales / Total category unit sales × 100",                     "Volume share"],
        ["Volume Share %",               "Brand oz/equivalent / Total category oz/equivalent × 100",               "Used for weight-sold categories"],
        ["Equiv Volume Share %",         "Normalized by pack size to compare across SKU sizes",                    "Nielsen calculated"],
    ], [1.8*inch, 3.2*inch, 1.5*inch]),
    Spacer(1, 8),

    Paragraph("4. Period Definitions", S["h1"]),
    tbl([
        ["Period",        "Definition",                    "Common Use"],
        ["L4W",           "Latest 4 weeks (rolling)",      "Short-term trend, promotional impact"],
        ["L12W",          "Latest 12 weeks (rolling)",     "Quarterly view, baseline measurement"],
        ["L52W",          "Latest 52 weeks (rolling)",     "Annual trend, YoY comparison base"],
        ["YTD",           "Year to date (calendar year)",  "Internal planning alignment"],
        ["MAT",           "Moving annual total",           "Rolling 52-week total"],
    ], [1.0*inch, 2.8*inch, 2.7*inch]),
    Spacer(1, 8),

    Paragraph("5. Key Distinctions", S["h1"]),
    Paragraph("ACV vs. Unweighted Distribution: ACV weights stores by their total sales volume, so gaining distribution in a high-volume Walmart supercenter counts more than gaining it in a small independent store. Always use ACV % unless specifically analyzing store counts.", S["body"]),
    Paragraph("Dollar Share vs. Volume Share: Premium brands typically have higher dollar share than volume share (favorable mix). Value brands show the reverse. A widening gap between the two indicates pricing power changes.", S["body"]),
] + footer_elem("Proprietary — NovaLife Nutrition Analytics CoE | Source: Nielsen / Circana methodology")

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "nielsen_iri_glossary_cpg.pdf", ANALYTICS_PATH)
uploaded.append(("nielsen_iri_glossary_cpg.pdf", ANALYTICS_PATH, len(pdf_bytes)))
print("✅ nielsen_iri_glossary_cpg.pdf")

# COMMAND ----------

# ── Doc 3: Brand Equity Measurement Guide ────────────────────────────────────

e = header("Brand Equity Measurement Guide", "Activation vs. Equity Metrics — KPI Hierarchy & Interpretation") + [
    Paragraph("1. Equity vs. Activation — Why Both Matter", S["h1"]),
    Paragraph("Brand equity metrics capture the long-term health and mental availability of a brand — what consumers think and feel about the brand even when not in a purchase situation. Activation metrics capture short-term commercial performance. Both are required for a complete picture.", S["body"]),
    tbl([
        ["Dimension",      "Equity Metrics (long-term)",               "Activation Metrics (short-term)"],
        ["Awareness",      "Unaided brand awareness %",                "Search volume index"],
        ["Consideration",  "Brand considered for next purchase %",     "Add-to-cart rate"],
        ["Trial",          "New buyer rate %",                         "Trial unit velocity"],
        ["Loyalty",        "Repeat purchase rate %",                   "Subscription rate"],
        ["Advocacy",       "Net Promoter Score (NPS)",                  "5-star review rate"],
    ], [1.3*inch, 2.7*inch, 2.5*inch]),
    Spacer(1, 10),

    Paragraph("2. KPI Hierarchy for CPG Brand Teams", S["h1"]),
    Paragraph("Level 1 — Business Outcomes (reported monthly):", S["body"]),
    Paragraph("Dollar Share % | Revenue growth % | Contribution margin %", S["formula"]),
    Paragraph("Level 2 — Market Performance (reported weekly):", S["body"]),
    Paragraph("ACV distribution % | Velocity per MM ACV | New buyers %", S["formula"]),
    Paragraph("Level 3 — Brand Equity Drivers (reported quarterly):", S["body"]),
    Paragraph("Unaided awareness | Brand consideration | Brand preference vs. category", S["formula"]),

    Paragraph("3. The Equity-Activation Balance", S["h1"]),
    Paragraph("Brands with high activation but declining equity are at risk: short-term sales are maintained through promotions, but underlying brand preference is eroding. NovaBaby should maintain a minimum 55% unaided awareness in the 18-34 new parent demographic to sustain long-term share above 30%.", S["alert"]),

    Paragraph("4. Measurement Cadence & Data Sources", S["h1"]),
    tbl([
        ["Metric",                 "Frequency",  "Source",              "Owner"],
        ["Dollar Share %",         "Weekly",     "Nielsen / Circana",   "Analytics CoE"],
        ["ACV Distribution %",     "Weekly",     "Nielsen / Circana",   "Analytics CoE"],
        ["New Buyer Rate",         "4-weekly",   "Numerator Panel",     "Consumer Insights"],
        ["Unaided Awareness",      "Quarterly",  "Custom Survey",       "Brand Team"],
        ["NPS",                    "Quarterly",  "Customer Survey",     "Marketing"],
        ["Brand Preference",       "Semi-annual","Custom Survey",       "Consumer Insights"],
    ], [1.5*inch, 0.9*inch, 1.7*inch, 1.4*inch]),
] + footer_elem()

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "brand_equity_measurement_guide.pdf", ANALYTICS_PATH)
uploaded.append(("brand_equity_measurement_guide.pdf", ANALYTICS_PATH, len(pdf_bytes)))
print("✅ brand_equity_measurement_guide.pdf")

# COMMAND ----------

# ── Doc 4: CPG Competitive Response Playbook ─────────────────────────────────

e = header("CPG Competitive Response Playbook", "Insurgent Brand Threat Assessment & Response Strategies") + [
    Paragraph("1. What Is an Insurgent Brand?", S["h1"]),
    Paragraph("An insurgent brand is a challenger brand that is gaining market share at an accelerating rate, typically competing on one or more of: natural/organic positioning, DTC channel presence, transparent ingredient claims, or premium price-performance value perception. In the Infant Formula and Baby Food categories, insurgents typically enter online first, then expand to specialty retail, then to mass.", S["body"]),

    Paragraph("2. Threat Scoring Model", S["h1"]),
    Paragraph("The BPM system uses a composite threat score (0–100) combining:", S["body"]),
    Paragraph("Threat Score = (ACV% × 0.40) + (Value Share% × 1.0) + (52W Share Gain ppt × 15)", S["formula"]),
    tbl([
        ["Score Range", "Threat Level",  "Recommended Response",                                          "Timeline"],
        ["0–20",        "Monitor",       "Track weekly in BPM dashboard. No active response required.",   "Ongoing"],
        ["21–40",       "Watch",         "Quarterly competitive review. Evaluate distribution overlap.",   "Quarterly"],
        ["41–60",       "Respond",       "Active response plan. Consider shelf blocking, promo defense.",   "30 days"],
        ["61–80",       "Escalate",      "VP-level review. Innovation pipeline acceleration.",              "14 days"],
        ["81–100",      "Critical",      "EVP intervention. Acquisition or direct counter-brand launch.",   "7 days"],
    ], [0.8*inch, 0.9*inch, 3.6*inch, 0.9*inch]),
    Spacer(1, 8),

    Paragraph("3. Response Playbook by Driver", S["h1"]),
    Paragraph("Distribution-led threat (insurgent ACV growing fast):", S["body"]),
    Paragraph("• Activate key account sell-in with category captain data showing your higher velocity\n• Request shelf review to defend category adjacencies\n• Negotiate for end-cap / secondary placement before insurgent achieves critical ACV mass", S["bullet"]),
    Paragraph("Rate-led threat (insurgent gaining on price-value perception):", S["body"]),
    Paragraph("• Audit shelf price gap — if >15% premium, consider trade promotion optimization\n• Activate value-tier SKU to provide down-trade option within your portfolio\n• Invest in benefit communication (clinicals, premium ingredients) to justify price delta", S["bullet"]),

    Paragraph("4. Case Study — Happy Roots in Infant Formula", S["h1"]),
    Paragraph("Happy Roots entered the Infant Formula category in early 2023 with DTC-first strategy, expanded to Target in mid-2023, and reached 28% ACV in Walmart by Q2 2024. Share gain of 1.8 ppt over 52W in Total US. Threat Score: 52 (Respond tier). NovaBaby response: launched NovaBaby Organics shelf-neighbor blocking strategy at Target, increasing facing allocation from 2→4 in the organic section.", S["body"]),
] + footer_elem()

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "cpg_competitive_response_playbook.pdf", ANALYTICS_PATH)
uploaded.append(("cpg_competitive_response_playbook.pdf", ANALYTICS_PATH, len(pdf_bytes)))
print("✅ cpg_competitive_response_playbook.pdf")

# COMMAND ----------

# ── Doc 5: Promotional ROI Framework ─────────────────────────────────────────

e = header("Promotional ROI Framework", "Trade Promotion Evaluation, Lift Calculation & Efficiency Metrics") + [
    Paragraph("1. Trade Promotion Mechanics", S["h1"]),
    Paragraph("Trade promotions include: TPR (Temporary Price Reduction), Feature (retailer ad circular placement), Display (secondary in-store placement), and combined F+D+TPR events. Each has different incremental lift and cost structures.", S["body"]),
    tbl([
        ["Promo Type",      "Avg Lift",    "Cost/Case",   "Duration",     "Best For"],
        ["TPR only",        "15–25%",      "$0.50–1.20",  "2–4 weeks",    "Maintaining velocity"],
        ["Feature only",    "20–35%",      "$1.50–3.00",  "1 week",       "Awareness boost"],
        ["Display only",    "25–40%",      "$2.00–4.00",  "2–4 weeks",    "New item support"],
        ["F+D+TPR",         "80–150%",     "$4.00–8.00",  "1–2 weeks",    "Major launches/events"],
    ], [1.2*inch, 0.8*inch, 0.9*inch, 0.9*inch, 2.7*inch]),
    Spacer(1, 8),

    Paragraph("2. Incremental Lift Calculation", S["h1"]),
    Paragraph("Baseline = rolling 4-week pre-event average velocity (adjusted for seasonality).", S["body"]),
    Paragraph("Incremental Units = Promoted Units − Baseline Units × Promoted ACV Weeks", S["formula"]),
    Paragraph("Incremental Revenue = Incremental Units × Net Realized Price per Unit", S["formula"]),
    Paragraph("Trade Spend = Promotional Allowance × All Units Sold on Deal", S["formula"]),
    Paragraph("Promotion ROI = (Incremental Revenue − Trade Spend) / Trade Spend × 100%", S["formula"]),

    Paragraph("3. ROI Benchmarks by Category", S["h1"]),
    tbl([
        ["Category",       "Min Acceptable ROI",  "Target ROI",   "Excellent ROI"],
        ["Infant Formula", "80%",                  "120–180%",     ">200%"],
        ["Baby Food",      "70%",                  "100–150%",     ">180%"],
        ["Toddler Snacks", "60%",                  "90–130%",      ">160%"],
    ], [1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch]),
    Spacer(1, 8),

    Paragraph("4. Common Evaluation Errors", S["h1"]),
    Paragraph("Forward buying: consumers (or retailers) buying excess during promotion for later use — artificially inflates lift measurement. Adjust by extending post-event window to 4 weeks to capture pull-forward effect.", S["body"]),
    Paragraph("Category cannibalization: lift on one SKU from consumers switching from another company SKU — calculate portfolio-level lift, not just item-level.", S["body"]),
] + footer_elem()

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "promotional_roi_framework.pdf", ANALYTICS_PATH)
uploaded.append(("promotional_roi_framework.pdf", ANALYTICS_PATH, len(pdf_bytes)))
print("✅ promotional_roi_framework.pdf")

# COMMAND ----------

# ── Doc 6: Category Management Handbook ──────────────────────────────────────

e = header("Category Management Handbook", "Category Review Frameworks, Shelf Optimization & Planogram Principles") + [
    Paragraph("1. Category Management Defined", S["h1"]),
    Paragraph("Category management is a retailer-supplier process of managing product categories as strategic business units to produce enhanced business results by focusing on delivering consumer value. As category captain, NovaBaby acts as a strategic advisor to retailer category managers, providing insights that benefit the full category (not just NovaBaby's portfolio).", S["body"]),

    Paragraph("2. The Category Review Process", S["h1"]),
    tbl([
        ["Step", "Phase",          "Duration",   "Key Output"],
        ["1",    "Category Definition",  "1 week", "Category boundaries, segments, consumer decision tree"],
        ["2",    "Market Assessment",    "2 weeks","Category sizing, growth, trend analysis, key metrics"],
        ["3",    "Consumer Insights",    "2 weeks","Shopper mission, barriers, needs-state mapping"],
        ["4",    "Competitive Analysis", "1 week", "Assortment gaps, pricing architecture, share dynamics"],
        ["5",    "Recommendations",      "2 weeks","Planogram, pricing strategy, promo calendar"],
        ["6",    "Implementation",       "4 weeks","Shelf reset, new item placement, communication"],
    ], [0.4*inch, 1.4*inch, 0.9*inch, 4.0*inch]),
    Spacer(1, 8),

    Paragraph("3. Shelf Space Allocation Principles", S["h1"]),
    Paragraph("Fair share: each brand should receive shelf space proportional to its dollar share. Above-fair-share allocation is justified for: (1) growing segments, (2) new item launch support, (3) high velocity per facing.", S["body"]),
    Paragraph("Space Productivity = $ Sales / Linear Foot of Shelf Space", S["formula"]),
    Paragraph("Brands with Space Productivity >150% of category average are candidates for shelf space expansion.", S["body"]),

    Paragraph("4. Planogram Optimization for Infant Formula", S["h1"]),
    Paragraph("Eye level placement (30in–60in from floor) drives 20–35% higher velocity vs. top or bottom shelf for the same SKU. In Infant Formula, consumers are highly brand-loyal but will trial adjacent brands if eye-level options are limited. Priority for eye-level placement: highest-velocity SKUs × highest-margin SKUs.", S["body"]),
    Paragraph("Secondary placement (end-caps, clip strips, cross-merchandising) provides 25–40% additional lift without displacing primary shelf space. Ideal end-cap candidates: new items, seasonal variants, bundle offers.", S["body"]),
] + footer_elem()

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "category_management_handbook.pdf", ANALYTICS_PATH)
uploaded.append(("category_management_handbook.pdf", ANALYTICS_PATH, len(pdf_bytes)))
print("✅ category_management_handbook.pdf")

# COMMAND ----------

# MAGIC %md ## Market Intelligence Docs — CPG Market Intelligence KA

# COMMAND ----------

# ── Doc 7: CPG Market Trends 2024–2025 ───────────────────────────────────────

e = header("CPG Market Trends 2024–2025", "Category Trends, Macro Environment & Channel Shifts", "NovaLife Nutrition — Market Intelligence") + [
    Paragraph("1. Macro Environment", S["h1"]),
    Paragraph("The US CPG market grew 3.2% in dollar terms in 2024, driven by persistent price elasticity recovery following the 2021–2023 inflation cycle. Volume growth remained subdued at +0.8%, reflecting consumer value-seeking behavior. Private label penetration reached 21.4% of total CPG dollars in 2024, up from 19.6% in 2022.", S["body"]),

    Paragraph("2. Infant Formula & Baby Food Category Outlook", S["h1"]),
    tbl([
        ["Category",        "2024 Dollar Growth",  "2025E Growth",  "Key Driver",               "Key Risk"],
        ["Infant Formula",  "+2.1%",               "+1.8%",         "Premium/organic segment",  "Insurgent brand expansion"],
        ["Baby Food",       "+1.8%",               "+2.3%",         "Pouches / convenient formats","Private label acceleration"],
        ["Toddler Snacks",  "+4.2%",               "+5.1%",         "Health-positioned snacking","Ingredient scrutiny"],
    ], [1.3*inch, 1.3*inch, 1.1*inch, 2.1*inch, 1.7*inch]),
    Spacer(1, 8),

    Paragraph("3. Channel Shift Dynamics", S["h1"]),
    Paragraph("E-commerce now accounts for 18% of Infant Formula dollars (up from 11% in 2022). Subscribe-and-save formats on Amazon and brand DTC sites are driving loyalty lock-in for insurgent brands like Happy Roots and Bobbie Natural, where 40%+ of revenue comes from subscription. Traditional brands with low e-commerce ACV face structural share loss to online-first insurgents.", S["body"]),

    Paragraph("4. Consumer Trends Impacting Category", S["h1"]),
    Paragraph("Ingredient transparency: 68% of millennial parents in 2024 research infant formula ingredients online before purchase (up from 49% in 2021). Brands with clean-label positioning (no corn syrup solids, organic certification) are growing at 3× the category rate.", S["body"]),
    Paragraph("Pediatrician influence: 71% of first-time parents receive a specific formula recommendation from their pediatrician. Brand-to-HCP marketing investment remains a key competitive moat for established brands.", S["body"]),
    Paragraph("Price sensitivity: 54% of formula buyers reported trading down to store brand at least once during the 2022–2023 inflation peak. Retention of these switchers remains a challenge — estimated 30% have not returned to premium brands.", S["body"]),
] + footer_elem("NovaLife Nutrition Market Intelligence | Sources: Nielsen, Circana, Mintel, Consumer Surveys 2024")

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "cpg_market_trends_2024_2025.pdf", MARKET_PATH)
uploaded.append(("cpg_market_trends_2024_2025.pdf", MARKET_PATH, len(pdf_bytes)))
print("✅ cpg_market_trends_2024_2025.pdf")

# COMMAND ----------

# ── Doc 8: Private Label Threat Assessment ───────────────────────────────────

e = header("Private Label Threat Assessment", "Private Label Share Dynamics & Competitive Response Strategies", "NovaLife Nutrition — Market Intelligence") + [
    Paragraph("1. Private Label in Infant Formula — Current State", S["h1"]),
    Paragraph("Private label (store brand) Infant Formula holds 7.2% dollar share in Total US measured channels as of Q3 2024. This compares to 23% for Baby Food and 18% for Toddler Snacks. The relatively low PL share in Infant Formula reflects (1) regulatory complexity creating quality barriers, (2) high pediatrician recommendation rates reducing price sensitivity, and (3) strong emotional attachment to brand safety among first-time parents.", S["body"]),

    Paragraph("2. PL Growth Drivers", S["h1"]),
    tbl([
        ["Driver",                         "Impact on PL",   "Vulnerability for Manufacturer Brands"],
        ["Retailer strategic investment",  "High",           "Kroger, Walmart investing in premium PL tiers"],
        ["Consumer value-seeking post-inflation","Medium",   "30% of trade-down buyers may stay"],
        ["Quality parity perception gains","Medium-High",    "Closing quality perception gap among repeat buyers"],
        ["Digital-native parent research", "Low-Medium",     "Parents research online — brands can defend via content"],
    ], [2.1*inch, 0.9*inch, 3.5*inch]),
    Spacer(1, 8),

    Paragraph("3. Response Strategies", S["h1"]),
    Paragraph("Innovation moat: accelerate the innovation pipeline (NovaBaby Organics, NovaBaby Gentle) in segments where PL cannot follow easily. PL cannot credibly compete on 'first organic infant formula with HMO' positioning.", S["body"]),
    Paragraph("HCP engagement: strengthen pediatrician advocacy programs. A pediatrician recommendation reduces the probability of PL switching by 65% (internal consumer research, 2023).", S["body"]),
    Paragraph("Value-tier defense: introduce a targeted 'value formula' pack at a 10–12% premium to PL, providing a down-trade option within the NovaBaby portfolio rather than losing the consumer to PL entirely.", S["body"]),
] + footer_elem("NovaLife Nutrition Market Intelligence | Confidential")

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "private_label_threat_assessment.pdf", MARKET_PATH)
uploaded.append(("private_label_threat_assessment.pdf", MARKET_PATH, len(pdf_bytes)))
print("✅ private_label_threat_assessment.pdf")

# COMMAND ----------

# ── Doc 9: Omnichannel Distribution Dynamics ─────────────────────────────────

e = header("Omnichannel Distribution Dynamics", "Online vs. Offline Distribution Shifts & E-Commerce Velocity Metrics", "NovaLife Nutrition — Market Intelligence") + [
    Paragraph("1. Channel Architecture — Infant Formula 2024", S["h1"]),
    tbl([
        ["Channel",              "Dollar Share", "YoY Growth", "Velocity Benchmark", "NovaBaby Coverage"],
        ["Mass (Walmart/Target)","48%",          "+1.2%",      "High",               "88% ACV"],
        ["Grocery (Kroger etc.)",  "22%",          "+0.8%",      "Medium-High",        "82% ACV"],
        ["Drug (CVS/Walgreens)", "8%",           "−0.5%",      "Medium",             "71% ACV"],
        ["E-commerce (Amazon)",  "18%",          "+14.2%",     "Subscription-led",   "65% coverage"],
        ["Club (Costco/Sam's)",  "4%",           "+3.1%",      "Bulk pack focused",  "40% items"],
    ], [1.5*inch, 1.0*inch, 0.9*inch, 1.3*inch, 1.8*inch]),
    Spacer(1, 8),

    Paragraph("2. E-Commerce Velocity Metrics", S["h1"]),
    Paragraph("E-commerce velocity requires different metrics from brick-and-mortar due to the absence of physical shelf space constraints:", S["body"]),
    Paragraph("Digital Shelf Score = (Search Rank + Content Score + Review Quantity + Subscribe Rate) / 4", S["formula"]),
    Paragraph("Subscribe-and-Save Rate: % of units sold via recurring subscription. NovaBaby S&S rate is 28%, vs. Happy Roots at 44% — indicating stronger retention via the subscription mechanic for insurgents.", S["body"]),
    Paragraph("Page 1 Search Presence: % of time brand appears on page 1 for category keywords. NovaBaby maintains 85% P1 presence for 'infant formula' but only 42% for 'organic infant formula' — a gap being exploited by insurgents.", S["body"]),

    Paragraph("3. Omnichannel Shopper Journey", S["h1"]),
    Paragraph("Research online, buy offline (ROBO): 61% of infant formula purchase decisions begin with an online search, but 72% of units are purchased in physical stores. Winning the digital shelf is therefore a prerequisite for winning the physical shelf in this category.", S["body"]),
    Paragraph("Implications for distribution strategy: brands must treat Amazon, brand.com, and retailer.com as distribution channels, not just marketing channels. ACV equivalent metrics for e-commerce should be tracked alongside physical ACV.", S["body"]),
] + footer_elem("NovaLife Nutrition Market Intelligence")

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "omnichannel_distribution_dynamics.pdf", MARKET_PATH)
uploaded.append(("omnichannel_distribution_dynamics.pdf", MARKET_PATH, len(pdf_bytes)))
print("✅ omnichannel_distribution_dynamics.pdf")

# COMMAND ----------

# ── Doc 10: Retailer Power Dynamics ──────────────────────────────────────────

e = header("Retailer Power Dynamics — Walmart & Target", "Shelf Space Negotiation, Strategic Priorities & Partnership Frameworks", "NovaLife Nutrition — Market Intelligence") + [
    Paragraph("1. Walmart — Category Strategy", S["h1"]),
    Paragraph("Walmart accounts for 35% of NovaBaby's total US brick-and-mortar dollar sales. Walmart's buyer priority hierarchy: (1) price competitiveness, (2) private label assortment health, (3) supply chain reliability, (4) brand equity support. New item acceptance rate at Walmart for established brands is 65%; for new-to-category insurgents it has increased from 18% (2020) to 41% (2024) — reflecting Walmart's strategy to capture premium/natural shoppers.", S["body"]),
    tbl([
        ["Metric",                 "NovaBaby at Walmart",  "Category Leader Benchmark"],
        ["ACV Distribution %",     "88%",                  "90–95%"],
        ["Space Productivity",     "$420 / linear ft",     "$380 / linear ft"],
        ["Planogram Share",        "22%",                  "Should match dollar share (35%)"],
        ["Out-of-Stock Rate",      "2.8%",                  "<2.5% target"],
        ["S&S / Auto-Reorder",    "Not applicable",        "N/A physical"],
    ], [2.0*inch, 1.8*inch, 2.7*inch]),
    Spacer(1, 8),

    Paragraph("2. Target — Category Strategy", S["h1"]),
    Paragraph("Target accounts for 18% of NovaBaby brick-and-mortar sales. Target's buyer priority: (1) brand aesthetic and sustainability alignment, (2) exclusive or differentiated items, (3) omnichannel integration (Target Circle app offers). Target's baby care section skews toward premium/natural, making it a high-priority battleground for insurgent brands. Happy Roots launched its exclusive Target organic infant formula end-cap program in Q1 2024.", S["body"]),
    Paragraph("Strategic recommendation: NovaBaby Organics requires dedicated Target expansion plan in 2025. Current 55% ACV at Target for NovaBaby Organics is below the category natural segment average of 72%, representing a distribution gap of ~340 Target stores. Closing this gap is estimated to deliver $4.2M in incremental annual revenue.", S["alert"]),

    Paragraph("3. Joint Business Planning (JBP) Framework", S["h1"]),
    Paragraph("Annual JBP with Walmart and Target should include: (1) category growth investment commitment from NovaBaby, (2) mutually agreed share targets and shelf space allocation, (3) promotional calendar with agreed funding levels, (4) new item placement guarantees with performance clauses (velocity thresholds for continued listing).", S["body"]),
] + footer_elem("NovaLife Nutrition Market Intelligence | Confidential — Retailer Sensitive")

pdf_bytes = to_bytes(e)
upload_pdf(pdf_bytes, "retailer_power_dynamics_walmart_target.pdf", MARKET_PATH)
uploaded.append(("retailer_power_dynamics_walmart_target.pdf", MARKET_PATH, len(pdf_bytes)))
print("✅ retailer_power_dynamics_walmart_target.pdf")

# COMMAND ----------

# MAGIC %md ## Validation Summary

# COMMAND ----------

print("=" * 70)
print("  BRAND PERFORMANCE DOCUMENT GENERATION COMPLETE")
print("=" * 70)
print(f"\n  {'Filename':<55} {'Path':<20} {'Size (KB)':>9}")
print("  " + "─" * 87)
for fname, path, size in uploaded:
    pname = "analytics" if "analytics" in path else "market"
    print(f"  {fname:<55} {pname:<20} {size//1024:>8,} KB")

print(f"\n  Total: {len(uploaded)} PDFs uploaded")

# Confirm files exist
for fname, path, _ in uploaded:
    files = [f.name for f in dbutils.fs.ls(path)]
    assert fname in files, f"Missing: {path}/{fname}"

print("\n  All files confirmed in UC Volumes ✅")
print("""
Next steps:
  Run notebooks/03_create_uc_functions.py to register UC Functions.
""")
