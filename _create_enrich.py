"""
Create ar_dpcatalog.brand_perf_utils.enrich_user_request as a standard SQL UDF
(RETURN + named_struct) that runs on a DBSQL warehouse. Ports notebook 03's logic
(ai_extract + ai_classify) but drops the `LANGUAGE SQL AS $$...$$` form (rejected by
both DBSQL and the serverless runtime) and simplifies the time-window regex to avoid
backslash-escaping pitfalls. Posts via the Statement Execution API (env PAT).
"""
from __future__ import annotations
import json, os, urllib.request, urllib.error

HOST = os.environ["DATABRICKS_HOST"].rstrip("/")
TOK  = os.environ["DATABRICKS_TOKEN"]
WH   = os.environ["BPM_WAREHOUSE_ID"]

DDL = """
CREATE OR REPLACE FUNCTION ar_dpcatalog.brand_perf_utils.enrich_user_request(query STRING)
RETURNS STRUCT<
  brand STRING, category STRING, time_window_weeks INT, retailer STRING,
  region STRING, question_type STRING, is_complete BOOLEAN, missing_params ARRAY<STRING>>
COMMENT 'Extract structured context + classify intent from a brand-performance question.'
RETURN (
  WITH extracted AS (
    SELECT ai_extract(
      query,
      ARRAY('brand', 'category', 'time_window', 'retailer', 'region')
    ) AS entities
  ),
  parsed AS (
    SELECT
      entities.brand AS brand,
      entities.category AS category,
      CASE
        WHEN entities.time_window RLIKE '(?i)(quarter|qtr)'                THEN 13
        WHEN entities.time_window RLIKE '(?i)(year|annual|ytd|mat|52)'     THEN 52
        WHEN entities.time_window RLIKE '(?i)(26|half|6 ?month)'           THEN 26
        WHEN entities.time_window RLIKE '(?i)(^|[^0-9])13'                 THEN 13
        WHEN entities.time_window RLIKE '(?i)(^|[^0-9])8'                  THEN 8
        WHEN entities.time_window RLIKE '(?i)(^|[^0-9])4'                  THEN 4
        WHEN entities.time_window RLIKE '(?i)(^|[^0-9])2'                  THEN 2
        WHEN entities.time_window RLIKE '(?i)(^|[^0-9])1([^0-9]|$)'        THEN 1
        ELSE 12
      END AS time_window_weeks,
      COALESCE(NULLIF(TRIM(entities.retailer), ''), 'Total US') AS retailer,
      COALESCE(NULLIF(TRIM(entities.region), ''),  'Total US') AS region
    FROM extracted
  ),
  classified AS (
    SELECT brand, category, time_window_weeks, retailer, region,
      ai_classify(
        query,
        ARRAY(
          'brand sales market share or share change',
          'emerging challenger competitor brands',
          'product distribution ACV shelf or velocity',
          'not about retail brand performance'
        )
      ) AS raw_label
    FROM parsed
  ),
  mapped AS (
    SELECT brand, category, time_window_weeks, retailer, region,
      CASE raw_label
        WHEN 'brand sales market share or share change' THEN 'topline'
        WHEN 'emerging challenger competitor brands'     THEN 'insurgent_brands'
        WHEN 'product distribution ACV shelf or velocity' THEN 'distribution_velocity'
        ELSE 'out_of_scope'
      END AS question_type
    FROM classified
  )
  SELECT named_struct(
    'brand', brand,
    'category', category,
    'time_window_weeks', time_window_weeks,
    'retailer', retailer,
    'region', region,
    'question_type', question_type,
    'is_complete', CASE question_type
        WHEN 'topline'               THEN (brand IS NOT NULL AND category IS NOT NULL)
        WHEN 'insurgent_brands'      THEN (category IS NOT NULL)
        WHEN 'distribution_velocity' THEN (category IS NOT NULL OR brand IS NOT NULL OR region <> 'Total US')
        ELSE false
      END,
    'missing_params', CASE question_type
        WHEN 'topline' THEN ARRAY_COMPACT(ARRAY(
            CASE WHEN brand IS NULL THEN 'brand' END,
            CASE WHEN category IS NULL THEN 'category' END))
        WHEN 'insurgent_brands' THEN ARRAY_COMPACT(ARRAY(
            CASE WHEN category IS NULL THEN 'category' END))
        WHEN 'distribution_velocity' THEN ARRAY_COMPACT(ARRAY(
            CASE WHEN (category IS NULL AND brand IS NULL AND region = 'Total US')
                 THEN 'category or region' END))
        ELSE ARRAY_COMPACT(ARRAY(CAST(NULL AS STRING)))
      END
  )
  FROM mapped
)
"""

def run_sql(stmt: str, wait="50s") -> dict:
    body = json.dumps({"statement": stmt, "warehouse_id": WH, "wait_timeout": wait}).encode()
    req = urllib.request.Request(f"{HOST}/api/2.0/sql/statements", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOK}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()}

print("Creating enrich_user_request (SQL UDF, RETURN form)...")
res = run_sql(DDL)
st = res.get("status", {})
print("  state:", st.get("state"), "| err:", (st.get("error") or {}).get("message", "")[:400] or res.get("_body","")[:400])
if st.get("state") != "SUCCEEDED":
    raise SystemExit(1)

for q in ["Why did NovaBaby share drop last 4 weeks at Walmart?",
          "What is our share trend?",
          "What is the weather in Chicago?"]:
    r = run_sql("SELECT ar_dpcatalog.brand_perf_utils.enrich_user_request('" + q.replace("'", "''") + "') AS r")
    s = r.get("status", {})
    out = (r.get("result", {}).get("data_array") or [["<none>"]])[0][0] if s.get("state") == "SUCCEEDED" else (s.get("error") or {}).get("message","")[:200]
    print(f"  [{s.get('state')}] {q!r} -> {out}")
print("Done.")
