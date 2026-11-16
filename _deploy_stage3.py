"""
Stage-3 deploy (REST-direct, no SDK/MCP): create Genie Spaces + the two Supervisor
Agents (MAS #3 Topline + Brand Performance Manager). KAs are deferred (they require the
databricks-sdk knowledge_assistants service + indexed PDFs). Reads DATABRICKS_HOST/TOKEN.
"""
from __future__ import annotations
import json, os, urllib.request, urllib.error

HOST = os.environ["DATABRICKS_HOST"].rstrip("/")
TOK  = os.environ["DATABRICKS_TOKEN"]
WH   = os.environ.get("BPM_WAREHOUSE_ID", "148ccb90800933a1")
CAT, SCH = "ar_dpcatalog", "brand_performance"

def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{HOST}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOK}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:800]}

def genie(display_name, table, description):
    r = call("POST", "/api/2.0/data-rooms/", {
        "display_name": display_name, "warehouse_id": WH,
        "table_identifiers": [f"{CAT}.{SCH}.{table}"],
        "run_as_type": "VIEWER", "description": description,
    })
    sid = r.get("space_id") or r.get("id") or (r.get("data_room") or {}).get("space_id")
    print(f"  genie '{display_name}': space_id={sid} {'' if sid else r}")
    return sid

def mas(name, agents, description, instructions):
    r = call("POST", "/api/2.0/multi-agent-supervisors", {
        "name": name, "agents": agents,
        "description": description, "instructions": instructions,
    })
    if r.get("_http_error"):
        print(f"  MAS '{name}' FAILED: {r}"); return None, None
    tile = r.get("id") or r.get("tile_id") or (r.get("multi_agent_supervisor") or {}).get("id")
    ep = r.get("endpoint_name") or (r.get("multi_agent_supervisor") or {}).get("endpoint_name")
    if tile and not ep:  # fetch endpoint_name
        g = call("GET", f"/api/2.0/multi-agent-supervisors/{tile}")
        ep = g.get("endpoint_name") or (g.get("multi_agent_supervisor") or {}).get("endpoint_name")
    print(f"  MAS '{name}': tile_id={tile} endpoint_name={ep}")
    return tile, ep

print("[1] Genie Spaces")
g_brand = genie("BPM Brand Analysis", "brand_topline_metrics",
                "Weekly brand sales and value/volume share trends.")
g_topl  = genie("BPM Topline Performance", "market_share_decomposition",
                "Share-change decomposition: distribution vs rate vs penetration drivers.")
g_ins   = genie("BPM Insurgent Brands", "insurgent_brand_tracker",
                "Emerging/challenger brands: share gain, ACV-weighted velocity, threat score.")
g_dist  = genie("BPM Distribution & Velocity", "distribution_velocity",
                "SKU-level ACV distribution, velocity, out-of-stock by retailer/region.")

assert all([g_brand, g_topl, g_ins, g_dist]), "Genie space creation failed; aborting"

print("[2] MAS #3 — Topline Agent (2 Genie sub-agents; KA deferred)")
topl_tile, topl_ep = mas(
    "Brand Performance Topline Agent",
    [
        {"name": "brand_analyst", "agent_type": "genie", "genie_space": {"id": g_brand},
         "description": "Brand share trends, value/volume share, YoY change over a time window."},
        {"name": "category_analyst", "agent_type": "genie", "genie_space": {"id": g_topl},
         "description": "Share-change decomposition (distribution, rate, penetration, frequency, basket)."},
    ],
    "Topline performance: share trends + 'what drove it' decomposition.",
    ("You analyze topline brand performance. For 'why did share change' questions, get the share "
     "delta from brand_analyst then the decomposition from category_analyst; name the primary driver. "
     "Always quantify (ppt, $, weeks). When chartable, end with: "
     "VISUALIZATION: <chart_type>|<x_field>|<y_field>|<title>"),
)
assert topl_ep, "MAS #3 endpoint_name not resolved; aborting"

print("[3] Brand Performance Manager — single execution supervisor")
bpm_tile, bpm_ep = mas(
    "Brand Performance Manager",
    [
        {"name": "topline_agent", "agent_type": "serving_endpoint",
         "serving_endpoint": {"name": topl_ep},
         "description": "ROUTE=topline. Share trends, value/volume share, YoY, share decomposition."},
        {"name": "insurgent_brands_analyst", "agent_type": "genie", "genie_space": {"id": g_ins},
         "description": "ROUTE=insurgent_brands. Emerging/challenger brands gaining share, velocity, 52w gain."},
        {"name": "distribution_velocity_analyst", "agent_type": "genie", "genie_space": {"id": g_dist},
         "description": "ROUTE=distribution_velocity. ACV gaps, SKU velocity, OOS, distribution gain/loss."},
    ],
    "Execution supervisor: dispatch a pre-confirmed ROUTE to one specialist.",
    ("The message contains ROUTE=<topline|insurgent_brands|distribution_velocity> plus context. "
     "The request is already enriched and user-confirmed. Read ROUTE and dispatch to the matching "
     "specialist; do NOT re-classify or ask for confirmation. Quantify answers. When chartable, end "
     "with: VISUALIZATION: <chart_type>|<x_field>|<y_field>|<title>"),
)
assert bpm_ep, "Brand Performance Manager endpoint_name not resolved; aborting"

print("\n=== STAGE 3 RESULT ===")
print("BPM_AGENT_ENDPOINT =", bpm_ep)
print("MAS#3 topline endpoint =", topl_ep)
print("genie:", {"brand": g_brand, "topline": g_topl, "insurgent": g_ins, "dist": g_dist})
open("/tmp/bpm_stage3.json", "w").write(json.dumps({
    "bpm_endpoint": bpm_ep, "topline_endpoint": topl_ep,
    "genie": {"brand": g_brand, "topline": g_topl, "insurgent": g_ins, "dist": g_dist}}))
