"""
Redeploy ONLY the two MAS supervisors (Topline sub-agent + Brand Performance Manager).

The 4 Genie Spaces created in stage 3 still exist, so we reuse their IDs rather than
recreate them (which would duplicate). This mirrors _deploy_stage3.py's MAS creation,
which uses the direct REST API /api/2.0/multi-agent-supervisors. Reads DATABRICKS_HOST/TOKEN.
"""
from __future__ import annotations
import json, os, urllib.request, urllib.error

HOST = os.environ["DATABRICKS_HOST"].rstrip("/")
TOK  = os.environ["DATABRICKS_TOKEN"]

# Surviving Genie space IDs (verified live before running).
G_BRAND = "01f160e0f9911c969a789ea6871dd48e"   # BPM Brand Analysis
G_TOPL  = "01f160e0fa071d9ea109a7f036249cd0"   # BPM Topline Performance
G_INS   = "01f160e0fa671534af619e467d0c9ff6"   # BPM Insurgent Brands
G_DIST  = "01f160e0fabd1769a0cd572d82db7f39"   # BPM Distribution & Velocity


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


def mas(name, agents, description, instructions):
    r = call("POST", "/api/2.0/multi-agent-supervisors", {
        "name": name, "agents": agents,
        "description": description, "instructions": instructions,
    })
    if r.get("_http_error"):
        print(f"  MAS '{name}' FAILED: {r}"); return None, None
    # Response shape: {"multi_agent_supervisor": {"tile": {"tile_id", "serving_endpoint_name", ...}}}
    tileobj = ((r.get("multi_agent_supervisor") or {}).get("tile")) or {}
    tile = tileobj.get("tile_id")
    ep = tileobj.get("serving_endpoint_name")
    print(f"  MAS '{name}': tile_id={tile} endpoint_name={ep}")
    return tile, ep


# The prior tiles (named "Brand Performance Topline Agent" / "Brand Performance Manager")
# survive but their serving endpoints were deleted; recreating by the same name 409s, and
# there is no list/delete-by-name API to reclaim them. Use fresh unique names — the serving
# endpoint name is auto-generated (mas-<hash>-endpoint) regardless, so the app repoints anyway.
SUFFIX = os.environ.get("MAS_SUFFIX", "v2")

print("[1] MAS #3 — Topline Agent (2 Genie sub-agents; KA deferred)")
topl_tile, topl_ep = mas(
    f"Brand Performance Topline Agent {SUFFIX}",
    [
        {"name": "brand_analyst", "agent_type": "genie", "genie_space": {"id": G_BRAND},
         "description": "Brand share trends, value/volume share, YoY change over a time window."},
        {"name": "category_analyst", "agent_type": "genie", "genie_space": {"id": G_TOPL},
         "description": "Share-change decomposition (distribution, rate, penetration, frequency, basket)."},
    ],
    "Topline performance: share trends + 'what drove it' decomposition.",
    ("You analyze topline brand performance. For 'why did share change' questions, get the share "
     "delta from brand_analyst then the decomposition from category_analyst; name the primary driver. "
     "Always quantify (ppt, $, weeks). When chartable, end with: "
     "VISUALIZATION: <chart_type>|<x_field>|<y_field>|<title>"),
)
assert topl_ep, "MAS #3 endpoint_name not resolved; aborting"

print("[2] Brand Performance Manager — single execution supervisor")
bpm_tile, bpm_ep = mas(
    f"Brand Performance Manager {SUFFIX}",
    [
        {"name": "topline_agent", "agent_type": "serving_endpoint",
         "serving_endpoint": {"name": topl_ep},
         "description": "ROUTE=topline. Share trends, value/volume share, YoY, share decomposition."},
        {"name": "insurgent_brands_analyst", "agent_type": "genie", "genie_space": {"id": G_INS},
         "description": "ROUTE=insurgent_brands. Emerging/challenger brands gaining share, velocity, 52w gain."},
        {"name": "distribution_velocity_analyst", "agent_type": "genie", "genie_space": {"id": G_DIST},
         "description": "ROUTE=distribution_velocity. ACV gaps, SKU velocity, OOS, distribution gain/loss."},
    ],
    "Execution supervisor: dispatch a pre-confirmed ROUTE to one specialist.",
    ("The message contains ROUTE=<topline|insurgent_brands|distribution_velocity> plus context. "
     "The request is already enriched and user-confirmed. Read ROUTE and dispatch to the matching "
     "specialist; do NOT re-classify or ask for confirmation. Quantify answers. When chartable, end "
     "with: VISUALIZATION: <chart_type>|<x_field>|<y_field>|<title>"),
)
assert bpm_ep, "Brand Performance Manager endpoint_name not resolved; aborting"

print("\n=== MAS REDEPLOY RESULT ===")
print("BPM_AGENT_ENDPOINT =", bpm_ep)
print("MAS#3 topline endpoint =", topl_ep)
open("/tmp/bpm_mas_redeploy.json", "w").write(json.dumps({
    "bpm_endpoint": bpm_ep, "topline_endpoint": topl_ep,
    "bpm_tile": bpm_tile, "topline_tile": topl_tile}))
