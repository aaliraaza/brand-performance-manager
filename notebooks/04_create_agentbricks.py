# Databricks notebook source
# MAGIC %md
# MAGIC # Brand Performance Manager — Step 4: Create AgentBricks
# MAGIC
# MAGIC Creates all AI components in this order:
# MAGIC
# MAGIC | Step | Component | Tool |
# MAGIC |------|-----------|------|
# MAGIC | 1 | 5x Genie Spaces | `manage_genie` |
# MAGIC | 2 | 2x Knowledge Assistants | `manage_ka` |
# MAGIC | 3 | MAS #3 — Topline Agent (specialist sub-agent) | `manage_mas` |
# MAGIC | 4 | Brand Performance Manager (single execution supervisor) | `manage_mas` |
# MAGIC
# MAGIC > Intake & intent classification run in the app via the `enrich_user_request` UC
# MAGIC > Function, and the human-in-the-loop routing gate is owned by the app — so the
# MAGIC > former MAS #1 (Intake) and MAS #2 (Router) supervisors are no longer created.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - SPEC-01, SPEC-02, SPEC-03 must all be complete
# MAGIC - AI Dev Kit MCP server must be running in this session
# MAGIC - `manage_genie`, `manage_ka`, `manage_mas` MCP tools must be available

# COMMAND ----------

# MAGIC %md ## Configuration

# COMMAND ----------

CATALOG = "ar_dpcatalog"  # Update to your catalog
SCHEMA  = "brand_performance"
UTILS   = "brand_perf_utils"

GENIE_TABLE = lambda t: f"{CATALOG}.{SCHEMA}.{t}"
UC_FN       = lambda fn: f"{CATALOG}.{UTILS}.{fn}"
VOL_PATH    = lambda subdir: f"/Volumes/{CATALOG}/{SCHEMA}/raw_data/{subdir}"

print(f"Catalog : {CATALOG}")
print(f"Schema  : {SCHEMA}")
print(f"Utils   : {UTILS}")

# COMMAND ----------

# MAGIC %md ## Step 1 — Create Genie Spaces
# MAGIC
# MAGIC Run each cell below. The `manage_genie` tool returns a Genie Space ID (UUID).
# MAGIC Copy each ID into the `GENIE_IDS` dict in the cell that follows.

# COMMAND ----------

# MAGIC %md ### 1a. Context DB Genie Space (category_benchmarks)

# COMMAND ----------

# MCP tool call — run this cell with the AI Dev Kit MCP server active
manage_genie(
    action="create_or_update",
    name="BPM Context DB",
    description=(
        "Context database for the Brand Performance Manager. "
        "Answers questions about valid brand names, category names, retailer names, "
        "and region names available in the data. Also provides category-level benchmarks "
        "(average velocity, category growth rate, private label share) for context enrichment."
    ),
    tables=[GENIE_TABLE("category_benchmarks")],
    instructions="""
    You are the context reference database for a CPG brand performance system.
    Your primary purpose is to answer validation questions about what entities are available in the data.

    COMMON QUERIES you will receive:
    - "What brands are in the data?" → list unique brands from brand_topline_metrics
    - "What categories are available?" → list unique categories
    - "What retailers are tracked?" → list unique retailers
    - "What regions are in the data?" → list unique regions
    - "What is the category average velocity for Infant Formula?" → query category_benchmarks

    Always respond with the exact names as they appear in the data (case-sensitive).
    Limit responses to what is available in the schema — never make up entity names.
    """
)

# COMMAND ----------

# MAGIC %md ### 1b. Brand Analysis Genie Space (brand_topline_metrics)

# COMMAND ----------

manage_genie(
    action="create_or_update",
    name="BPM Brand Analysis",
    description=(
        "Analyzes weekly brand-level sales and value/volume share trends. "
        "Primary table: brand_topline_metrics. "
        "Supports: weekly share trend, latest N-week average share, YoY change, "
        "brand vs. category comparison, rolling L4W/L12W/L52W share."
    ),
    tables=[GENIE_TABLE("brand_topline_metrics")],
    instructions="""
    You are the brand analytics specialist. Query brand_topline_metrics to answer
    questions about brand performance.

    COMMON ANALYSIS PATTERNS:
    1. Share trend: SELECT week_ending, value_share_pct FROM brand_topline_metrics
       WHERE brand = '<brand>' AND retailer = '<retailer>' AND category = '<category>'
       ORDER BY week_ending DESC LIMIT <n_weeks>

    2. Latest N-week avg: SELECT AVG(value_share_pct) AS avg_share FROM brand_topline_metrics
       WHERE brand = '<brand>' AND week_ending >= DATEADD(WEEK, -<n>, CURRENT_DATE)

    3. Share delta: Compare current 4-week avg vs. prior 4-week avg

    Always return numeric data with units. Format share as XX.X% (1 decimal place).
    Return results sorted by week_ending DESC for trend charts.
    Include the exact SQL in your response for auditability.
    """
)

# COMMAND ----------

# MAGIC %md ### 1c. Topline Performance Genie Space (market_share_decomposition)

# COMMAND ----------

manage_genie(
    action="create_or_update",
    name="BPM Topline Performance",
    description=(
        "Share change decomposition analysis. "
        "Primary table: market_share_decomposition. "
        "Supports: 'what drove share change' analysis, distribution vs. rate contribution split, "
        "penetration/frequency/basket size drivers."
    ),
    tables=[GENIE_TABLE("market_share_decomposition")],
    instructions="""
    You are the share decomposition analyst. Query market_share_decomposition to explain
    what drove brand share changes.

    DECOMPOSITION QUERY PATTERN:
    SELECT
        brand,
        SUM(distribution_contribution_ppt) AS distribution_driver,
        SUM(rate_contribution_ppt) AS rate_driver,
        SUM(penetration_contribution_ppt) AS penetration_driver,
        SUM(frequency_contribution_ppt) AS frequency_driver,
        SUM(basket_size_contribution_ppt) AS basket_driver,
        SUM(share_change_ppt) AS total_change
    FROM market_share_decomposition
    WHERE brand = '<brand>'
      AND retailer = '<retailer>'
      AND week_ending >= DATEADD(WEEK, -<n_weeks>, CURRENT_DATE)
    GROUP BY brand

    Interpret results: identify the PRIMARY driver (largest |contribution|).
    If distribution_driver < 0: "losing shelf space". If rate_driver < 0: "pricing/mix headwind".
    Always state total share change in ppt, then break down the composition.
    """
)

# COMMAND ----------

# MAGIC %md ### 1d. Insurgent Brands Genie Space (insurgent_brand_tracker)

# COMMAND ----------

manage_genie(
    action="create_or_update",
    name="BPM Insurgent Brands",
    description=(
        "Tracks emerging and challenger brand performance. "
        "Primary table: insurgent_brand_tracker. "
        "Supports: fastest-growing insurgent brands, ACV gain analysis, threat scoring, "
        "52-week share gain ranking."
    ),
    tables=[GENIE_TABLE("insurgent_brand_tracker")],
    instructions="""
    You are the competitive intelligence analyst tracking insurgent and challenger brands.

    COMMON ANALYSIS PATTERNS:
    1. Top insurgent brands by share gain:
       SELECT brand, AVG(value_share_pct) AS avg_share, AVG(share_gain_52w_ppt) AS gain_52w,
              AVG(threat_score) AS avg_threat, AVG(acv_pct) AS avg_acv
       FROM insurgent_brand_tracker
       WHERE category = '<category>' AND week_ending >= DATEADD(WEEK, -12, CURRENT_DATE)
       GROUP BY brand ORDER BY gain_52w DESC

    2. ACV trajectory for a specific brand:
       SELECT week_ending, acv_pct, velocity_per_mm_acv, share_gain_4w_ppt
       FROM insurgent_brand_tracker WHERE brand = '<brand>' ORDER BY week_ending DESC LIMIT 12

    3. Direct competitor identification: WHERE is_direct_competitor = TRUE

    Sort results by threat_score DESC when asked for "biggest threats".
    Always include threat_score in your response (context: 0=low, 100=critical).
    """
)

# COMMAND ----------

# MAGIC %md ### 1e. Distribution & Velocity Genie Space (distribution_velocity)

# COMMAND ----------

manage_genie(
    action="create_or_update",
    name="BPM Distribution & Velocity",
    description=(
        "SKU-level ACV distribution and velocity metrics. "
        "Primary table: distribution_velocity. "
        "Supports: ACV gaps by retailer/region, velocity benchmarks, OOS analysis, "
        "distribution gain/loss trends, stores-selling count."
    ),
    tables=[GENIE_TABLE("distribution_velocity")],
    instructions="""
    You are the distribution and velocity analyst. Query distribution_velocity to answer
    questions about where and how well SKUs are distributed.

    COMMON ANALYSIS PATTERNS:
    1. Below-threshold ACV: SELECT sku_id, sku_name, brand, retailer, region, acv_pct
       FROM distribution_velocity WHERE acv_pct < <threshold>
       AND week_ending >= DATEADD(WEEK, -4, CURRENT_DATE)
       ORDER BY acv_pct ASC

    2. Velocity comparison:
       SELECT brand, AVG(velocity_per_mm_acv) AS avg_velocity, AVG(acv_pct) AS avg_acv
       FROM distribution_velocity WHERE week_ending >= DATEADD(WEEK, -12, CURRENT_DATE)
       GROUP BY brand ORDER BY avg_velocity DESC

    3. OOS hotspots:
       SELECT retailer, region, AVG(out_of_stock_rate_pct) AS oos_rate
       FROM distribution_velocity WHERE brand = '<brand>'
       GROUP BY retailer, region ORDER BY oos_rate DESC

    Format ACV as XX.X%. Flag any ACV < 60% as a "distribution gap".
    Include stores_selling counts when available (context: Walmart ~4,700 stores total).
    """
)

# COMMAND ----------

# MAGIC %md ### Collect Genie Space IDs
# MAGIC
# MAGIC After each `manage_genie` call above, note the returned Genie Space IDs and fill in the dict below.

# COMMAND ----------

# ⚠️  FILL IN THE ACTUAL IDs RETURNED BY manage_genie ABOVE
GENIE_IDS = {
    "CONTEXT_DB":          "<CONTEXT_DB_GENIE_SPACE_ID>",     # from cell 1a
    "BRAND_ANALYSIS":      "<BRAND_ANALYSIS_GENIE_SPACE_ID>",  # from cell 1b
    "TOPLINE_PERF":        "<TOPLINE_PERF_GENIE_SPACE_ID>",    # from cell 1c
    "INSURGENT":           "<INSURGENT_GENIE_SPACE_ID>",        # from cell 1d
    "DIST_VEL":            "<DIST_VEL_GENIE_SPACE_ID>",         # from cell 1e
}

# Validate — warn if placeholder values remain
for k, v in GENIE_IDS.items():
    if v.startswith("<"):
        print(f"⚠️  GENIE_IDS['{k}'] is still a placeholder. Fill it before running Step 3.")
    else:
        print(f"✅  Genie Space ID [{k}]: {v}")

# COMMAND ----------

# MAGIC %md ## Step 2 — Create Knowledge Assistants

# COMMAND ----------

# MAGIC %md ### 2a. Brand Analytics Framework KA

# COMMAND ----------

manage_ka(
    action="create_or_update",
    name="Brand Analytics Framework",
    description=(
        "Knowledge base for brand analytics methodology: share decomposition frameworks, "
        "Nielsen/Circana terminology, brand equity measurement, promotional ROI, "
        "and category management best practices."
    ),
    volume_path=VOL_PATH("analytics_docs"),
    instructions="""
    You are a CPG brand analytics methodology expert. Your knowledge comes from the Brand Analytics
    Framework documents uploaded to the analytics_docs volume.

    Respond to:
    - "What is ACV?" / Nielsen glossary definitions
    - "How do I interpret share decomposition results?" / rate vs. distribution driver guidance
    - "What is a good promotional ROI?" / benchmark guidance
    - "How should I think about brand equity vs. activation metrics?"
    - Category management principles and shelf optimization guidance

    Always cite the specific document and page where possible.
    Use the exact terminology from the documents (ACV %, velocity per MM ACV, L4W, L12W, L52W).
    If a question is better answered by querying live data, say: "For actual data, please ask the
    Brand Analysis or Distribution agents."
    """
)

# COMMAND ----------

# MAGIC %md ### 2b. CPG Market Intelligence KA

# COMMAND ----------

manage_ka(
    action="create_or_update",
    name="CPG Market Intelligence",
    description=(
        "Knowledge base for CPG market trends, private label dynamics, "
        "omnichannel distribution shifts, and retailer strategic context."
    ),
    volume_path=VOL_PATH("market_docs"),
    instructions="""
    You are a CPG market intelligence expert. Your knowledge comes from the Market Intelligence
    documents uploaded to the market_docs volume.

    Respond to:
    - Category-level market trends (Infant Formula, Baby Food, Toddler Snacks)
    - Private label threat context and competitive dynamics
    - Omnichannel and e-commerce distribution shifts
    - Walmart and Target strategic priorities and shelf dynamics
    - Macro environment context for category performance

    Always specify the time period your information covers (2024–2025 data).
    If asked about real-time data, refer the user to the live Genie Space analytics.
    """
)

# COMMAND ----------

# MAGIC %md ### Collect Knowledge Assistant Tile IDs
# MAGIC
# MAGIC Fill in the tile IDs returned by `manage_ka` above.

# COMMAND ----------

# ⚠️  FILL IN THE ACTUAL IDs RETURNED BY manage_ka ABOVE
KA_IDS = {
    "BRAND_ANALYTICS_FW":  "<BRAND_ANALYTICS_KA_TILE_ID>",  # from cell 2a
    "CPG_MARKET_INTEL":    "<CPG_MARKET_INTEL_KA_TILE_ID>",  # from cell 2b
}

for k, v in KA_IDS.items():
    if v.startswith("<"):
        print(f"⚠️  KA_IDS['{k}'] is still a placeholder. Fill it before running Step 3.")
    else:
        print(f"✅  KA Tile ID [{k}]: {v}")

# COMMAND ----------


# MAGIC %md ## Step 3 — Create MAS #3 (Topline Agent — specialist sub-agent)

# COMMAND ----------

manage_mas(
    action="create_or_update",
    name="Brand Performance Topline Agent",
    description=(
        "Answers topline brand performance questions including share trends, YoY performance, "
        "share decomposition, and 'what drove it' analysis."
    ),
    agents=[
        {
            "name": "brand_analyst",
            "genie_space_id": GENIE_IDS["BRAND_ANALYSIS"],
            "description": (
                "Run SQL analytics on brand_topline_metrics table. Use for: weekly brand sales, "
                "value share %, volume share %, YoY change, trend over N weeks. "
                "Always filter by brand and time window from the enriched request."
            ),
        },
        {
            "name": "category_analyst",
            "genie_space_id": GENIE_IDS["TOPLINE_PERF"],
            "description": (
                "Run SQL analytics on market_share_decomposition table. Use for: "
                "share change decomposition (distribution contribution, rate contribution, "
                "penetration, frequency, basket size), category-level share trends, "
                "driver analysis for 'what drove share change' questions."
            ),
        },
        {
            "name": "methodology_expert",
            "ka_tile_id": KA_IDS["BRAND_ANALYTICS_FW"],
            "description": (
                "Answer questions about analytical methodology and interpretation: "
                "how to interpret share decomposition results, what ACV-weighted velocity means, "
                "Nielsen/IRI glossary definitions, brand equity framework guidance, "
                "promotional ROI methodology, category management frameworks."
            ),
        },
    ],
    instructions="""
    You are the topline brand performance analyst.

    ANALYSIS APPROACH for 'what drove share change' questions:
    1. First call brand_analyst: get the actual share change (current - prior period).
    2. Then call category_analyst: get the decomposition (distribution_contribution, rate_contribution,
       penetration_contribution, frequency_contribution, basket_size_contribution).
    3. Identify the PRIMARY driver (largest absolute contribution).
    4. If the user asks "why" or "what drove it": optionally call methodology_expert to add
       interpretive context about that driver type.

    OUTPUT FORMAT:
    - Lead with the headline number: "[Brand] share changed by [X] ppt in [time window]"
    - List the decomposition contributions in order of size
    - Highlight the primary driver
    - If data supports a recommendation, add one concise action item

    ALWAYS include units: share in ppt (percentage points), sales in $M, time window in weeks.
    ALWAYS end your response with: "VISUALIZATION: [chart_type]|[x_axis]|[y_axis]|[title]"
    so the Streamlit app can request the appropriate chart from the Visualization Adapter.

    Example VISUALIZATION line:
    VISUALIZATION: waterfall|driver|contribution_ppt|NovaBaby Share Change Decomposition — Last 4W
    """,
    examples=[
        {
            "question": "Why did our topline share drop last 4 weeks?",
            "guideline": "Call brand_analyst for share delta, then category_analyst for decomposition",
        },
        {
            "question": "What is our value share trend over the last 52 weeks?",
            "guideline": "Call brand_analyst with 52-week filter, return weekly trend data; end with VISUALIZATION: line|week_ending|value_share_pct|...",
        },
        {
            "question": "What does ACV-weighted velocity mean?",
            "guideline": "Call methodology_expert — this is a methodology question, no VISUALIZATION needed",
        },
    ],
)

MAS3_ENDPOINT = "mas-topline-endpoint"  # confirm in output
print(f"✅  MAS #3 endpoint: {MAS3_ENDPOINT}")

# COMMAND ----------

# MAGIC %md ## Step 4 — Create the Brand Performance Manager (single supervisor)
# MAGIC
# MAGIC Intake and intent classification now happen in the Streamlit app via the
# MAGIC `enrich_user_request` UC Function, and the human-in-the-loop routing gate is
# MAGIC owned by the app. This supervisor is the **execution layer only**: it receives an
# MAGIC already-enriched, user-confirmed request carrying an explicit `ROUTE=` and
# MAGIC dispatches to exactly one specialist. (The former MAS #1 Intake and MAS #2 Router
# MAGIC supervisors have been removed — they added LLM hops and could not pause for HITL.)

# COMMAND ----------

manage_mas(
    action="create_or_update",
    name="Brand Performance Manager",
    description=(
        "Execution supervisor for brand performance questions. Receives an enriched, "
        "user-confirmed request with an explicit ROUTE and dispatches to one specialist "
        "(topline / insurgent brands / distribution & velocity)."
    ),
    agents=[
        {
            "name": "topline_agent",
            "endpoint_name": MAS3_ENDPOINT,
            "description": (
                "ROUTE=topline. Brand share trends, value/volume share, year-over-year "
                "performance, share decomposition (rate vs. distribution drivers), and "
                "'what drove it' analysis."
            ),
        },
        {
            "name": "insurgent_brands_analyst",
            "genie_space_id": GENIE_IDS["INSURGENT"],
            "description": (
                "ROUTE=insurgent_brands. Emerging / challenger brands gaining share, "
                "ACV-weighted velocity vs. portfolio, 52-week share-gain ranking."
            ),
        },
        {
            "name": "distribution_velocity_analyst",
            "genie_space_id": GENIE_IDS["DIST_VEL"],
            "description": (
                "ROUTE=distribution_velocity. ACV distribution gaps by retailer/region, "
                "SKU velocity benchmarks, out-of-stock rates, distribution gain/loss, "
                "stores-selling analysis."
            ),
        },
    ],
    instructions="""
    You are the execution layer for a brand performance assistant.

    The incoming message ALWAYS contains a line "ROUTE=<topline|insurgent_brands|distribution_velocity>"
    plus already-extracted context (brand, category, retailer, region, time_window_weeks).
    The request has ALREADY been validated and confirmed by the user in the app.

    YOUR ONLY JOB:
    1. Read the ROUTE value.
    2. Dispatch to the matching specialist (topline_agent / insurgent_brands_analyst /
       distribution_velocity_analyst), passing the context and question through verbatim.
    3. DO NOT perform intake, DO NOT ask for clarification, DO NOT ask for confirmation,
       DO NOT re-classify. Trust the ROUTE.

    Always quantify answers (share points, $, weeks). When the answer is chartable, end with:
    VISUALIZATION: <chart_type>|<x_field>|<y_field>|<title>
    """,
    examples=[
        {
            "question": ("ROUTE=topline. Context: brand=NovaBaby, retailer=Walmart, "
                         "time_window_weeks=4. Why did NovaBaby share drop last 4 weeks at Walmart?"),
            "guideline": "Dispatch to topline_agent. Do not re-route or re-confirm.",
        },
        {
            "question": ("ROUTE=insurgent_brands. Context: category=Infant Formula. "
                         "Which insurgent brands are gaining share?"),
            "guideline": "Dispatch to insurgent_brands_analyst.",
        },
        {
            "question": ("ROUTE=distribution_velocity. Context: region=Northeast. "
                         "Which SKUs have below-80% ACV?"),
            "guideline": "Dispatch to distribution_velocity_analyst.",
        },
    ],
)

MAS4_ENDPOINT = "mas-brand-performance-manager-endpoint"  # confirm in output
print(f"✅  Brand Performance Manager endpoint: {MAS4_ENDPOINT}")
print("    Set this as BPM_AGENT_ENDPOINT in app/app.yaml.")

# COMMAND ----------

# MAGIC %md ## Summary — Copy-Paste for app.yaml

# COMMAND ----------

print("=" * 70)
print("  AGENTBRICKS CREATION COMPLETE")
print("=" * 70)
print()
print("  ── Genie Space IDs ──────────────────────────────────────────────")
for k, v in GENIE_IDS.items():
    print(f"    {k:<25}: {v}")

print()
print("  ── Knowledge Assistant Tile IDs ─────────────────────────────────")
for k, v in KA_IDS.items():
    print(f"    {k:<25}: {v}")

print()
print("  ── MAS Endpoint Names ───────────────────────────────────────────")
for name, ep in [
    ("MAS #3 Topline (sub)",      MAS3_ENDPOINT),
    ("Brand Performance Mgr",     MAS4_ENDPOINT),
]:
    print(f"    {name:<25}: {ep}")

print()
print("  ── Copy to app/app.yaml ─────────────────────────────────────────")
print(f"    BPM_AGENT_ENDPOINT = {MAS4_ENDPOINT}")
print()
print("  ── Next Step ─────────────────────────────────────────────────────")
print("  1. Copy BPM_AGENT_ENDPOINT into brand-performance-manager/app/app.yaml")
print("  2. Set BPM_WAREHOUSE_ID in app/app.yaml")
print("  3. Deploy: databricks bundle deploy --target dev")
print("  4. Open the Databricks Apps URL in the browser")
