# Product Requirements Document
# Brand Performance Manager — Multi-Agent AI Application

**Version:** 1.0  
**Status:** Draft  
**Date:** May 2026  
**Platform:** Databricks Agentic AI (AgentBricks, Genie, Databricks Apps)  
**Confidential: For internal use**

---

## 1. Executive Summary

The **Brand Performance Manager** is a CPG-industry AI application that gives commercial and strategy teams instant, conversational access to brand performance intelligence. Users ask natural language questions — "Why did our topline share drop last 4 weeks in Walmart?" — and the system routes those questions through a hierarchical chain of specialized AI agents, returns structured data analysis, and renders auto-generated visualizations. It replaces fragmented syndicated data workflows (Nielsen, IRI/Circana) that currently take analysts days with an answer in under 90 seconds.

---

## 2. Problem Statement

CPG commercial teams manage brand performance across dozens of categories, hundreds of retailers, and multiple time horizons. Today's workflow is broken:

| Pain Point | Current State | Business Impact |
|---|---|---|
| **Data fragmentation** | Topline, insurgent brands, and distribution data live in separate syndicated data feeds with no unified query layer | Analysts spend 2–3 days per insight request |
| **Insight latency** | Weekly reporting cadence means competitive threats (insurgent brands gaining velocity) are spotted 2–3 weeks late | Revenue loss from delayed response |
| **Visualization bottleneck** | Charts require manual Excel / Tableau work after data is extracted | Decision-ready outputs take hours |
| **Expert dependency** | Only senior analysts know which SQL queries to run across which tables | Insight generation doesn't scale |
| **No routing intelligence** | Users don't know whether their question is a "topline" question, an "insurgent brand" question, or a "distribution" question | Wrong data surfaces, decisions made on incomplete information |

---

## 3. Goals

### Primary Goals
- Provide a single natural-language chat interface covering all brand performance question types
- Route queries intelligently to the right specialized agent with human confirmation before execution
- Return structured, chart-ready answers in under 90 seconds end-to-end

### Secondary Goals
- Validate and enrich every user request before processing (context enrichment)
- Generate Plotly visualizations automatically from agent output
- Deploy fully on Databricks Apps (no external infrastructure)

### Non-Goals
- This is not a replacement for the full Tableau/Looker BI layer
- Does not handle financial planning/forecasting (separate system)
- Does not cover supply chain or operations data

---

## 4. Users & Personas

| Persona | Role | Primary Questions |
|---|---|---|
| **VP Commercial** | Executive sponsor | "What is our total brand share vs. 12 weeks ago?" |
| **Brand Manager** | Day-to-day owner | "Which subcategories are driving our share loss?" |
| **Category Analyst** | Data power user | "Show me insurgent brands gaining >1pt share in the last 8 weeks in the baby food category" |
| **Sales Director** | Field + retailer focus | "Which of our SKUs have below-threshold ACV in the Northeast?" |

---

## 5. Architecture Overview

The application is a fully native Databricks Agentic AI system. Intake/classification
and the human-in-the-loop (HITL) routing gate are **owned by the Streamlit app** (a
synchronous two-phase flow); a single supervisor agent is the execution layer that
dispatches a pre-confirmed request to one specialist. This avoids nested supervisors
(which compound latency) and the unsupported "pause-and-resume mid-agent" pattern (a
deployed MAS endpoint is a synchronous request/response and cannot block on a human).

```
User Request
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Databricks App (Streamlit)   app/app.py                         │
│                                                                   │
│  PHASE 1 — classify (synchronous, no agent)                       │
│    └── UC Function: enrich_user_request(question)                 │
│          → {brand, category, time_window, retailer, region,       │
│             question_type, is_complete, missing_params}           │
│          • out_of_scope / incomplete → reply or clarify, stop     │
│                                                                   │
│  HITL GATE (Streamlit session_state — no DB, no polling)          │
│    └── show proposed route + context; Confirm / Change route      │
│                                                                   │
│  PHASE 2 — execute (on Confirm, one supervisor call)              │
└─────────────────────────┬─────────────────────────────────────────┘
                          │  x-forwarded-access-token auth; ROUTE=<…> + context
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Brand Performance Manager — single execution supervisor (MAS)   │
│  Reads ROUTE and dispatches to exactly one specialist:            │
└──┬───────────────────────┬────────────────────────┬──────────────┘
   ▼                       ▼                        ▼
MAS #3 Topline        Genie Space              Genie Space
(sub-supervisor)      Insurgent Brands         Distribution & Velocity
   │
   ├── Genie: Brand Analysis      (brand_topline_metrics)
   ├── Genie: Topline Performance (market_share_decomposition)
   └── KA:    Brand Analytics Framework
   │
   ▼
Agent returns answer + VISUALIZATION hint
    │
    ▼
App renders Plotly chart deterministically (SQL keyed on route + context)
    │
    ▼
Rendered in Streamlit
```

> **Removed vs. the original reference diagram:** MAS #1 (Intake) and MAS #2 (Router)
> are no longer supervisor agents — intake is a direct UC-function call and routing is
> the app-owned HITL gate. The standalone LLM "Visualization Adapter" endpoint is
> replaced by deterministic Python/Plotly rendering driven by SQL.

---

## 6. Agent Inventory

### Phase 1 — Intake & Enrichment (app-owned, not a supervisor)

**Purpose:** Validate and enrich every user request before the routing gate. Implemented
as a **single direct UC-function call from the Streamlit app** (`enrich_user_request`) —
not a MAS — because intake is a deterministic one-shot extraction, and wrapping it in a
supervisor only adds an LLM hop and latency.

**Mechanism:** `enrich_user_request(question)` (SQL UC Function using `ai_extract` +
`ai_classify`) returns a struct: `brand, category, time_window_weeks, retailer, region,
question_type, is_complete, missing_params`.

**App logic:**
- `question_type == out_of_scope` → reply with scope explanation, stop
- `is_complete == false` → ask the user for `missing_params`, stop
- complete → set the enriched context and open the HITL gate (Phase 1 → gate)

> Entity validation (valid brand/retailer/category names) is best served by a direct
> lookup against a reference table rather than a Genie Space NL→SQL round-trip; the
> "Context DB Genie" remains available but is not on the critical path.

---

### HITL Routing Gate (app-owned, synchronous)

**Purpose:** Show the user the proposed route + enriched context and let them confirm or
change it **before** any analysis runs. The gate lives entirely in Streamlit
`session_state` — there is no Lakebase write, no polling, and no LLM-generated join key.

**Routing outputs:** `topline` → MAS #3 Topline Agent · `insurgent_brands` → Insurgent
Brands Genie · `distribution_velocity` → Distribution & Velocity Genie.

**HITL Flow (corrected — two-phase, app-orchestrated):**
1. Phase 1 returns `{enriched_context, question_type}` → app proposes `route = question_type`.
2. App renders a confirmation card (route + why + context) with **Confirm & Run** / **Change route** / **Cancel**.
3. On **Confirm**, the app invokes the supervisor **once** (Phase 2) with `ROUTE=<route>` + context. **Change route** lets the user override the proposal before running.
4. The supervisor dispatches to the chosen specialist and returns the answer.

> **Why not a Router MAS + Lakebase pause/resume?** A deployed MAS endpoint is a
> synchronous request/response and cannot suspend mid-run to wait for a human, so the
> earlier "write PENDING → poll → agent resumes" design dead-ended at confirmation. The
> app owning the gate makes the resume real. Lakebase may still be used as an **audit
> log** of routing decisions (best-effort, off the critical path) to support the
> HITL-confirmation-rate metric.

---

### MAS #3 — Topline Agent

**Purpose:** Orchestrate complex topline performance questions that require brand-level, category-level, and "what drove it" analysis simultaneously. Uses a Planner → Orchestrator pattern to decompose questions before executing.

**Sub-agents:**
| Agent | Type | Data |
|---|---|---|
| `brand_analysis` | Genie Space | `brand_topline_metrics` table — weekly brand sales, value share, volume share |
| `category_analysis` | Genie Space | `market_share_decomposition` table — category share drivers, benchmarks |
| `what_analysis` | Knowledge Assistant | Brand analytics methodology PDFs, share decomposition frameworks |

**Planner Agent (Model Serving Endpoint):**
- Receives the enriched user question
- Decomposes it into 2–3 parallel sub-queries (one per domain)
- Passes sub-queries to the Orchestrator (MAS #3 internal routing)

**Topline Agent output** → feeds into Visualization Adapter

**Databricks service:** `manage_mas` with `genie_space_id` × 2 + `ka_tile_id` × 1

---

### Insurgent Brands Agent

**Purpose:** Answer questions about emerging brands gaining share at the expense of the manufacturer's portfolio.

**Type:** Genie Space  
**Tables:** `insurgent_brand_tracker`  
**Sample questions:**
- "Which challenger brands gained >0.5pt share in the baby food category last 12 weeks?"
- "What is the ACV-weighted velocity of [Brand X] in Walmart vs. our flagship SKU?"
- "Show me the insurgent brand share trend over the last 52 weeks in the beverage aisle"

---

### Distribution & Velocity Agent

**Purpose:** Answer questions about SKU distribution health and velocity at the retailer/region level.

**Type:** Genie Space  
**Tables:** `distribution_velocity`  
**Sample questions:**
- "Which SKUs have below-80% ACV in the Southeast region?"
- "What is the velocity trend for our premium SKU at Target vs. Walmart?"
- "Show me distribution gains/losses this quarter vs. prior quarter"

---

### Visualization Adapter

**Purpose:** Convert raw tabular data from any domain agent into a Plotly chart specification rendered directly in Streamlit.

**Type:** Model Serving Endpoint (LLM-based)  
**Input:** JSON array of rows from the responding Genie Space + question context  
**Output:** Plotly `go.Figure` JSON spec  
**Rendering:** `st.plotly_chart(fig)` in the Streamlit app

---

## 7. Data Model

**Unity Catalog location:** `{catalog}.brand_performance`

### Tables

#### `brand_topline_metrics`
Weekly brand-level sales performance data.

| Column | Type | Description |
|---|---|---|
| `week_ending` | DATE | Week end date (Saturday) |
| `brand` | STRING | Brand name |
| `category` | STRING | Category hierarchy |
| `retailer` | STRING | Retailer name |
| `region` | STRING | Nielsen/IRI geographic region |
| `dollar_sales` | DOUBLE | Total dollar sales ($) |
| `unit_sales` | BIGINT | Total unit volume |
| `value_share_pct` | DOUBLE | Dollar share of category (%) |
| `volume_share_pct` | DOUBLE | Unit share of category (%) |
| `l4w_value_share` | DOUBLE | Rolling 4-week average value share (%) |
| `l12w_value_share` | DOUBLE | Rolling 12-week average value share (%) |
| `l52w_value_share` | DOUBLE | Rolling 52-week average value share (%) |
| `yoy_dollar_chg_pct` | DOUBLE | Year-over-year dollar change (%) |
| `yoy_volume_chg_pct` | DOUBLE | Year-over-year volume change (%) |

#### `market_share_decomposition`
Decomposition of share change into rate (pricing/mix) and distribution drivers.

| Column | Type | Description |
|---|---|---|
| `week_ending` | DATE | Week end date |
| `brand` | STRING | Brand name |
| `category` | STRING | Category |
| `share_change_ppt` | DOUBLE | Share change in percentage points vs. prior period |
| `distribution_contribution_ppt` | DOUBLE | Share points from distribution changes |
| `rate_contribution_ppt` | DOUBLE | Share points from price/mix changes |
| `penetration_contribution_ppt` | DOUBLE | Share points from shopper penetration |
| `frequency_contribution_ppt` | DOUBLE | Share points from purchase frequency |
| `basket_size_contribution_ppt` | DOUBLE | Share points from basket size |

#### `insurgent_brand_tracker`
Emerging and challenger brand performance signals.

| Column | Type | Description |
|---|---|---|
| `week_ending` | DATE | Week end date |
| `brand` | STRING | Insurgent brand name |
| `parent_company` | STRING | Parent company |
| `category` | STRING | Category competing in |
| `retailer` | STRING | Retailer |
| `value_share_pct` | DOUBLE | Dollar share of category (%) |
| `acv_pct` | DOUBLE | All Commodity Volume distribution (%) |
| `velocity_per_mm_acv` | DOUBLE | Sales velocity per million ACV |
| `share_gain_4w_ppt` | DOUBLE | 4-week share gain in percentage points |
| `share_gain_52w_ppt` | DOUBLE | 52-week share gain in percentage points |
| `threat_score` | DOUBLE | Composite threat score (0 = low, 100 = critical) |
| `is_direct_competitor` | BOOLEAN | True if brand is a direct substitute for manufacturer portfolio |

#### `distribution_velocity`
SKU-level distribution and velocity at retailer/region granularity.

| Column | Type | Description |
|---|---|---|
| `week_ending` | DATE | Week end date |
| `sku_id` | STRING | Internal SKU identifier |
| `sku_name` | STRING | SKU display name |
| `brand` | STRING | Brand |
| `retailer` | STRING | Retailer |
| `region` | STRING | Geographic region |
| `acv_pct` | DOUBLE | % ACV distribution |
| `velocity_per_mm_acv` | DOUBLE | $ velocity per million ACV |
| `stores_selling` | BIGINT | Number of stores selling the SKU |
| `out_of_stock_rate_pct` | DOUBLE | Estimated out-of-stock rate (%) |
| `yoy_acv_chg_ppt` | DOUBLE | Year-over-year ACV change in percentage points |

#### `category_benchmarks`
Category-level norms used for context enrichment and "what analysis."

| Column | Type | Description |
|---|---|---|
| `category` | STRING | Category name |
| `retailer` | STRING | Retailer |
| `avg_value_share_leader_pct` | DOUBLE | Category leader average share (%) |
| `avg_velocity_per_mm_acv` | DOUBLE | Category average velocity benchmark |
| `total_category_dollar_sales` | DOUBLE | Total category dollar sales |
| `yoy_category_growth_pct` | DOUBLE | Category year-over-year growth (%) |
| `week_ending` | DATE | Reference week |

### HITL Table (Lakebase — PostgreSQL)

**`brand_perf.hitl.pending_confirmations`**

| Column | Type | Description |
|---|---|---|
| `confirmation_id` | UUID | Unique confirmation identifier |
| `session_id` | TEXT | Streamlit session ID |
| `query_text` | TEXT | Original user question |
| `enriched_context` | JSONB | Extracted brand, category, time window |
| `proposed_route` | TEXT | Agent path: topline / insurgent_brands / distribution |
| `route_explanation` | TEXT | Human-readable explanation of routing decision |
| `status` | TEXT | PENDING / CONFIRMED / REJECTED / TIMEOUT |
| `created_at` | TIMESTAMPTZ | Timestamp |
| `resolved_at` | TIMESTAMPTZ | When user confirmed/rejected |

---

## 8. Knowledge Assistants

### Brand Analytics Framework KA

**Volume path:** `/Volumes/{catalog}/brand_performance/raw_data/analytics_docs/`

| Document | Purpose |
|---|---|
| `brand_share_decomposition_framework.pdf` | Methodology for decomposing share change into rate, distribution, penetration, frequency |
| `nielsen_iri_glossary_cpg.pdf` | Syndicated data terminology, ACV definition, velocity calculations |
| `brand_equity_measurement_guide.pdf` | How to interpret brand equity vs. activation metrics |
| `cpg_competitive_response_playbook.pdf` | How to assess and respond to insurgent brand threats |
| `promotional_roi_framework.pdf` | Trade promotion evaluation methodology |
| `category_management_handbook.pdf` | Category review frameworks, shelf optimization principles |

### CPG Market Intelligence KA

**Volume path:** `/Volumes/{catalog}/brand_performance/raw_data/market_docs/`

| Document | Purpose |
|---|---|
| `cpg_market_trends_2024_2025.pdf` | Category trends, macro CPG environment |
| `private_label_threat_assessment.pdf` | Private label share dynamics and competitive response |
| `omnichannel_distribution_dynamics.pdf` | Online vs. offline distribution shifts |
| `retailer_power_dynamics_walmart_target.pdf` | Retailer negotiation context and strategic priorities |

---

## 9. Unity Catalog Functions

### `brand_perf.utils.enrich_user_request`

```sql
CREATE FUNCTION brand_perf.utils.enrich_user_request(query STRING)
RETURNS STRUCT<
  brand STRING,
  category STRING,
  time_window_weeks INT,
  retailer STRING,
  question_type STRING,
  is_complete BOOLEAN,
  missing_params ARRAY<STRING>
>
COMMENT 'Extract structured context from natural language brand performance questions'
```

**Logic:** Uses `ai_query()` with a prompt to extract brand names, categories, time windows, and retailers from user input. Sets `is_complete = false` and populates `missing_params` if critical fields are absent.

---

### `brand_perf.utils.validate_routing_decision`

```sql
CREATE FUNCTION brand_perf.utils.validate_routing_decision(
  query_id STRING,
  session_id STRING,
  question_type STRING,
  proposed_route STRING,
  route_explanation STRING
)
RETURNS STRING
COMMENT 'Write HITL confirmation request to Lakebase and return confirmation_id'
```

**Logic:** Inserts a row into `pending_confirmations` Lakebase table. Returns the `confirmation_id` for Streamlit to poll.

---

### `brand_perf.utils.format_visualization_spec`

```sql
CREATE FUNCTION brand_perf.utils.format_visualization_spec(
  data_json STRING,
  chart_type STRING,
  title STRING
)
RETURNS STRING
COMMENT 'Convert tabular data JSON into a Plotly figure JSON spec'
```

**Logic:** Uses `ai_query()` to call an LLM that generates a Plotly-compatible JSON spec from the data. Returns a `go.Figure`-serializable JSON string.

---

## 10. Application — Streamlit on Databricks Apps

**Path:** `brand-performance-manager/app/app.py`  
**Runtime:** Databricks Apps (Streamlit)

### Key UI Sections

| Tab / Section | Purpose |
|---|---|
| **Brand Performance Chat** | Main conversational interface — wired to MAS #4 top-level endpoint |
| **HITL Confirmation Panel** | Polls `pending_confirmations` every 3s; shows routing decision card; Confirm / Reject buttons |
| **Visualization Canvas** | Renders Plotly chart from Visualization Adapter output |
| **Context Sidebar** | Shows extracted brand/category/time window context from Intake Agent |
| **Analysis History** | Scrollable list of past Q&A + charts from this session |

### Auth Pattern

Uses `x-forwarded-access-token` from `st.context.headers` — the Databricks Apps platform injects the user's identity token, so no hardcoded credentials are needed. Falls back to M2M OAuth for service-to-service calls.

```python
def _auth_token() -> str:
    # Priority: user token → M2M OAuth
    user_tok = st.context.headers.get("x-forwarded-access-token", "")
    if user_tok:
        return user_tok
    return _m2m_token()   # cached, ttl=3300s
```

### HITL Polling Loop

```python
# In Streamlit: poll Lakebase every 3s for pending confirmations
if st.session_state.get("awaiting_confirmation"):
    conf_id = st.session_state["confirmation_id"]
    row = query_sql(f"""
        SELECT * FROM brand_perf_lakebase.hitl.pending_confirmations
        WHERE confirmation_id = '{conf_id}' AND status = 'PENDING'
    """)
    if not row.empty:
        st.info(f"Routing to: **{row['proposed_route'][0]}**\n\n{row['route_explanation'][0]}")
        col1, col2 = st.columns(2)
        if col1.button("Confirm", type="primary"):
            # Update row to CONFIRMED → agent resumes
            ...
        if col2.button("Change Route"):
            # Update row to REJECTED → present alternatives
            ...
```

### Visualization Rendering

```python
def render_agent_response(response_text: str):
    # Try to parse Plotly JSON from response
    if response_text.strip().startswith('{"data"'):
        import plotly.io as pio
        fig = pio.from_json(response_text)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(response_text)
```

---

## 11. Setup & Deployment

### Prerequisites
- Databricks workspace with Unity Catalog enabled
- `{your_catalog}` catalog created (update `CATALOG` constant in all notebooks)
- Databricks CLI configured with appropriate profile
- AI Dev Kit MCP server running (for `manage_mas`, `manage_ka`, `manage_genie` tool calls)
- Lakebase project created for HITL table

### Setup Steps

```bash
# 1. Generate all Delta tables + PDFs (single command)
python3 brand-performance-manager/run_setup.py

# 2. Create UC Functions — run notebook 03 in Databricks workspace
# 3. Create Genie Spaces, KAs, and MAS agents — run notebook 04 via AI assistant MCP
# 4. Deploy the app
cd brand-performance-manager/app
databricks apps deploy --profile <YOUR_PROFILE>
```

### Setup Notebooks

| Notebook | What it creates |
|---|---|
| `01_generate_brand_data.py` | 5 Delta tables in `{catalog}.brand_performance` schema |
| `02_generate_brand_docs.py` | 10 PDFs uploaded to UC Volume (2 KA document sets) |
| `03_create_uc_functions.py` | `enrich_user_request` (required) + 2 optional UC Functions, with `EXECUTE` grants |
| `04_create_agentbricks.py` | 5 Genie Spaces + 2 KAs + 2 Supervisors (MAS #3 Topline + Brand Performance Manager) via MCP |

### Environment Variables (`app.yaml`)

| Variable | Source | Description |
|---|---|---|
| `BPM_AGENT_ENDPOINT` | Set after notebook 04 | Brand Performance Manager (supervisor) endpoint name |
| `BPM_WAREHOUSE_ID` | Your SQL warehouse | For `query_sql()` — KPI tiles + Phase 1 enrichment |
| `BPM_CATALOG` | Your catalog | Unity Catalog catalog name |
| `DATABRICKS_CLIENT_ID` | Auto-injected by Apps | OAuth M2M (fallback) |
| `DATABRICKS_CLIENT_SECRET` | Auto-injected by Apps | OAuth M2M (fallback) |
| `PGHOST` / `PGDATABASE` | Auto-injected by Apps | Lakebase connection (optional audit log only) |

---

## 12. Databricks Services Used

| Service | Usage | Count |
|---|---|---|
| **AgentBricks — Supervisor Agent (MAS)** | Single execution supervisor + MAS #3 Topline sub-supervisor | 2 |
| **AgentBricks — Knowledge Assistant** | Document RAG (brand frameworks, market intelligence) | 2 |
| **Genie Spaces** | Natural language SQL analytics (topline, insurgent, distribution, category, context) | 5 |
| **Unity Catalog Functions** | `enrich_user_request` (required) + 2 optional | 1 + 2 |
| **Model Serving Endpoints** | None — charts rendered deterministically in-app | 0 |
| **Databricks Apps** | Streamlit frontend hosting + Phase 1/2 orchestration + HITL gate | 1 |
| **Lakebase (PostgreSQL)** | Optional routing audit log (off the critical path) | 0–1 |
| **Unity Catalog Volumes** | PDF document storage for KAs | 2 |
| **Delta Tables** | Brand performance data layer | 5 |
| **Statement Execution API** | `query_sql()` — KPI tiles + Phase 1 `enrich_user_request` | Used in app |

---

## 13. Success Metrics

| Metric | Target |
|---|---|
| End-to-end answer latency (p50) | < 45 seconds |
| End-to-end answer latency (p90, Genie path) | < 90 seconds |
| Routing accuracy (correct agent path) | > 90% |
| HITL confirmation rate (user confirms first suggestion) | > 80% |
| Visualization render success rate | > 95% |
| User sessions per week (post-launch) | > 20 |

---

## 14. Out of Scope for v1

- Fine-tuned LLM for CPG domain (use platform LLM via Genie + `ai_query`)
- Real syndicated data integration (demo uses synthetic data)
- Multi-turn memory across sessions (session history only, no cross-session persistence)
- Mobile-optimized UI
- Export to PDF / PowerPoint

---

## 15. File Structure

```
brand-performance-manager/
├── PRD.md                                  ← This document
├── README.md                               ← Setup instructions
├── run_setup.py                            ← Single-command data setup script
├── create_agentbricks.py                   ← AgentBricks creation (run via AI assistant MCP)
├── databricks.yml                          ← DAB bundle for deployment
├── notebooks/
│   ├── 01_generate_brand_data.py           ← 5 Delta tables
│   ├── 02_generate_brand_docs.py           ← 10 PDFs → UC Volume
│   ├── 03_create_uc_functions.py           ← 3 UC Functions
│   └── 04_create_agentbricks.py           ← MAS #3 + Brand Performance Mgr + Genie + KA
└── app/
    ├── app.py                              ← Streamlit Databricks App
    ├── app.yaml                            ← App env vars
    ├── databricks.yml                      ← App-level DAB bundle
    └── requirements.txt                    ← pandas, plotly
```

---

*Document owner: AI Dev Kit · Databricks CPG Industry Team*
