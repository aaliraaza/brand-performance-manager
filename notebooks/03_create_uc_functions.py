# Databricks notebook source
# MAGIC %md
# MAGIC # Brand Performance Manager — Step 3: Create Unity Catalog Functions
# MAGIC
# MAGIC Creates three UC Functions in `{CATALOG}.brand_perf_utils`:
# MAGIC
# MAGIC | Function | Language | Purpose |
# MAGIC |----------|----------|---------|
# MAGIC | `enrich_user_request(query)` | SQL | Extract brand/category/time entities + classify intent |
# MAGIC | `validate_routing_decision(...)` | Python | Write HITL confirmation to Lakebase |
# MAGIC | `format_visualization_spec(...)` | SQL | Generate Plotly JSON spec via LLM |
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - SPEC-01 must be complete (`{CATALOG}.brand_performance` schema must exist)
# MAGIC - Lakebase project must be created with `hitl.pending_confirmations` table
# MAGIC - `BPM_WAREHOUSE_ID` environment variable must be set

# COMMAND ----------

# MAGIC %md ## Configuration

# COMMAND ----------

import os

CATALOG      = "ar_dpcatalog"   # Update to your catalog
SCHEMA       = "brand_perf_utils"
WAREHOUSE_ID = os.environ.get("BPM_WAREHOUSE_ID", "")  # Set in cluster env vars or Databricks Apps

assert WAREHOUSE_ID, "Set BPM_WAREHOUSE_ID in the cluster environment variables before running."
print(f"Using catalog  : {CATALOG}")
print(f"Using schema   : {SCHEMA}")
print(f"Warehouse ID   : {WAREHOUSE_ID}")

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"Schema ready   : {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md ## Function 1 — `enrich_user_request`
# MAGIC
# MAGIC Uses `ai_extract` for entity extraction and `ai_classify` for intent routing.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.enrich_user_request(query STRING)
RETURNS STRUCT<
    brand                STRING    COMMENT 'Primary brand name extracted from the question, or NULL',
    category             STRING    COMMENT 'Product category (e.g. Infant Formula, Baby Food, Toddler Snacks) or NULL',
    time_window_weeks    INT       COMMENT 'Requested time window in weeks (default 12)',
    retailer             STRING    COMMENT 'Retailer name (default Total US)',
    region               STRING    COMMENT 'Region name (default Total US)',
    question_type        STRING    COMMENT 'topline | insurgent_brands | distribution_velocity | out_of_scope',
    is_complete          BOOLEAN   COMMENT 'True when brand and category are present and question_type != out_of_scope',
    missing_params       ARRAY<STRING> COMMENT 'List of required parameters not found in the query'
>
COMMENT 'Enriches a natural-language brand performance question with structured entities and intent classification.
         Uses ai_extract for entity extraction and ai_classify for routing intent.
         Returns a struct with all extracted fields and completeness flags.'
LANGUAGE SQL
AS $$
    WITH extracted AS (
        SELECT ai_extract(
            query,
            named_struct(
                'brand',             'the brand name being asked about (e.g. NovaBaby, PuraMilk)',
                'category',          'the product category (Infant Formula, Baby Food, or Toddler Snacks)',
                'time_window',       'the time window as a number and unit (e.g. 4 weeks, 3 months, last quarter)',
                'retailer',          'the specific retailer name (e.g. Walmart, Target, Kroger)',
                'region',            'the geographic region (Total US, Northeast, Southeast, Midwest, West)'
            )
        ) AS entities
    ),
    parsed AS (
        SELECT
            entities.brand                                          AS brand,
            entities.category                                       AS category,
            CASE
                WHEN entities.time_window RLIKE '(?i)\\b(1|one)\\s*(week|wk)'  THEN 1
                WHEN entities.time_window RLIKE '(?i)\\b(2|two)\\s*(week|wk)'  THEN 2
                WHEN entities.time_window RLIKE '(?i)\\b(4|four)\\s*(week|wk)' THEN 4
                WHEN entities.time_window RLIKE '(?i)\\b(8|eight)\\s*(week|wk)'THEN 8
                WHEN entities.time_window RLIKE '(?i)\\b(13|thirteen)\\s*(week|wk)' THEN 13
                WHEN entities.time_window RLIKE '(?i)\\b(26|twenty)\\s*(week|wk)'   THEN 26
                WHEN entities.time_window RLIKE '(?i)\\b(52|fifty)\\s*(week|wk)'    THEN 52
                WHEN entities.time_window RLIKE '(?i)(quarter|qtr)'                 THEN 13
                WHEN entities.time_window RLIKE '(?i)(half.year|6.month)'           THEN 26
                WHEN entities.time_window RLIKE '(?i)(year|annual|ytd|mat)'         THEN 52
                WHEN entities.time_window RLIKE '(?i)\\b(12|twelve)\\s*(week|wk)'   THEN 12
                ELSE 12
            END                                                     AS time_window_weeks,
            COALESCE(NULLIF(TRIM(entities.retailer), ''), 'Total US') AS retailer,
            COALESCE(NULLIF(TRIM(entities.region), ''), 'Total US')   AS region
        FROM extracted
    ),
    classified AS (
        SELECT
            brand,
            category,
            time_window_weeks,
            retailer,
            region,
            ai_classify(
                query,
                ARRAY(
                    'topline',
                    'insurgent_brands',
                    'distribution_velocity',
                    'out_of_scope'
                ),
                'Classify the user question about CPG brand performance into one of these categories:
                 - topline: questions about brand sales, value share, volume share, share change, revenue, market position, or overall brand performance
                 - insurgent_brands: questions about challenger brands, new entrants, growing competitors, organic/natural alternatives gaining share
                 - distribution_velocity: questions about ACV, shelf coverage, out-of-stock, velocity per ACV, facings, shelf position, distribution gaps
                 - out_of_scope: questions not related to CPG brand performance data (weather, news, general knowledge, etc.)'
            )                                                         AS question_type
        FROM parsed
    )
    SELECT
        brand,
        category,
        time_window_weeks,
        retailer,
        region,
        question_type,
        (brand IS NOT NULL AND category IS NOT NULL AND question_type != 'out_of_scope') AS is_complete,
        ARRAY_COMPACT(ARRAY(
            CASE WHEN brand IS NULL    THEN 'brand'    END,
            CASE WHEN category IS NULL THEN 'category' END
        ))                                                            AS missing_params
    FROM classified
$$
""")
print("✅ Created: enrich_user_request")

# COMMAND ----------

# MAGIC %md ## Function 2 — `validate_routing_decision`
# MAGIC
# MAGIC Python UDF that writes a HITL confirmation record to Lakebase via the Statement Execution API.
# MAGIC Note: Cross-database writes to Lakebase (PostgreSQL) must use the REST API from a Python UDF,
# MAGIC not direct JDBC within a SQL function body.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.validate_routing_decision(
    query_id         STRING  COMMENT 'Unique identifier for this routing decision',
    session_id       STRING  COMMENT 'User session ID from Streamlit st.session_state',
    original_question STRING COMMENT 'The raw user question text',
    question_type    STRING  COMMENT 'Classified intent: topline | insurgent_brands | distribution_velocity',
    proposed_route   STRING  COMMENT 'Agent or data source to route to',
    route_explanation STRING COMMENT 'Human-readable explanation of why this route was chosen'
)
RETURNS STRING
COMMENT 'Writes a HITL pending confirmation record to Lakebase and returns the query_id on success.
         On failure, returns an error string starting with ERROR:.
         Reads DATABRICKS_HOST, DATABRICKS_TOKEN, BPM_WAREHOUSE_ID from os.environ.
         Inserts into brand_perf_lakebase.hitl.pending_confirmations.'
LANGUAGE PYTHON
AS $$
import os
import json
import uuid
import urllib.request

host         = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
token        = os.environ.get("DATABRICKS_TOKEN", os.environ.get("MJN_API_TOKEN", ""))
warehouse_id = os.environ.get("BPM_WAREHOUSE_ID", "")

if not host or not token or not warehouse_id:
    return "ERROR: Missing DATABRICKS_HOST, DATABRICKS_TOKEN, or BPM_WAREHOUSE_ID"

confirmation_id = str(uuid.uuid4())

insert_sql = f"""
INSERT INTO brand_perf_lakebase.hitl.pending_confirmations
    (confirmation_id, query_id, session_id, query_text, question_type,
     proposed_route, route_explanation, status, created_at)
VALUES
    ('{confirmation_id}', '{query_id}', '{session_id}',
     '{original_question.replace("'", "''")}',
     '{question_type}', '{proposed_route}',
     '{route_explanation.replace("'", "''")}',
     'PENDING', CURRENT_TIMESTAMP)
"""

payload = json.dumps({
    "statement":    insert_sql,
    "warehouse_id": warehouse_id,
    "wait_timeout": "30s",
    "on_wait_timeout": "CANCEL",
}).encode("utf-8")

req = urllib.request.Request(
    url     = f"{host}/api/2.0/sql/statements",
    data    = payload,
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    },
    method  = "POST",
)

try:
    with urllib.request.urlopen(req, timeout=35) as resp:
        result = json.loads(resp.read().decode())
    state = result.get("status", {}).get("state", "UNKNOWN")
    if state in ("SUCCEEDED", "RUNNING"):
        return query_id
    err_msg = result.get("status", {}).get("error", {}).get("message", "Unknown error")
    return f"ERROR: Statement state={state} — {err_msg}"
except Exception as e:
    return f"ERROR: {str(e)}"
$$
""")
print("✅ Created: validate_routing_decision")

# COMMAND ----------

# MAGIC %md ## Function 3 — `format_visualization_spec`
# MAGIC
# MAGIC Calls an LLM via `ai_query` to convert data + a chart hint into valid Plotly JSON.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.format_visualization_spec(
    data_json  STRING  COMMENT 'JSON string of data rows, e.g. [{"brand":"NovaBaby","share":35.2}, ...]',
    chart_hint STRING  COMMENT 'Chart type hint: bar | line | waterfall | pie | scatter',
    title      STRING  COMMENT 'Chart title'
)
RETURNS STRING
COMMENT 'Generates a Plotly-compatible JSON specification string from structured data and a chart type hint.
         Uses ai_query with databricks-claude-sonnet-4 for structured JSON output.
         Returns raw Plotly JSON string starting with {"data": [...]}.
         On failure, returns an empty JSON object {}.'
LANGUAGE SQL
AS $$
    SELECT COALESCE(
        ai_query(
            'databricks-claude-sonnet-4',
            CONCAT(
                'You are a data visualization expert. Convert the following data into a valid Plotly JSON specification.\n\n',
                'Chart type: ', chart_hint, '\n',
                'Chart title: ', title, '\n',
                'Data (JSON array): ', data_json, '\n\n',
                'Requirements:\n',
                '- Return ONLY valid Plotly JSON starting with {"data": [...], "layout": {...}}\n',
                '- Background color: #FFFFFF (white)\n',
                '- Primary series color: #003087 (navy)\n',
                '- Secondary series color: #E87722 (orange)\n',
                '- Chart height: 400\n',
                '- Font family: Arial, sans-serif\n',
                '- Include axis labels based on the data field names\n',
                '- For waterfall charts use type "waterfall" with increasing/decreasing/total measure arrays\n',
                '- For line charts add markers (mode: "lines+markers")\n',
                '- Do not include any explanation or markdown — return ONLY the JSON object'
            ),
            responseFormat => ''{"type": "json_object"}'',
            failOnError => false
        ).response,
        '{}'
    )
$$
""")
print("✅ Created: format_visualization_spec")

# COMMAND ----------

# MAGIC %md ## Grants — App Service Principal

# COMMAND ----------

# Grant EXECUTE to the app's service principal (update the principal as needed)
# Uncomment and set APP_PRINCIPAL to your Databricks Apps service principal email or group name.

# APP_PRINCIPAL = "bpm-app-sp@company.com"
# for fn in ["enrich_user_request", "validate_routing_decision", "format_visualization_spec"]:
#     spark.sql(f"GRANT EXECUTE ON FUNCTION {CATALOG}.{SCHEMA}.{fn} TO `{APP_PRINCIPAL}`")
#     print(f"✅ Granted EXECUTE on {fn} to {APP_PRINCIPAL}")

print("NOTE: Uncomment the grants block above and set APP_PRINCIPAL before deploying to production.")

# COMMAND ----------

# MAGIC %md ## Smoke Tests

# COMMAND ----------

print("=" * 65)
print("  SMOKE TESTS — enrich_user_request")
print("=" * 65)
tests = [
    {
        "desc":         "Complete query (brand + category explicit)",
        "query":        "Why did NovaBaby share drop last 4 weeks at Walmart?",
        "expect_brand": "NovaBaby",
        "expect_qtype": "topline",
        "expect_complete": True,
        "expect_tw":    4,
    },
    {
        "desc":         "Incomplete query (missing brand)",
        "query":        "What is our share trend this quarter?",
        "expect_brand": None,
        "expect_qtype": "topline",
        "expect_complete": False,
        "expect_missing_brand": True,
    },
    {
        "desc":         "Insurgent intent",
        "query":        "Which insurgent brands are gaining share in Baby Food?",
        "expect_brand": None,
        "expect_qtype": "insurgent_brands",
        "expect_complete": False,
    },
    {
        "desc":         "Distribution intent",
        "query":        "Which SKUs have below 80% ACV in the Northeast?",
        "expect_brand": None,
        "expect_qtype": "distribution_velocity",
        "expect_complete": False,
    },
    {
        "desc":         "Out of scope",
        "query":        "What is the weather forecast for Chicago today?",
        "expect_brand": None,
        "expect_qtype": "out_of_scope",
        "expect_complete": False,
    },
    {
        "desc":         "Default time window",
        "query":        "Show me NovaBaby share in Infant Formula",
        "expect_brand": "NovaBaby",
        "expect_qtype": "topline",
        "expect_tw_default": 12,
    },
    {
        "desc":         "Default retailer",
        "query":        "Show me NovaBaby share in Infant Formula last 8 weeks",
        "expect_brand": "NovaBaby",
        "expect_retailer_default": "Total US",
        "expect_tw": 8,
    },
]

all_pass = True
for t in tests:
    row = spark.sql(f"""
        SELECT {CATALOG}.{SCHEMA}.enrich_user_request('{t["query"]}') AS result
    """).collect()[0]["result"]

    result_dict = {
        "brand":             row["brand"],
        "category":          row["category"],
        "time_window_weeks": row["time_window_weeks"],
        "retailer":          row["retailer"],
        "question_type":     row["question_type"],
        "is_complete":       row["is_complete"],
        "missing_params":    list(row["missing_params"] or []),
    }

    passed = True
    if "expect_brand"      in t and t["expect_brand"] and t["expect_brand"].lower() not in (result_dict["brand"] or "").lower():
        passed = False
    if "expect_qtype"      in t and result_dict["question_type"] != t["expect_qtype"]:
        passed = False
    if "expect_complete"   in t and result_dict["is_complete"] != t["expect_complete"]:
        passed = False
    if "expect_tw"         in t and result_dict["time_window_weeks"] != t["expect_tw"]:
        passed = False
    if "expect_tw_default" in t and result_dict["time_window_weeks"] != t["expect_tw_default"]:
        passed = False
    if "expect_missing_brand" in t and "brand" not in result_dict["missing_params"]:
        passed = False
    if "expect_retailer_default" in t and result_dict["retailer"] != "Total US":
        passed = False

    status = "PASS" if passed else "FAIL"
    if not passed:
        all_pass = False
    print(f"  [{status}] {t['desc']}")
    if not passed:
        print(f"         Query   : {t['query']}")
        print(f"         Result  : {result_dict}")

# COMMAND ----------

print("\n" + "=" * 65)
print("  SMOKE TESTS — format_visualization_spec")
print("=" * 65)

test_data = '[{"week":"W1","share":35.2},{"week":"W2","share":34.8},{"week":"W3","share":34.1}]'
result = spark.sql(f"""
    SELECT {CATALOG}.{SCHEMA}.format_visualization_spec(
        '{test_data}',
        'line',
        'NovaBaby Value Share Trend'
    ) AS viz_spec
""").collect()[0]["viz_spec"]

import json
try:
    parsed = json.loads(result)
    has_data = "data" in parsed
    print(f"  [{'PASS' if has_data else 'FAIL'}] format_visualization_spec returns valid JSON with 'data' key")
    if not has_data:
        all_pass = False
        print(f"  Result: {result[:200]}")
except json.JSONDecodeError:
    all_pass = False
    print(f"  [FAIL] Response is not valid JSON: {result[:200]}")

# COMMAND ----------

print("\n" + "=" * 65)
print("  SMOKE TESTS — validate_routing_decision")
print("=" * 65)
print("  NOTE: This test requires Lakebase to be configured.")
print("  If Lakebase is not yet set up, this test will return ERROR: — that is expected.")
print()

import uuid as _uuid
test_qid = f"smoke-test-{_uuid.uuid4()}"

vrd_result = spark.sql(f"""
    SELECT {CATALOG}.{SCHEMA}.validate_routing_decision(
        '{test_qid}',
        'test-session-001',
        'Test routing decision smoke test',
        'topline',
        'topline_agent',
        'Routing to topline agent because question is about value share'
    ) AS result
""").collect()[0]["result"]

is_error = str(vrd_result).startswith("ERROR:")
if is_error:
    print(f"  [WARN] validate_routing_decision returned error (Lakebase may not be configured):")
    print(f"         {vrd_result}")
    print(f"  This is expected if Lakebase is not yet provisioned.")
else:
    print(f"  [PASS] validate_routing_decision wrote PENDING record, returned query_id: {vrd_result}")

# COMMAND ----------

# MAGIC %md ## Summary

# COMMAND ----------

print("\n" + "=" * 65)
print("  UC FUNCTION CREATION COMPLETE")
print("=" * 65)
print(f"\n  Catalog: {CATALOG}")
print(f"  Schema : {SCHEMA}")
print("\n  Functions created:")
for fn in ["enrich_user_request", "validate_routing_decision", "format_visualization_spec"]:
    print(f"    ✅ {CATALOG}.{SCHEMA}.{fn}")

print(f"\n  Smoke test result: {'ALL PASSED ✅' if all_pass else 'SOME FAILED ⚠️  — review output above'}")

print("""
Next steps:
  Run notebooks/04_create_agentbricks.py to create Genie Spaces, Knowledge Assistants,
  and the 2 Supervisor Agents (MAS #3 Topline + the Brand Performance Manager).
  Note: enrich_user_request is the only required UC Function; validate_routing_decision
  and format_visualization_spec are optional (the app owns the HITL gate and renders
  charts deterministically).
  Requires: MCP AI Dev Kit server active in the Databricks session.
""")
