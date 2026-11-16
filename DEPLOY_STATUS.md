# Brand Performance Manager — Deployment Status

**Deployed:** 2026-06-05 · **Workspace:** `<workspace-host>` (Azure) · **Catalog:** `ar_dpcatalog`
**Scope:** Data + UC function + App + **Stage-3 AgentBricks (Genie + MAS)**. KAs deferred (see notes).

## Stage 3 — deployed (Genie + MAS, via direct REST)

| Artifact | ID / endpoint |
|---|---|
| Genie: BPM Brand Analysis | `01f160e0f9911c969a789ea6871dd48e` |
| Genie: BPM Topline Performance | `01f160e0fa071d9ea109a7f036249cd0` |
| Genie: BPM Insurgent Brands | `01f160e0fa671534af619e467d0c9ff6` |
| Genie: BPM Distribution & Velocity | `01f160e0fabd1769a0cd572d82db7f39` |
| MAS #3 Topline Agent | tile `0215b843-…` → endpoint `mas-0215b843-endpoint` (brand_analyst + category_analyst) |
| **Brand Performance Manager** (supervisor) | tile `c30e5158-ff72-4e89-a52d-6b216922f4e9` → endpoint **`mas-c30e5158-endpoint`** (READY) |

`app.yaml` `BPM_AGENT_ENDPOINT` = `mas-c30e5158-endpoint`; app SP granted CAN_QUERY.
**Verified end-to-end:** invoking the supervisor with `ROUTE=insurgent_brands` routed to the
insurgent Genie and returned real rows (Happy Roots +2.43 ppt, …).

> **2026-06-25 — MAS endpoints recreated.** The original `mas-be0195b8-endpoint` (and the
> `mas-ed7f0112` topline) were deleted, so the app's invocation returned **HTTP 404** after
> confirming a route. Recreated both MAS supervisors via `POST /api/2.0/multi-agent-supervisors`
> on top of the 4 surviving Genie spaces, re-granted the app SP `CAN_QUERY`, updated `app.yaml`,
> and redeployed. New endpoints: topline `mas-0215b843-endpoint`, supervisor `mas-c30e5158-endpoint`.
>
> **2026-07-09 — MAS endpoints recreated again + warehouse re-grant.** `mas-c30e5158-endpoint` and
> `mas-0215b843-endpoint` were both deleted again (Phase 2 → 404), and the app SP had also been
> dropped from the SQL warehouse ACL (Dashboard → **HTTP 403 PERMISSION_DENIED**). Fixes, all on top
> of the 4 surviving Genie spaces (see `_redeploy_mas.py`):
> - Recreated both supervisors: topline **`mas-83ef56ad-endpoint`**, Brand Performance Manager
>   **`mas-4f34a7d2-endpoint`**. (Tiles carry "v2/v3" name suffixes because the old-named tiles
>   survive and block same-name recreation, and there's no list/delete API to reclaim them; the
>   serving-endpoint names are auto-generated, so this is cosmetic.)
> - Re-granted app SP `<old-app-sp>-…`: **CAN_USE** on warehouse `148ccb90800933a1`, **CAN_QUERY** on
>   both new MAS endpoints.
> - Repointed `BPM_AGENT_ENDPOINT` → `mas-4f34a7d2-endpoint` in the deployed `app.yaml`; redeployed.
> - Verified: `ROUTE=insurgent_brands` returned real rows (Happy Roots +2.35 ppt 52w, TinyStart
>   Organic +2.07, Bobbie Natural +1.74).
>
> **2026-09-04 — MAS endpoints recreated AND the App itself recreated (demo prep).** Both the
> `mas-fa64d756-endpoint` supervisor and the **`brand-performance-manager` App** had been deleted
> (App get → "does not exist or is deleted"). Durable pieces survived: the 5 Delta tables, the
> `enrich_user_request` UC function, all 4 Genie spaces, and the Shared Endpoint warehouse (RUNNING).
> Recovery (`_redeploy_mas.py` now reads `MAS_SUFFIX` env; ran with `MAS_SUFFIX=20260904`):
> - Recreated both supervisors on the 4 surviving Genie spaces: topline **`mas-ff802aeb-endpoint`**,
>   Brand Performance Manager **`mas-c9aa7611-endpoint`** (both READY).
> - Recreated the App (`databricks apps create`) → **new** app SP
>   **`<app-sp-client-id>`** (`<app-sp-name>`). The old SP
>   `<old-app-sp>-…` is gone with the old app, so all grants had to be re-applied to the new SP:
>   USE_CATALOG on `ar_dpcatalog`; USE_SCHEMA+SELECT on `brand_performance`; USE_SCHEMA+EXECUTE on
>   `brand_perf_utils`; **CAN_USE** on warehouse `148ccb90800933a1`; **CAN_QUERY** on
>   `mas-c9aa7611-endpoint` (endpoint id `0d5cda3f47fc41ffac95e7c451b8873e`) **and CAN_QUERY on the
>   topline sub-agent `mas-ff802aeb-endpoint`** (endpoint id `d7c4931d51fd4f278fa1b02377062aa4`).
>   ⚠️ The topline sub-agent grant is easy to miss: the supervisor delegates to it on-behalf-of the
>   app SP, so ROUTE=topline fails with `does not have permission 'View' on Endpoint mas-ff802aeb-…`
>   if only the supervisor endpoint is granted. Insurgent/distribution routes go straight to Genie
>   spaces (no nested serving endpoint) and are unaffected.
> - Repointed `BPM_AGENT_ENDPOINT` → `mas-c9aa7611-endpoint` in `app/app.yaml`; synced `./app` →
>   `/Workspace/Users/<your-email>/bpm-app`; `databricks apps deploy` → SUCCEEDED, RUNNING.
> - Verified end-to-end (all against the live deploy): MAS invocation `ROUTE=insurgent_brands`
>   returned real rows (Happy Roots +2.27 ppt 52w); app `/api/health` ok; `/api/kpis` returned 6
>   rows from the warehouse (SP grants work at runtime); `/api/enrich` returned a `gate` decision
>   routed to `insurgent_brands` (Phase-1 UC function works).

> **2026-09-16 — MAS endpoints recreated AND the App recreated again (same failure as 2026-09-04).**
> App get → "does not exist or is deleted"; both MAS supervisors gone. All auth had also expired
> (both CLI profiles + MCP servers → invalid token) — re-ran `databricks auth login -p oauth-cpg`.
> Durable pieces all survived: 5 Delta tables, `enrich_user_request` UC fn, all 4 Genie spaces,
> Shared Endpoint warehouse `148ccb90800933a1` (RUNNING). Recovery (`_redeploy_mas.py` with
> `MAS_SUFFIX=20260916`, token pulled from `databricks auth token -p oauth-cpg`):
> - Recreated both supervisors on the 4 surviving Genie spaces: topline **`mas-265d5028-endpoint`**
>   (id `e674dc823b974abdba8194fc6b3b8f9f`), Brand Performance Manager **`mas-c00e856c-endpoint`**
>   (id `7c89909b7d66481ca5289ead10ce3a1c`) — both READY.
> - Recreated the App (`databricks apps create`) → **new** app SP
>   **`<app-sp-client-id>`** (`<app-sp-name>`, sp_id
>   `<sp-id>`). Re-applied all grants to the new SP: USE_CATALOG on `ar_dpcatalog`;
>   USE_SCHEMA+SELECT on `brand_performance`; USE_SCHEMA+EXECUTE on `brand_perf_utils`; **CAN_USE**
>   on warehouse `148ccb90800933a1`; **CAN_QUERY** on **both** `mas-c00e856c-endpoint` (supervisor)
>   **and** `mas-265d5028-endpoint` (topline sub-agent — the easy-to-miss one).
> - Repointed `BPM_AGENT_ENDPOINT` → `mas-c00e856c-endpoint` in `app/app.yaml`; synced `./app` →
>   `/Workspace/Users/<your-email>/bpm-app --full`; `databricks apps deploy` → SUCCEEDED,
>   RUNNING/ACTIVE.
> - Verified end-to-end: MAS `ROUTE=insurgent_brands` → real rows (Happy Roots +2.43 ppt 52w);
>   `/api/health` ok; `/api/kpis` → 6 rows from the warehouse; `/api/enrich` → `gate` routed to
>   `insurgent_brands` (Phase-1 UC function works).

> **2026-11-16 — MAS endpoints + App recreated again (same failure as 2026-09-16).** App,
> `mas-c00e856c-endpoint` and `mas-265d5028-endpoint` all deleted; Genie spaces, 5 Delta tables,
> `enrich_user_request` and warehouse `148ccb90800933a1` (RUNNING) survived. Recovery used
> `databricks api post /api/2.0/multi-agent-supervisors` (CLI OAuth, same payloads as
> `_redeploy_mas.py`, suffix `20261116`) — no raw token needed:
> - Topline **`mas-7ba91858-endpoint`** (id `c3206c5535d44b7cbe949c6c0b3b64a0`); Brand Performance
>   Manager **`mas-b3115b9a-endpoint`** (id `96d804ba02c44eeca66e96d4543b5b75`) — both READY.
> - New app SP **`<app-sp-client-id>`** (sp_id `<sp-id>`). Grants:
>   USE_CATALOG `ar_dpcatalog`; USE_SCHEMA+SELECT `brand_performance`; USE_SCHEMA+EXECUTE
>   `brand_perf_utils`; CAN_USE warehouse; CAN_QUERY on **both** MAS endpoints.
> - `BPM_AGENT_ENDPOINT` → `mas-b3115b9a-endpoint`; synced `./app` → `bpm-app --full`; deployed →
>   SUCCEEDED, RUNNING/ACTIVE. Verified MAS `ROUTE=insurgent_brands` → Happy Roots +2.43 ppt 52w.

> **2026-11-16 — Lakeflow ingest + Lakebase decision log added.**
> - **Lakeflow:** the 5 tables were exported as CSV to
>   `/Volumes/ar_dpcatalog/brand_performance/raw_data/landing/<table>/`, dropped, and recreated as
>   streaming tables by serverless pipeline **`bpm-brand-performance-ingest`**
>   (id `6340746d-0a21-4982-95d6-f3b6b81d7e8a`, source `pipelines/brand_performance_ingest.sql`,
>   synced to `/Workspace/Users/<your-email>/bpm-pipeline/`). Auto Loader + warn-only
>   expectations, explicit schemas. Verified row counts, checksums and column types are identical to
>   the pre-migration tables; supervisor `ROUTE=distribution_velocity` answers from them. Notebook 01
>   now lands CSVs (`land_raw`) instead of writing tables — run the pipeline after it.
> - **Lakebase:** Autoscaling project **`brand-performance-manager`** (PG 17, 0.5–1 CU, suspends after
>   5 min idle; endpoint `projects/brand-performance-manager/branches/production/endpoints/primary`).
>   Bound to the app as resource `lakebase` (`postgres`, CAN_CONNECT_AND_CREATE). `app/audit.py` writes
>   every gate decision (confirmed / overridden / cancelled / timed_out) to
>   `bpm_audit.routing_decisions` as a background task; `/api/hitl/stats` returns the confirmation
>   rate; the Advisor tab shows it. The app SP creates the table at startup (verified).
> - Registered the database in UC as catalog **`bpm_lakebase`** → query
>   `bpm_lakebase.bpm_audit.routing_decisions` from any SQL warehouse.

App fixes required for stage 3 to work (now applied):
- `call_domain_agent` now posts the **Responses API** shape `{"input": [...]}` (the endpoint
  rejects `{"messages": ...}`); `_extract_output_text` parses the `output` list; `error` is
  guarded against being `None`/str.

KAs (the topline `methodology_expert`) are still deferred — they need the databricks-sdk
`knowledge_assistants` service (no PyPI access in the deploy env) plus indexed PDFs (notebook 02).
MAS #3 runs fine with its 2 Genie sub-agents without it.

---


## ✅ Deployed and verified

| Component | Detail |
|---|---|
| Schemas | `ar_dpcatalog.brand_performance`, `ar_dpcatalog.brand_perf_utils` |
| Volume | `ar_dpcatalog.brand_performance.raw_data` |
| Delta tables (5) | `brand_topline_metrics` (37,440), `market_share_decomposition` (37,440), `insurgent_brand_tracker` (49,920), `distribution_velocity` (41,600), `category_benchmarks` (6,240) |
| UC function | `ar_dpcatalog.brand_perf_utils.enrich_user_request` (Phase 1 intake/classify) |
| App | **brand-performance-manager** — RUNNING |
| App URL | https://<app-url> |
| App service principal | `<app-sp-client-id>` (granted USE CATALOG/SCHEMA, SELECT, EXECUTE, warehouse CAN_USE) |
| Runtime SQL warehouse | `148ccb90800933a1` (Shared Endpoint — always running, no cold start) |

What works now: the **Dashboard / Insurgent / Distribution tabs** (query Delta directly) and the
**AI Advisor Phase 1** (enrichment + the HITL gate proposal). The AI Advisor's Phase 2 (actually
running an analysis) is inert until the agent layer below is created.

## ⏳ Stage 3 — AgentBricks (run in a session with the AI Dev Kit MCP server)

This was **not** done here because the `manage_genie` / `manage_ka` / `manage_mas` MCP tools were
not connected in the deploying session. To finish:

1. Open a session/workspace where the **AI Dev Kit MCP server** is active.
2. Run `notebooks/04_create_agentbricks.py` (creates 5 Genie Spaces, 2 KAs, MAS #3 Topline, and the
   Brand Performance Manager supervisor). Catalog is already `ar_dpcatalog`.
3. Copy the printed **`BPM_AGENT_ENDPOINT`** into `app/app.yaml` (replace the placeholder).
4. Redeploy the app:
   ```bash
   databricks sync app /Workspace/Users/<you>/bpm-app --full -p <profile>
   databricks apps deploy brand-performance-manager \
     --source-code-path /Workspace/Users/<you>/bpm-app -p <profile>
   ```

## Corrections made during deploy (vs. the repo as-authored)

- **`databricks.yml`** — declared the `catalog` variable (was assigned-but-undeclared → bundle wouldn't load) and removed the unresolved Lakebase resource binding (Lakebase is optional in the corrected design).
- **`enrich_user_request`** — recreated as a standard SQL UDF (`RETURN (… named_struct …)`). Notebook 03's version could not be created on a SQL warehouse or serverless because (a) it used `LANGUAGE SQL AS $$…$$`, and (b) it called `ai_extract(query, named_struct(...))` and `ai_classify(query, ARRAY, '<prompt string>')` — but the real signatures are `ai_extract(content, ARRAY<STRING> labels)` and `ai_classify(content, ARRAY<STRING> labels [, MAP<STRING,STRING> options])`. See `_create_enrich.py`.
- **`app.yaml`** — `BPM_WAREHOUSE_ID` set to the running Shared Endpoint; dead `BPM_VIZ_ENDPOINT` removed earlier.

## Known limitation

`enrich_user_request` uses the 2-arg `ai_classify` (bare labels), so intent classification is rough
(e.g. a clearly-topline question can land `out_of_scope`). For better accuracy, pass label
descriptions via the `ai_classify` options `MAP<STRING,STRING>`, or supply few-shot examples. This
affects routing-proposal quality only; the function returns the correct struct shape.

## Notebook 03 bug (not fixed here — optional functions)

`validate_routing_decision` in `notebooks/03_create_uc_functions.py` is unrunnable as written: its
Python-UDF body's `{confirmation_id}` / `{original_question…}` braces sit inside the *outer*
`spark.sql(f"""…""")`, so they evaluate at definition time. It's optional in the corrected design
(app-owned HITL), so it was skipped.
