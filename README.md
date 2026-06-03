# Brand Performance Manager
## Multi-Agent CPG Analytics Application — Databricks AgentBricks

A hierarchical multi-agent AI application for CPG commercial teams. Answers natural-language questions about brand share performance, insurgent competitive threats, and distribution/velocity gaps — powered by Databricks AgentBricks (Supervisor Agents + Genie Spaces + Knowledge Assistants).

---

## Architecture

```
User (Browser)
    └── Databricks Apps (Streamlit)
            │
            │  PHASE 1 — classify (synchronous, no agent)
            │   └── UC Function: enrich_user_request   (ai_extract + ai_classify)
            │
            │  HITL GATE (session_state) — Confirm / Change route / Cancel
            │
            │  PHASE 2 — execute (one call, on Confirm)
            └── Brand Performance Manager  ← single execution supervisor; dispatches on ROUTE=
                    ├── MAS #3: Topline Agent           (sub-supervisor)
                    │       ├── Genie: BPM Brand Analysis      (brand_topline_metrics)
                    │       ├── Genie: BPM Topline Performance (market_share_decomposition)
                    │       └── KA:    Brand Analytics Framework
                    ├── Genie: BPM Insurgent Brands         (insurgent_brand_tracker)
                    └── Genie: BPM Distribution & Velocity  (distribution_velocity)

Charts: rendered deterministically in the app (Plotly from SQL) — no LLM viz endpoint.
```

**Human-in-the-Loop:** Intake/classification is a direct UC-function call, and the routing
decision is confirmed by the user in an **app-owned gate** (Streamlit `session_state`) before
Phase 2 runs. There is no Lakebase polling and no nested Intake/Router supervisors — a deployed
MAS endpoint is synchronous and cannot pause mid-run for a human, so the app orchestrates the
two phases. (`pending_confirmations` may be kept as an optional routing audit log.)

> **Divergences from the reference architecture:** this is a production-oriented realisation
> that deliberately deviates from the original reference diagram (no Intake/Router MAS, no LLM
> Visualization Adapter, no separate Planner). See **PRD §5.1** and **SDD §1.3** for the full
> mapping and rationale.

---

## Project Structure

```
brand-performance-manager/
├── PRD.md                              Product Requirements Document
├── SDD.md                              Software Design Document
├── SPECS.md                            Spec-driven development specs (SPEC-01 → SPEC-07)
├── run_setup.py                        Local setup runner — DDL + Lakebase table creation
├── databricks.yml                      Databricks Asset Bundle configuration
│
├── notebooks/
│   ├── 01_generate_brand_data.py       Generate 5 Delta tables (104W synthetic CPG data)
│   ├── 02_generate_brand_docs.py       Generate 10 KA PDFs (reportlab) → UC Volumes
│   ├── 03_create_uc_functions.py       Register 3 UC Functions (enrich / validate / visualize)
│   └── 04_create_agentbricks.py        Create Genie Spaces + KAs + 4 MAS agents via MCP
│
├── app/
│   ├── app.py                          Streamlit application (4-tab UI + HITL + Plotly)
│   ├── app.yaml                        Databricks Apps configuration
│   ├── requirements.txt                Python dependencies (pandas, plotly, psycopg2)
│   └── .gitignore
│
└── tests/
    ├── conftest.py                     Fakes `streamlit` so app.py imports for unit tests
    ├── test_uc_functions.py            enrich_user_request classifier (+ optional fns, skipped)
    ├── test_hitl_flow.py               Two-phase flow: Phase 1 gating + Phase 2 ROUTE directive
    ├── test_routing.py                 Phase 2 dispatch accuracy (integration)
    └── test_visualization.py           Deterministic Plotly rendering (unit)
```

---

## Setup Guide

### Prerequisites

- Databricks workspace with Unity Catalog enabled
- A SQL warehouse (running)
- A Lakebase project created in Databricks
- AI Dev Kit MCP server configured (for notebook 04)
- `databricks` CLI installed and configured

### Step 1 — Run Local Setup

```bash
cd brand-performance-manager

# Configure connection (or set env vars)
export DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
export DATABRICKS_TOKEN=dapi...
export BPM_WAREHOUSE_ID=your_warehouse_id
export BPM_CATALOG=your_catalog

# Create schemas, DDL, and Lakebase HITL table
python3 run_setup.py
```

### Step 2 — Run Data Generation Notebooks

Run these notebooks **on a Databricks cluster** in the order shown:

```
01_generate_brand_data.py   →  Creates 5 Delta tables (~75K total rows)
02_generate_brand_docs.py   →  Uploads 10 CPG PDFs to UC Volumes
03_create_uc_functions.py   →  Registers 3 UC Functions + smoke tests
```

Set `CATALOG` at the top of each notebook to match your catalog.

### Step 3 — Create AgentBricks (requires MCP)

Run notebook `04_create_agentbricks.py` in an environment where the **AI Dev Kit MCP server** is active. This notebook:

1. Creates 5 Genie Spaces
2. Creates 2 Knowledge Assistants
3. Creates 2 Supervisor Agents — MAS #3 Topline (sub), then the Brand Performance Manager (top)

After running, copy the `BPM_AGENT_ENDPOINT` value printed at the end into `app/app.yaml`.

### Step 4 — Configure & Deploy

```yaml
# app/app.yaml — update these two values:
- name: BPM_AGENT_ENDPOINT
  value: "mas-brand-performance-manager-endpoint"  # from step 3

- name: BPM_WAREHOUSE_ID
  value: "your_warehouse_id"
```

```bash
# Validate bundle
databricks bundle validate

# Deploy to dev
databricks bundle deploy --target dev

# Open the app URL (printed after deploy)
```

---

## Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `BPM_AGENT_ENDPOINT` | `app.yaml` | Brand Performance Manager (supervisor) endpoint name |
| `BPM_WAREHOUSE_ID` | `app.yaml` | SQL warehouse for KPI tiles + Phase 1 enrichment |
| `BPM_CATALOG` | `app.yaml` | Unity Catalog catalog name |
| `DATABRICKS_HOST` | Auto-injected | Workspace URL |
| `DATABRICKS_CLIENT_ID` | Auto-injected | Apps service principal |
| `DATABRICKS_CLIENT_SECRET` | Auto-injected | Apps service principal secret |
| `PGHOST` / `PGDATABASE` | Auto-injected | Lakebase PostgreSQL connection |

---

## Demo Scenario

**End-to-end flow:**

1. User opens the app → **Dashboard tab** shows KPI cards (brand value shares) and Plotly charts
2. User goes to **AI Advisor tab** and types: *"Why did NovaBaby share drop last 4 weeks at Walmart?"*
3. **Phase 1** — the app calls `enrich_user_request` → `brand=NovaBaby`, `retailer=Walmart`, `time_window=4W`, `question_type=topline`, `is_complete=true`
4. **HITL gate** appears in the sidebar — proposed route `Topline Performance` + context; user can **Confirm**, **Change route**, or **Cancel**. User clicks **✅ Confirm & Run**
5. **Phase 2** — the app calls the supervisor once with `ROUTE=topline` + context → it dispatches to **MAS #3 (Topline)**, which queries the Genie Spaces for share + decomposition
6. Agent returns: *"NovaBaby share declined 1.3 ppt L4W at Walmart. Primary driver: distribution loss (−0.8 ppt, 61% of decline)..."*
7. **Plotly chart** renders deterministically from a SQL query keyed on the route + context

---

## Data Schema

| Table | Rows | Description |
|-------|------|-------------|
| `brand_topline_metrics` | ~12,500 | Weekly brand sales + value/volume share |
| `market_share_decomposition` | ~12,500 | Share change decomposed into 5 drivers |
| `insurgent_brand_tracker` | ~16,600 | Emerging brand threat scores + ACV trends |
| `distribution_velocity` | ~41,600 | SKU-level ACV distribution + OOS |
| `category_benchmarks` | ~6,200 | Category norms (PL share, avg velocity) |

All tables cover 104 weeks (2 years) of history for 3 categories × 4 retailers × 5 regions.

---

## Related Documents

- [PRD.md](PRD.md) — Product requirements, user personas, success metrics
- [SDD.md](SDD.md) — Detailed technical design (agents, DDL, UC Functions, HITL, API contracts)
- [SPECS.md](SPECS.md) — Spec-driven development breakdown (SPEC-01 → SPEC-07)

---

*NovaLife Nutrition — Analytics Center of Excellence | Built with Databricks AgentBricks*
