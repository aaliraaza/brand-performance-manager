# SPECS.md — Brand Performance Manager
# Spec-Driven Development Decomposition

**Derived from:** PRD.md v1.0 + SDD.md v1.0  
**Date:** May 2026  
**Purpose:** Break the PRD/SDD into discrete, independently-implementable specs. Each spec defines the contract, acceptance criteria, and dependencies for one deliverable file. Use these specs as the authoritative prompt context when asking Claude to implement each component.

---

## Build Order & Dependency Chain

```
SPEC-01: 01_generate_brand_data.py       (no dependencies)
    ↓
SPEC-02: 02_generate_brand_docs.py       (no dependencies — can run in parallel with SPEC-01)
    ↓
SPEC-03: 03_create_uc_functions.py       (requires SPEC-01 tables to exist)
    ↓
SPEC-04: 04_create_agentbricks.py        (requires SPEC-01, SPEC-02, SPEC-03)
    ↓
SPEC-05: app/app.py                      (requires SPEC-04 endpoint names)
SPEC-06: app/app.yaml + databricks.yml   (requires SPEC-04 endpoint names)
    ↓
SPEC-07: tests/                          (requires all above)
```

---

## SPEC-01 — Delta Table Generation

**File:** `brand-performance-manager/notebooks/01_generate_brand_data.py`  
**PRD ref:** Section 7 (Data Model)  
**SDD ref:** Section 4 (Data Layer Design)

### Inputs
- `CATALOG` — string constant, set at top of notebook (e.g. `"ar_dpcatalog"`)
- No external dependencies required

### Outputs
Five Delta tables in `{CATALOG}.brand_performance`:

| Table | Min Rows | Weeks of History |
|---|---|---|
| `brand_topline_metrics` | 10,000 | 104 |
| `market_share_decomposition` | 5,000 | 104 |
| `insurgent_brand_tracker` | 15,000 | 104 |
| `distribution_velocity` | 40,000 | 104 |
| `category_benchmarks` | 1,000 | 104 |

### Schema contracts
Use the exact DDL from SDD Section 4.2 for all five tables — including all column names, types, NOT NULL constraints, COMMENT annotations, and TBLPROPERTIES.

Additional columns present in SDD (beyond PRD): include them all:
- `brand_topline_metrics`: `manufacturer`, `subcategory`, `l4w_value_share`, `l12w_value_share`, `l52w_value_share`
- `market_share_decomposition`: `price_index_vs_category`, `promotion_support_pct`
- `insurgent_brand_tracker`: `subcategory`, `volume_share_pct`, `share_gain_4w_ppt`, `share_gain_12w_ppt`, `is_direct_competitor`, `threat_score`
- `distribution_velocity`: `total_stores`, `yoy_velocity_chg_pct`, `facings`, `shelf_position`
- `category_benchmarks`: `region`, `top3_concentration_pct`, `private_label_share_pct`, `avg_price_per_unit`, `promotional_pressure_pct`

### Data realism constraints
- `value_share_pct` values for all brands in a given week/retailer/region must sum to approximately 100%
- `dollar_sales` must be in realistic CPG ranges: $500K–$50M per brand/week/retailer
- `share_gain_52w_ppt` for insurgent brands: mix of negative, near-zero, and positive values (−2 to +3 ppt range)
- `acv_pct` for distribution: 10–98% range (never exactly 0 or 100)
- `out_of_stock_rate_pct`: 0–15% range
- Brands to include in `brand_topline_metrics` and `market_share_decomposition`: at least 3 manufacturer brands + 2–3 insurgent overlap brands
- Retailers: at minimum `["Walmart", "Target", "Kroger", "Total US"]`
- Regions: at minimum `["Total US", "Northeast", "Southeast", "Midwest", "West"]`
- Categories: at minimum `["Infant Formula", "Baby Food", "Toddler Snacks"]`

### Acceptance criteria
- [ ] Schema `{CATALOG}.brand_performance` is created if it does not exist
- [ ] All 5 tables are created with `CREATE TABLE IF NOT EXISTS`
- [ ] All 5 tables have row counts ≥ the minimums in the table above
- [ ] `SELECT COUNT(*) FROM {table}` is printed for each table before notebook exits
- [ ] `value_share_pct` values are between 0 and 100 for all rows
- [ ] No NULL values in any NOT NULL column
- [ ] Tables are partitioned or have `autoOptimize` enabled per SDD DDL
- [ ] Notebook exits with a success message and no uncaught exceptions

### Dependencies
- None

---

## SPEC-02 — Knowledge Assistant Document Generation

**File:** `brand-performance-manager/notebooks/02_generate_brand_docs.py`  
**PRD ref:** Section 8 (Knowledge Assistants)  
**SDD ref:** Section 1.2 (Deployment Boundaries — Volumes)

### Inputs
- `CATALOG` — string constant at top of notebook

### Outputs
Ten PDF files uploaded to Unity Catalog Volumes:

**Brand Analytics Framework KA** → `/Volumes/{CATALOG}/brand_performance/raw_data/analytics_docs/`

| Filename | Min Pages | Content summary |
|---|---|---|
| `brand_share_decomposition_framework.pdf` | 4 | Rate vs. distribution decomposition methodology, formulas, worked example |
| `nielsen_iri_glossary_cpg.pdf` | 5 | ACV definition, velocity calculations, share definitions, data collection methods |
| `brand_equity_measurement_guide.pdf` | 4 | Brand equity vs. activation metrics, measurement framework, KPI hierarchy |
| `cpg_competitive_response_playbook.pdf` | 5 | Insurgent brand threat assessment, response strategies, case study |
| `promotional_roi_framework.pdf` | 4 | Trade promotion evaluation, lift calculation, efficiency metrics |
| `category_management_handbook.pdf` | 5 | Category review frameworks, shelf optimization, planogram principles |

**CPG Market Intelligence KA** → `/Volumes/{CATALOG}/brand_performance/raw_data/market_docs/`

| Filename | Min Pages | Content summary |
|---|---|---|
| `cpg_market_trends_2024_2025.pdf` | 5 | Category trends, macro environment, channel shifts |
| `private_label_threat_assessment.pdf` | 4 | Private label share dynamics, competitive response strategies |
| `omnichannel_distribution_dynamics.pdf` | 4 | Online vs. offline distribution shifts, e-commerce velocity metrics |
| `retailer_power_dynamics_walmart_target.pdf` | 4 | Retailer negotiation context, shelf space dynamics, strategic priorities |

### Content quality constraints
- Each PDF must contain substantive CPG-domain content (not lorem ipsum or placeholder text)
- Documents will be used as RAG sources for Knowledge Assistants — terminology must match the data schema (e.g. use "ACV", "value share", "velocity per million ACV" as defined in SDD Section 4.2)
- Use `reportlab` or equivalent Python PDF library to generate structured documents with headings, body text, and at least one table or formula per document

### Acceptance criteria
- [ ] UC Volume paths are created if they do not exist: `{CATALOG}.brand_performance.raw_data`
- [ ] All 10 PDF files are uploaded to their correct volume paths
- [ ] Each PDF is at least the minimum page count listed above
- [ ] `dbutils.fs.ls()` confirms each file exists before notebook exits
- [ ] File sizes are > 5KB each (confirms substantive content, not empty files)
- [ ] Notebook prints a confirmation table of all 10 files with their paths and sizes
- [ ] Notebook exits with no uncaught exceptions

### Dependencies
- None (can run in parallel with SPEC-01)

---

## SPEC-03 — Unity Catalog Functions

**File:** `brand-performance-manager/notebooks/03_create_uc_functions.py`  
**PRD ref:** Section 9 (Unity Catalog Functions)  
**SDD ref:** Section 5 (Unity Catalog Function Design)

### Inputs
- `CATALOG` — string constant at top of notebook
- UC schema `{CATALOG}.brand_performance` must exist (from SPEC-01)
- SQL warehouse ID available via environment or `dbutils.secrets`

### Outputs
Three UC Functions in schema `brand_perf.utils` (or `{CATALOG}.brand_perf_utils`):

| Function | Language | Return Type |
|---|---|---|
| `enrich_user_request(query STRING)` | SQL | `STRUCT<brand, category, time_window_weeks, retailer, question_type, is_complete, missing_params>` |
| `validate_routing_decision(query_id, session_id, original_question, question_type, proposed_route, route_explanation)` | PYTHON | `STRING` |
| `format_visualization_spec(data_json, chart_hint, title)` | SQL | `STRING` |

### Implementation contracts

**`enrich_user_request`:**
- Use `ai_extract` for entity extraction (brand, category, time_window, retailer) — NOT `ai_query`
- Use `ai_classify` for intent classification with exactly 4 labels: `['topline', 'insurgent_brands', 'distribution_velocity', 'out_of_scope']`
- Default `time_window_weeks` to `12` when not extractable
- Default `retailer` to `'Total US'` when not specified
- Set `is_complete = TRUE` only when both `brand` and `category` are non-null AND `question_type != 'out_of_scope'`
- `missing_params` array uses `ARRAY_COMPACT` to exclude NULLs
- Full implementation follows SDD Section 5.1 exactly

**`validate_routing_decision`** _(OPTIONAL — audit log only; not on the critical path)_:
- The corrected HITL gate is app-owned (`session_state`), so this function is **not required**.
  Create it only if a persistent routing audit log is wanted; prefer writing the audit row
  from the app via `psycopg2` (`PGHOST`/`PGDATABASE`) over a UC Function writing to Lakebase.
- If created: `LANGUAGE PYTHON` UDF calling the Statement Execution API; inserts into the audit
  table; returns the id on success, `"ERROR: {message}"` on failure. See SDD §5.2.

**`format_visualization_spec`** _(OPTIONAL — off the default path)_:
- The app renders charts deterministically (SPEC-05 / SDD §6), so this is **not required**.
  Keep only as an optional LLM fallback. If created: `ai_query` with
  `responseFormat => '{"type": "json_object"}'`, `failOnError => false`, returns Plotly JSON
  starting with `{"data": [...]}`. See SDD §5.3.

### Acceptance criteria
- [ ] UC schema `brand_perf_utils` (or equivalent) is created with `CREATE SCHEMA IF NOT EXISTS`
- [ ] `enrich_user_request` created with `CREATE OR REPLACE FUNCTION` (required); optional functions created only if used
- [ ] `GRANT EXECUTE ON FUNCTION ... TO ...` is run for the app service principal
- [ ] `enrich_user_request` is smoke-tested inline: `SELECT brand_perf_utils.enrich_user_request('Why did Enfamil share drop last 4 weeks?')` — must return `is_complete=true`, `brand='Enfamil'`, `question_type='topline'`
- [ ] `enrich_user_request` incomplete test: `SELECT brand_perf_utils.enrich_user_request('What is our share trend?')` — must return `is_complete=false`, `missing_params` containing `'brand'`
- [ ] (optional) `format_visualization_spec` smoke-tested with a small JSON array — returns a string starting with `{"data":`
- [ ] (optional) `validate_routing_decision` smoke-tested — returns the id (not an ERROR string)
- [ ] Notebook prints PASS/FAIL for each smoke test before exiting

### Dependencies
- SPEC-01 must be complete (schema must exist for function grants)
- `BPM_WAREHOUSE_ID` environment variable must be set
- _(Optional)_ Lakebase project + audit table only if `validate_routing_decision` is used

---

## SPEC-04 — AgentBricks Creation (Genie + KA + MAS)

**File:** `brand-performance-manager/notebooks/04_create_agentbricks.py`  
**PRD ref:** Section 6 (Agent Inventory)  
**SDD ref:** Section 3 (Agent Design), Section 2 (Component Architecture)

### Inputs
- `CATALOG` — string constant
- All 5 Delta tables from SPEC-01 must exist
- All 10 PDFs in UC Volumes from SPEC-02 must exist
- All 3 UC Functions from SPEC-03 must exist
- AI Dev Kit MCP server must be running (`manage_mas`, `manage_genie`, `manage_ka` tools available)

### Outputs (in creation order)

**Step 1 — Genie Spaces (5x):**

| Variable Name | Genie Space Name | Primary Table |
|---|---|---|
| `CONTEXT_DB_GENIE_SPACE_ID` | "BPM Context DB" | `category_benchmarks` |
| `BRAND_ANALYSIS_GENIE_SPACE_ID` | "BPM Brand Analysis" | `brand_topline_metrics` |
| `TOPLINE_PERF_GENIE_SPACE_ID` | "BPM Topline Performance" | `market_share_decomposition` |
| `INSURGENT_GENIE_SPACE_ID` | "BPM Insurgent Brands" | `insurgent_brand_tracker` |
| `DIST_VEL_GENIE_SPACE_ID` | "BPM Distribution & Velocity" | `distribution_velocity` |

Each Genie Space must reference its table as `{CATALOG}.brand_performance.{table_name}`.

**Step 2 — Knowledge Assistants (2x):**

| Variable Name | KA Name | Volume Path |
|---|---|---|
| `BRAND_ANALYTICS_KA_TILE_ID` | "Brand Analytics Framework" | `/Volumes/{CATALOG}/brand_performance/raw_data/analytics_docs/` |
| `CPG_MARKET_INTEL_KA_TILE_ID` | "CPG Market Intelligence" | `/Volumes/{CATALOG}/brand_performance/raw_data/market_docs/` |

**Step 3 — Supervisor Agents (2x, in dependency order):**

| MAS | Endpoint Variable | Depends on |
|---|---|---|
| MAS #3 Topline Agent (sub) | `MAS3_ENDPOINT` | `BRAND_ANALYSIS_GENIE_SPACE_ID`, `TOPLINE_PERF_GENIE_SPACE_ID`, `BRAND_ANALYTICS_KA_TILE_ID` |
| Brand Perf Manager (top) | `MAS4_ENDPOINT` | `MAS3_ENDPOINT`, `INSURGENT_GENIE_SPACE_ID`, `DIST_VEL_GENIE_SPACE_ID` |

> MAS #1 (Intake) and MAS #2 (Router) are **not created**. Intake/classification is the
> `enrich_user_request` UC Function called directly by the app (Phase 1), and the HITL routing
> gate is app-owned (`session_state`). The top supervisor only dispatches a pre-confirmed
> `ROUTE=` to one specialist. See PRD §5–§6 and SDD §3.

### Agent configuration contracts
Each supervisor must be created with the exact `manage_mas()` configuration from SDD Sections 3.1 / 3.4:
- All `description` strings verbatim
- All `instructions` blocks verbatim (dispatch rules, output format)
- All `examples` entries verbatim
- Placeholder IDs (e.g. `{INSURGENT_GENIE_SPACE_ID}`) must be replaced with actual IDs from Step 1/2

### Acceptance criteria
- [ ] All 5 Genie Space IDs are printed to notebook output after creation
- [ ] All 2 KA tile IDs are printed to notebook output after creation
- [ ] Both supervisor endpoint names are printed to notebook output after creation
- [ ] The Brand Performance Manager endpoint name is explicitly labeled `BPM_AGENT_ENDPOINT: <value>` — this value goes into `app.yaml`
- [ ] A summary block at notebook end prints all IDs/endpoint names in copy-paste format for `app.yaml`
- [ ] Each `manage_mas` call uses the `create_or_update` action so re-runs are idempotent
- [ ] The top supervisor instructions say to trust `ROUTE=` and NOT re-classify/re-confirm; MAS #3 includes the `VISUALIZATION:` output format (SDD §3.4)

### Dependencies
- SPEC-01, SPEC-02, SPEC-03 must all be complete
- MCP server must be active in the session

---

## SPEC-05 — Streamlit Application

**File:** `brand-performance-manager/app/app.py`  
**PRD ref:** Section 10 (Application)  
**SDD ref:** Section 8 (Streamlit Application Design), Section 9 (Auth), Section 6 (Visualization Adapter), Section 7 (HITL), Section 12 (Error Handling), Section 13 (Performance & Caching)

### Inputs (at runtime)
Environment variables injected by Databricks Apps:
- `BPM_AGENT_ENDPOINT` — Brand Performance Manager (supervisor) endpoint name (from SPEC-04 output)
- `BPM_WAREHOUSE_ID` — SQL warehouse ID (KPI tiles + Phase 1 `enrich_user_request`)
- `BPM_CATALOG` — catalog name (default: `"main"`)
- `DATABRICKS_HOST` — auto-injected
- `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` — auto-injected for M2M OAuth
- `PGHOST` / `PGDATABASE` — auto-injected for Lakebase (optional audit log only)

### Module structure
Implement in this exact order within `app.py` (per SDD Section 8.1):
1. Constants & Config block (incl. `ROUTE_LABEL` / `ROUTE_WHY`)
2. Auth helpers: `_db_host()`, `_m2m_token()`, `_auth_token()`
3. SQL helpers: `query_sql()` via Statement Execution API
4. Phase 1 — intake: `enrich_request()` (calls `enrich_user_request` UC Function)
5. Phase 2 — execute: `_db_post()`, `call_domain_agent()`, `_extract_output_text()`
6. Visualization helpers: `extract_visualization()`, `render_visualization()` (deterministic Plotly from SQL)
7. HITL helpers: `render_hitl_panel()` (session_state gate), `_record_hitl_outcome()` (optional audit no-op)
8. KPI dashboard helpers: `load_brand_summary_kpis()`, `load_share_trend()`, `load_top_insurgent_brands()`, `load_distribution_overview()`
9. UI components: `render_header()`, `render_kpi_cards()`, `render_context_pills()`, `render_chat_tab()`, `_assistant()`, `render_dashboard_tab()`, `render_insurgent_tab()`, `render_distribution_tab()`
10. `main()` entry point

### Session state
Initialize `st.session_state` with all keys from SDD Section 8.2 `SESSION_STATE_DEFAULTS` dict at app startup.

### UI layout — 4 tabs
Implement the exact tab structure from SDD Section 8.3:

| Tab | Content |
|---|---|
| `📊 Dashboard` | KPI cards (Value Share, Share Change, Topline Sales, Insurgent %) + 3 Plotly charts (share trend line, share decomposition waterfall, top insurgent brands bar) |
| `💬 AI Advisor` | Suggested question buttons + `st.chat_message` history + `st.chat_input` + Plotly chart below each agent response |
| `🏃 Insurgent Brands` | Top insurgent brands table + share gain chart |
| `📦 Distribution` | ACV coverage table + velocity bar chart |

Context pills (Brand / Retailer / Time Window) rendered above all tabs, populated from `st.session_state.enriched_context`.

HITL confirmation panel in `st.sidebar` — only visible when `st.session_state.awaiting_confirmation == True`.

### Auth contract
Follow the exact token priority chain from SDD Section 9.1:
1. `st.context.headers.get("x-forwarded-access-token")` — user JWT (primary)
2. `os.environ.get("MJN_API_TOKEN")` — PAT (dev/testing fallback)
3. M2M OAuth via OIDC, cached with `@st.cache_resource(ttl=3300)`

No hardcoded tokens or passwords anywhere in the file.

### HITL contract (app-owned, no DB/polling)
Implement `render_hitl_panel()` per SDD Section 7:
- State lives in `st.session_state`; no Lakebase, no polling, no LLM-generated id
- Timeout: `HITL_TIMEOUT_SECS = 300` (gate auto-closes)
- A `selectbox` lets the user **Change route** before running
- On "Confirm & Run": call `call_domain_agent(question, ctx, route, session_id)` (Phase 2),
  append the answer, `st.rerun()`
- On "Cancel": clear the gate, post a cancellation message, `st.rerun()`
- `_record_hitl_outcome()` is an optional best-effort audit no-op

### Visualization contract (deterministic)
Implement `extract_visualization()` and `render_visualization()` per SDD Section 6:
- Parse `VISUALIZATION: chart_type|x_axis|y_axis|title` from the agent response (title only is required)
- Build the figure **in Python from a SQL query** keyed on route + context (no LLM, no endpoint)
- Render with `st.plotly_chart(fig, use_container_width=True)`
- On loader/render failure: degrade to `st.caption("(chart unavailable: …)")` — surfaced, not silent

### Phase 1 / Phase 2 call contracts
- `enrich_request(question)` (Phase 1): `SELECT enrich_user_request(...)` via `query_sql`; returns the
  struct dict or None. Drives the gate decision (out_of_scope / incomplete / proceed).
- `call_domain_agent(question, ctx, route, session_id)` (Phase 2): one POST to `BPM_AGENT_EP`
  with a `ROUTE=<route>` + context directive; timeout `TIMEOUT_AGENT_CALL_SECS = 180`;
  returns `(response_text, viz_hint_or_none)`.

### Error handling contract
Handle all error types from SDD Section 12.1:
- `TimeoutError` → "Agent is warming up..." message with retry suggestion
- `error_code` in response → "Agent error: ..." message
- Empty response → "The agent returned an empty response..." message
- Phase 1 warehouse unreachable (`enrich_request` → None) → ask the user to retry
- Visualization build failure → `st.caption("(chart unavailable: …)")`
- HITL timeout → warning message, gate closes

Implement the circuit breaker from SDD Section 12.3 for repeated endpoint failures.

### Caching contract
Apply caching per SDD Section 13.1:
- `@st.cache_resource(ttl=3300)` — M2M OAuth token
- `@st.cache_data(ttl=300)` — KPI dashboard data
- `@st.cache_data(ttl=3600)` — brand/entity metadata

### Acceptance criteria
- [ ] App starts without import errors or missing constant errors
- [ ] All 4 tabs render without exceptions when no agent call has been made
- [ ] KPI cards load data from `brand_topline_metrics` table via `query_sql()`
- [ ] A complete question in the AI Advisor tab opens the HITL gate; **Confirm & Run** calls `call_domain_agent()` and displays the response
- [ ] HITL panel appears in sidebar when `awaiting_confirmation = True` in session state
- [ ] "Confirm & Run" issues exactly one Phase 2 supervisor call carrying `ROUTE=` and clears the gate
- [ ] Sending "What is the weather today?" returns the out-of-scope message (no gate)
- [ ] No hardcoded tokens, passwords, catalog names, or endpoint names (all from env vars / constants)
- [ ] No `st.experimental_*` APIs used — all Streamlit APIs must be current stable

### Dependencies
- SPEC-04 must be complete (BPM_AGENT_ENDPOINT must be known to populate app.yaml)

---

## SPEC-06 — Deployment Configuration

**Files:**
- `brand-performance-manager/app/app.yaml`
- `brand-performance-manager/databricks.yml`
- `brand-performance-manager/app/requirements.txt`

**PRD ref:** Section 11 (Setup & Deployment)  
**SDD ref:** Section 14 (Deployment Design)

### `app/app.yaml`
Implement exactly as in SDD Section 14.2:
```yaml
command: ["streamlit", "run", "app.py"]
env:
  - name: BPM_AGENT_ENDPOINT
    value: "<value from SPEC-04 output>"
  - name: BPM_WAREHOUSE_ID
    value: "<YOUR_WAREHOUSE_ID>"
  - name: BPM_CATALOG
    value: "main"
```
(No `BPM_VIZ_ENDPOINT` — charts are rendered deterministically in the app.)
Comment block listing auto-injected vars: `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, `DATABRICKS_HOST`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGSSLMODE`.

### `databricks.yml`
Implement exactly as in SDD Section 14.1. Bundle name: `brand-performance-manager`. Two targets: `dev` (default, catalog=`main`) and `prod` (catalog=`prod_catalog`). Lakebase resource binding with `<LAKEBASE_BRANCH>` and `<LAKEBASE_DATABASE>` as placeholders.

### `app/requirements.txt`
Exactly three pinned dependencies per SDD Section 14.3:
```
pandas>=2.0.0
plotly>=5.20.0
psycopg2-binary>=2.9.0
```

### Acceptance criteria
- [ ] `app.yaml` has the 3 `BPM_*` env vars (`BPM_AGENT_ENDPOINT`, `BPM_WAREHOUSE_ID`, `BPM_CATALOG`) with placeholder values clearly labeled
- [ ] `databricks.yml` validates with `databricks bundle validate` (no schema errors)
- [ ] `requirements.txt` contains exactly the 3 packages above, no others
- [ ] No actual secret values, tokens, or passwords in any config file

### Dependencies
- SPEC-04 (to know the BPM_AGENT_ENDPOINT value to document)

---

## SPEC-07 — Test Suite

**Files:**
- `brand-performance-manager/tests/test_uc_functions.py`
- `brand-performance-manager/tests/test_hitl_flow.py`
- `brand-performance-manager/tests/test_routing.py`
- `brand-performance-manager/tests/test_visualization.py`

**PRD ref:** Section 13 (Success Metrics)  
**SDD ref:** Section 15 (Testing Strategy)

### `test_uc_functions.py`
Implement the following tests from SDD Section 15.1:

| Test | Input | Expected output |
|---|---|---|
| `test_enrich_complete` | `"Why did Enfamil share drop last 4 weeks at Walmart?"` | `brand="Enfamil"`, `time_window_weeks=4`, `retailer="Walmart"`, `is_complete=True`, `question_type="topline"` |
| `test_enrich_incomplete` | `"What is our share trend?"` | `is_complete=False`, `"brand"` in `missing_params` |
| `test_enrich_insurgent` | `"Which insurgent brands are gaining share in baby food?"` | `question_type="insurgent_brands"`, `category="Baby Food"` |
| `test_enrich_distribution` | `"Which SKUs have below-80% ACV in the Northeast?"` | `question_type="distribution_velocity"`, `region="Northeast"` |
| `test_enrich_out_of_scope` | `"What is the weather forecast for Chicago?"` | `question_type="out_of_scope"`, `is_complete=False` |
| `test_enrich_default_time_window` | `"Show me Enfamil share in Infant Formula"` | `time_window_weeks=12` (default applied) |
| `test_enrich_default_retailer` | `"Show me Enfamil share in Infant Formula last 8 weeks"` | `retailer="Total US"` (default applied) |

### `test_hitl_flow.py`
Unit-test the two-phase, app-owned flow (SDD §7, §15.3) — no Lakebase, no polling:
1. **Phase 2 contract:** `call_domain_agent` makes exactly one supervisor call whose message
   contains `ROUTE=<route>` + the enriched context + the question (mock `_db_post`).
2. Circuit breaker: when open, `call_domain_agent` does NOT call `_db_post`.
3. **Phase 1 gating:** `enrich_request` parses the UC-function struct (complete / incomplete /
   warehouse-unreachable → None), which is what the gate uses to clarify / scope / proceed.

### `test_routing.py`
Validate **Phase 2 dispatch** against the supervisor endpoint (live, `@pytest.mark.integration`).
Each call sends a confirmed `ROUTE=` + context exactly as the app does on Confirm:

| ROUTE + question | Expected |
|---|---|
| `topline` — "Why did NovaBaby share drop last 4 weeks at Walmart?" | share / decomposition content |
| `insurgent_brands` — "Which insurgent brands are gaining share?" | insurgent / challenger content |
| `distribution_velocity` — "Which SKUs have below-80% ACV?" | ACV / velocity content |
| `topline` — "value share trend" | must NOT re-request HITL confirmation |

(Intake clarification / out-of-scope are Phase 1 — covered by `test_uc_functions.py`.)

### `test_visualization.py`
Unit-test the deterministic renderer (SDD §6, §15.4) — no LLM, no serving endpoint:
- `extract_visualization()` parses `VISUALIZATION: type|x|y|title` → tuple
- `render_visualization()` builds a Plotly figure from a mocked SQL loader (asserts a figure is rendered)
- No context → nothing rendered; loader error → degrades to a caption, never raises

### Test infrastructure requirements
- `conftest.py` fakes `streamlit` so `app.py` imports for unit tests; app-side tests skip if deps absent
- Integration tests read `BPM_WAREHOUSE_ID`, `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `BPM_AGENT_ENDPOINT` from env — no hardcoded values; skip without creds
- Optional UC-Function tests (`validate_routing_decision`, `format_visualization_spec`) are gated behind `BPM_TEST_OPTIONAL=1`

### Acceptance criteria (mapped to PRD Section 13 Success Metrics)

| PRD Metric | Target | Test that validates it |
|---|---|---|
| Routing accuracy | > 90% | `test_routing.py` — Phase 2 dispatch scenarios pass |
| Visualization render success | > 95% | `test_visualization.py` — deterministic figure built from SQL |
| HITL executes on confirm | core regression | `test_hitl_flow.py` — Confirm path issues one ROUTE-carrying call |
| Classifier correctness | Foundation for routing accuracy | `test_uc_functions.py` — `enrich_user_request` cases pass |

### Dependencies
- All of SPEC-01 through SPEC-06 must be complete

---

## Validation Checklist — Full System

Use this after all specs are implemented to confirm end-to-end system health:

### Data layer
- [ ] All 5 tables queryable via Databricks SQL Editor
- [ ] `SELECT COUNT(*) FROM {CATALOG}.brand_performance.brand_topline_metrics` returns > 10,000
- [ ] Share values sum to ~100% for a given week/retailer/region

### UC Functions
- [ ] `SELECT brand_perf_utils.enrich_user_request('Enfamil share last 4 weeks')` returns a complete struct
- [ ] _(optional)_ `format_visualization_spec` / `validate_routing_decision` only if created

### Agent layer
- [ ] All 5 Genie Space IDs are valid and respond to a test NL query
- [ ] Both KA tile IDs are valid and return a response to "What is ACV?"
- [ ] Brand Performance Manager endpoint responds to a `ROUTE=topline` directive within 90 seconds

### HITL (app-owned)
- [ ] Phase 1 `enrich_request` returns the proposed route for a complete question
- [ ] The gate appears in the sidebar and **Confirm & Run** triggers exactly one Phase 2 call
- [ ] _(optional)_ routing audit row is written via psycopg2 if the audit log is enabled

### App
- [ ] `databricks apps deploy` completes without errors
- [ ] App URL loads Streamlit UI in browser
- [ ] KPI cards show data (not empty / error state)
- [ ] AI Advisor: a complete question opens the HITL gate; Confirm reaches the supervisor and returns a response
- [ ] Incomplete question asks for missing params; out-of-scope returns a scope message — neither opens the gate
- [ ] A Plotly chart renders below the agent response

---

*Document owner: AI Dev Kit · Databricks CPG Industry Team*  
*Derived from: PRD.md v1.0 + SDD.md v1.0*
