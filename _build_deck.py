#!/usr/bin/env python3
"""
Build an editable Google-Slides-ready .pptx for the Brand Performance Manager
solution overview — using ONLY the Python standard library (no python-pptx, no
network). A .pptx is an OOXML ZIP; we emit the minimal valid part set plus one
content slide per section. Upload the result to Google Drive and open with
Google Slides (it converts to native, fully-editable slides).

Run:  python3 _build_deck.py
Out:  brand-performance-manager-overview.pptx
"""
from __future__ import annotations
import zipfile
from xml.sax.saxutils import escape

OUT = "brand-performance-manager-overview.pptx"

# ── Slide geometry (16:9 EMUs) ──────────────────────────────────────────────
EMU = 914400
W, H = 12192000, 6858000  # 13.333in x 7.5in

# ── Palette (Databricks-style) ──────────────────────────────────────────────
RED   = "FF3621"
DARK  = "1B2431"
NAVY  = "232F3E"
GRAY  = "8B9BAA"
WHITE = "FFFFFF"
GREEN = "00A972"
BLUE  = "1E7FDB"
AMBER = "FFB300"
LIGHT = "DCE3EA"


def _pt(emu_pts: float) -> int:
    return int(emu_pts)


def in_(v: float) -> int:
    return int(v * EMU)


# ── Low-level shape builders (DrawingML) ────────────────────────────────────
def _run(text, sz, color, bold=True, italic=False):
    b = ' b="1"' if bold else ' b="0"'
    i = ' i="1"' if italic else ''
    return (
        f'<a:r><a:rPr lang="en-US" sz="{sz}"{b}{i} dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="Segoe UI"/></a:rPr>'
        f'<a:t>{escape(text)}</a:t></a:r>'
    )


def _para(runs, align="l", bullet=False, space_after=600, line=None):
    algn = f' algn="{align}"'
    buf = '<a:buNone/>' if not bullet else (
        '<a:buFont typeface="Arial"/><a:buChar char="▸"/>')
    indent = ' marL="228600" indent="-228600"' if bullet else ''
    ln = f'<a:lnSpc><a:spcPct val="{line}"/></a:lnSpc>' if line else ''
    sa = f'<a:spcAft><a:spcPts val="{space_after}"/></a:spcAft>'
    return (f'<a:p><a:pPr{algn}{indent}>{ln}{sa}{buf}</a:pPr>{runs}</a:p>')


def _txbox(sid, name, x, y, cx, cy, paras, anchor="t", wrap=True):
    name = escape(name)
    w = ' wrap="square"' if wrap else ' wrap="none"'
    return f'''<p:sp>
  <p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody><a:bodyPr{w} lIns="0" tIns="0" rIns="0" bIns="0" anchor="{anchor}"/><a:lstStyle/>{''.join(paras)}</p:txBody>
</p:sp>'''


def _rect(sid, name, x, y, cx, cy, fill, line=None, line_w=12700, paras=None,
          anchor="ctr", round_=True):
    name = escape(name)
    geom = "roundRect" if round_ else "rect"
    fillxml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else '<a:noFill/>'
    lnxml = (f'<a:ln w="{line_w}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
             if line else '<a:ln><a:noFill/></a:ln>')
    body = ''.join(paras) if paras else '<a:p><a:endParaRPr lang="en-US"/></a:p>'
    return f'''<p:sp>
  <p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>{fillxml}{lnxml}</p:spPr>
  <p:txBody><a:bodyPr wrap="square" lIns="91440" tIns="68580" rIns="91440" bIns="45720" anchor="{anchor}"/><a:lstStyle/>{body}</p:txBody>
</p:sp>'''


def _slide_xml(shapes, bg=DARK):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{bg}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
{''.join(shapes)}
</p:spTree></p:cSld><p:clrMapOvr><a:overrideClrMapping bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/></p:clrMapOvr></p:sld>'''


# ── Reusable slide furniture ────────────────────────────────────────────────
def header(sid_start, kicker, title, subtitle=None):
    """Top bar + kicker + title (+ optional subtitle). Returns (shapes, next_id, content_y)."""
    s = []
    i = sid_start
    # red accent bar
    s.append(_rect(i, "bar", in_(0.85), in_(0.62), in_(0.6), in_(0.07), RED, round_=True)); i += 1
    s.append(_txbox(i, "kicker", in_(0.85), in_(0.30), in_(11), in_(0.3),
                    [_para(_run(kicker, 1100, RED), space_after=0)])); i += 1
    s.append(_txbox(i, "title", in_(0.85), in_(0.74), in_(11.6), in_(0.9),
                    [_para(_run(title, 2600, WHITE), space_after=0, line=100000)])); i += 1
    cy = 1.62
    if subtitle:
        s.append(_txbox(i, "sub", in_(0.85), in_(1.66), in_(11.0), in_(0.8),
                        [_para(_run(subtitle, 1250, GRAY, bold=False), space_after=0, line=120000)])); i += 1
        cy = 2.5
    return s, i, cy


def card(i, x, y, cx, cy, accent, title, body, icon=None):
    paras = []
    if icon:
        paras.append(_para(_run(icon, 1600, accent), space_after=300))
    paras.append(_para(_run(title, 1250, WHITE), space_after=200))
    for line in (body if isinstance(body, list) else [body]):
        paras.append(_para(_run(line, 1000, LIGHT, bold=False), space_after=120, line=118000))
    return _rect(i, "card", x, y, cx, cy, NAVY, line=accent, line_w=34925,
                 paras=paras, anchor="t")


# ── Build all slides ────────────────────────────────────────────────────────
slides = []

# Slide 1 — Title
s = []; i = 2
s.append(_rect(i, "lbar", 0, 0, in_(0.22), H, RED, round_=False)); i += 1
s.append(_txbox(i, "kick", in_(0.95), in_(2.05), in_(11), in_(0.4),
                [_para(_run("DATABRICKS AGENTBRICKS  ·  CPG ANALYTICS", 1250, RED), space_after=0)])); i += 1
s.append(_txbox(i, "t1", in_(0.9), in_(2.5), in_(11.5), in_(2.0),
                [_para(_run("Brand Performance Manager", 4400, WHITE), space_after=0, line=100000)])); i += 1
s.append(_txbox(i, "t2", in_(0.95), in_(4.35), in_(10.8), in_(1.6),
                [_para(_run("A hierarchical multi-agent AI application that turns natural-language "
                            "questions about brand share, competitive threats, and distribution gaps "
                            "into decision-ready answers — in under 90 seconds, fully native on Databricks.",
                            1350, GRAY, bold=False), space_after=0, line=130000)])); i += 1
s.append(_txbox(i, "foot", in_(0.95), in_(6.7), in_(11), in_(0.4),
                [_para(_run("NovaLife Nutrition — Analytics Center of Excellence  ·  Solution Overview",
                            1000, GRAY, bold=False), space_after=0)])); i += 1
slides.append(_slide_xml(s))

# Slide 2 — What is BPM
s, i, cy = header(2, "SECTION 01", "What is the Brand Performance Manager?",
                  "A conversational analytics co-pilot for CPG commercial teams: ask in plain English, "
                  "confirm the plan, get a charted answer.")
cw, gap = in_(3.72), in_(0.3)
x0 = in_(0.85)
s.append(card(i, x0, in_(2.55), cw, in_(2.0), RED, "Ask in plain English",
              "“Why did NovaBaby share drop the last 4 weeks at Walmart?” — no SQL, no dashboards, no waiting on an analyst.",
              "\U0001F4AC")); i += 1
s.append(card(i, x0+cw+gap, in_(2.55), cw, in_(2.0), BLUE, "Smart routing + your sign-off",
              "It classifies the question, proposes a plan, and waits for you to Confirm before running anything.",
              "\U0001F9ED")); i += 1
s.append(card(i, x0+2*(cw+gap), in_(2.55), cw, in_(2.0), GREEN, "Decision-ready answer",
              "Returns a quantified narrative (−1.3 ppt, 61% from distribution loss) plus an auto-rendered chart.",
              "\U0001F4CA")); i += 1
fw = in_(5.67)
s.append(card(i, x0, in_(4.75), fw, in_(1.7), AMBER, "In one line — for executives",
              "Replaces the 2–3 day ‘ask an analyst, wait for a deck’ cycle with a 90-second self-service conversation, so decisions run on fresh data.")); i += 1
s.append(card(i, x0+fw+gap, in_(4.75), fw, in_(1.7), GREEN, "In one line — for engineers",
              "A Streamlit app orchestrates a two-phase flow: a UC-function intake call, an app-owned HITL gate, then one Multi-Agent Supervisor dispatching to Genie specialists.")); i += 1
slides.append(_slide_xml(s))

# Slide 3 — Problems it solves (table-like rows)
s, i, cy = header(2, "SECTION 02", "What problems does it solve?",
                  "Today's brand-performance workflow is fragmented and slow — insight requests take days; threats are spotted weeks late.")
rows = [
    ("Data fragmentation", "Topline, insurgent & distribution data live in separate syndicated feeds (Nielsen, IRI/Circana)", "Analysts spend 2–3 days per request"),
    ("Insight latency", "Weekly reporting cadence — insurgent brands gaining velocity are caught late", "Threats spotted 2–3 weeks late"),
    ("Visualization bottleneck", "Charts need manual Excel / Tableau work after the data is pulled", "Decision-ready output takes hours"),
    ("Expert dependency", "Only senior analysts know which queries to run across which tables", "Insight generation doesn't scale"),
    ("No routing intelligence", "Users don't know if it's a topline, insurgent, or distribution question", "Wrong data → incomplete decisions"),
]
y = in_(2.55); rh = in_(0.78)
c1, c2, c3 = in_(0.85), in_(3.95), in_(8.7)
w1, w2, w3 = in_(3.0), in_(4.65), in_(3.45)
# header row
s.append(_txbox(i, "h1", c1, in_(2.25), w1, in_(0.3), [_para(_run("PAIN POINT", 1050, AMBER), space_after=0)])); i += 1
s.append(_txbox(i, "h2", c2, in_(2.25), w2, in_(0.3), [_para(_run("TODAY'S BROKEN WORKFLOW", 1050, AMBER), space_after=0)])); i += 1
s.append(_txbox(i, "h3", c3, in_(2.25), w3, in_(0.3), [_para(_run("BUSINESS IMPACT", 1050, AMBER), space_after=0)])); i += 1
for r, (a, b, c) in enumerate(rows):
    yy = y + r*rh
    fill = NAVY if r % 2 == 0 else "1F2A3A"
    s.append(_rect(i, f"row{r}", in_(0.8), yy, in_(11.65), rh-in_(0.08), fill, round_=True)); i += 1
    s.append(_txbox(i, f"r{r}a", c1+in_(0.1), yy+in_(0.12), w1, rh, [_para(_run(a, 1100, WHITE), space_after=0, line=110000)], anchor="ctr")); i += 1
    s.append(_txbox(i, f"r{r}b", c2, yy+in_(0.12), w2, rh, [_para(_run(b, 1000, LIGHT, bold=False), space_after=0, line=112000)], anchor="ctr")); i += 1
    s.append(_txbox(i, f"r{r}c", c3, yy+in_(0.12), w3, rh, [_para(_run(c, 1000, RED), space_after=0, line=112000)], anchor="ctr")); i += 1
slides.append(_slide_xml(s))

# Slide 4 — Outcome / value (stat cards + two lists)
s, i, cy = header(2, "SECTION 03", "The outcome: one interface, every question",
                  "A single natural-language surface, human confirmation before execution, chart-ready answers.")
stat_w = in_(2.78); sx = in_(0.85)
stats = [("< 90s", "answer vs. 2–3 days", AMBER), ("4", "personas: VP → Sales Dir.", GREEN),
         ("3", "routes: topline / insurgent / dist.", BLUE), ("0", "external infra — 100% Databricks", RED)]
for n, (big, lbl, col) in enumerate(stats):
    s.append(_rect(i, f"st{n}", sx+n*(stat_w+in_(0.2)), in_(2.5), stat_w, in_(1.5), NAVY, line=col, line_w=34925,
                   paras=[_para(_run(big, 2800, col), align="ctr", space_after=120),
                          _para(_run(lbl, 950, GRAY, bold=False), align="ctr", space_after=0, line=115000)], anchor="ctr")); i += 1
lw = in_(5.67)
s.append(_rect(i, "who", in_(0.85), in_(4.2), lw, in_(2.25), NAVY, line=AMBER, line_w=25400, anchor="t", paras=[
    _para(_run("Who uses it", 1250, AMBER), space_after=200),
    _para(_run("VP Commercial — total share vs. 12 weeks ago", 1000, LIGHT, bold=False), bullet=True, space_after=120),
    _para(_run("Brand Manager — which subcategories drive share loss", 1000, LIGHT, bold=False), bullet=True, space_after=120),
    _para(_run("Category Analyst — insurgents gaining >1pt in baby food", 1000, LIGHT, bold=False), bullet=True, space_after=120),
    _para(_run("Sales Director — SKUs below ACV threshold in Northeast", 1000, LIGHT, bold=False), bullet=True, space_after=0),
])); i += 1
s.append(_rect(i, "not", in_(0.85)+lw+in_(0.3), in_(4.2), lw, in_(2.25), NAVY, line=GREEN, line_w=25400, anchor="t", paras=[
    _para(_run("What it is deliberately NOT", 1250, GREEN), space_after=200),
    _para(_run("Not a replacement for the full Tableau / Looker BI layer", 1000, LIGHT, bold=False), bullet=True, space_after=120),
    _para(_run("Not a financial planning or forecasting system", 1000, LIGHT, bold=False), bullet=True, space_after=120),
    _para(_run("Not a supply-chain or operations data tool", 1000, LIGHT, bold=False), bullet=True, space_after=120),
    _para(_run("Scoped tightly so every answer is fast and trustworthy", 1000, LIGHT, bold=False), bullet=True, space_after=0),
])); i += 1
slides.append(_slide_xml(s))

# Slide 5 — Key challenges
s, i, cy = header(2, "SECTION 04", "Key challenges & the decisions they forced",
                  "Building agentic AI on a real platform: four hard constraints shaped the architecture.")
cw2 = in_(5.67); ch = in_(1.95); gx = in_(0.3); gy = in_(0.2)
x0 = in_(0.85); y0 = in_(2.5)
ch_cards = [
    (RED, "\U0001F512 Agents can't pause for a human",
     "A deployed supervisor endpoint is synchronous request/response — it can't suspend mid-run for approval. Solution: the app owns the HITL gate; the agent runs only after you confirm."),
    (BLUE, "⚡ Nested supervisors compound latency",
     "Wrapping intake & routing in their own agent layers adds an LLM hop each. Solution: intake is one UC-function call; one supervisor dispatches directly. MAS 4 → 2."),
    (AMBER, "\U0001F3B2 LLM-generated charts are fragile",
     "Asking an LLM for full Plotly JSON on the critical path is an extra call with a big failure surface. Solution: charts render deterministically from SQL → >95% success."),
    (GREEN, "\U0001F9ED Right data for the right question",
     "Users don't know if they're asking topline / insurgent / distribution. Solution: Phase-1 enrichment classifies intent; the confirmed ROUTE= guarantees the right specialist."),
]
for n, (col, t, b) in enumerate(ch_cards):
    cx_ = x0 + (n % 2)*(cw2+gx)
    cyy = y0 + (n // 2)*(ch+gy)
    s.append(card(i, cx_, cyy, cw2, ch, col, t, b)); i += 1
slides.append(_slide_xml(s))

# Slide 6 — Reference Architecture (4 stacked layers)
s, i, cy = header(2, "SECTION 05", "Reference Architecture", None)
lx, lw2 = in_(0.85), in_(11.6)
def layer(i, y, h, name, col, nodes):
    sh = [_rect(i, name+"_box", lx, y, lw2, h, NAVY, line=col, line_w=28575, round_=True,
                paras=[_para(_run(name, 950, col), space_after=0)], anchor="t")]
    ni = i + 1
    nodes_n = len(nodes)
    nw = (lw2 - in_(0.4) - (nodes_n-1)*in_(0.2)) // nodes_n
    for k, (nt, ns) in enumerate(nodes):
        nx = lx + in_(0.2) + k*(nw+in_(0.2))
        sh.append(_rect(ni, f"{name}_n{k}", nx, y+in_(0.42), nw, h-in_(0.6), "2A3850", line=col, line_w=12700, round_=True,
                        paras=[_para(_run(nt, 1000, WHITE), align="ctr", space_after=80, line=108000),
                               _para(_run(ns, 850, GRAY, bold=False), align="ctr", space_after=0, line=110000)], anchor="ctr")); ni += 1
    return sh, ni

y = in_(1.55); lh = in_(1.18); arrow_h = in_(0.32)
sh, i = layer(i, y, in_(0.95), "USER", BLUE, [("\U0001F464  Commercial user (Browser)", "asks a natural-language question")])
s += sh
def arrow(i, y, label=None):
    return _txbox(i, "arr", lx, y, lw2, arrow_h, [_para(_run("▼" + (("    "+label) if label else ""), 1100, GRAY, bold=False), align="ctr", space_after=0)])
s.append(arrow(i, y+in_(0.95))); i += 1
y2 = y+in_(0.95)+arrow_h
sh, i = layer(i, y2, lh, "ORCHESTRATION — DATABRICKS APPS (STREAMLIT)", BLUE, [
    ("① Enrich", "UC Function + Mosaic AI (ai_query)"),
    ("② HITL Gate", "Streamlit session_state"),
    ("③ Execute", "Agent serving endpoint call"),
    ("④ Render", "Plotly · Statement Execution API")]); s += sh
s.append(arrow(i, y2+lh, "Model Serving · OAuth (x-forwarded-access-token)")); i += 1
y3 = y2+lh+arrow_h
sh, i = layer(i, y3, lh, "AGENT LAYER — MOSAIC AI AGENT BRICKS (MULTI-AGENT SUPERVISOR)", RED, [
    ("\U0001F4C8 Topline Supervisor", "Agent Bricks MAS + Knowledge Assistant"),
    ("\U0001F680 Insurgent Brands", "AI/BI Genie Space"),
    ("\U0001F3EA Distribution & Velocity", "AI/BI Genie Space")]); s += sh
s.append(arrow(i, y3+lh)); i += 1
y4 = y3+lh+arrow_h
sh, i = layer(i, y4, lh, "DATA & GOVERNANCE — UNITY CATALOG", GREEN, [
    ("Delta Lake tables", "5 tables · ~75K rows · 104 wks"),
    ("Databricks SQL Warehouse", "serverless compute"),
    ("Vector Search", "Knowledge Assistant index"),
    ("Unity Catalog Volumes", "source PDFs")]); s += sh
slides.append(_slide_xml(s))

# Slide 7 — Key components table
s, i, cy = header(2, "SECTION 06", "Key components — what each piece does", None)
comps = [
    ("Databricks Apps", "Apps", "Hosts the Streamlit UI + orchestrator. Runs the two-phase flow, owns the HITL gate, renders charts — one governed deployable.", BLUE),
    ("Unity Catalog Function", "UC + AI", "enrich_user_request: SQL fn calling Mosaic AI (ai_extract / ai_classify) to pull entities and classify intent.", BLUE),
    ("HITL Gate", "Apps", "App-owned confirmation in Streamlit session_state. Shows proposed route + context before any agent runs.", AMBER),
    ("Agent Bricks — MAS", "Mosaic AI", "Multi-Agent Supervisor. Reads ROUTE= and dispatches a pre-confirmed request to exactly one specialist.", RED),
    ("Topline Supervisor", "Agent Bricks", "Sub-supervisor for share questions: 2 Genie Spaces + a Knowledge Assistant for 'what drove the change'.", RED),
    ("AI/BI Genie Spaces (×4)", "AI/BI", "Natural-language-to-SQL over Delta: Brand Analysis, Topline, Insurgent Brands, Distribution & Velocity.", GREEN),
    ("Delta Lake + SQL Warehouse", "UC", "5 governed tables (~75K rows, 104 wks) queried via the Statement Execution API for tiles + deterministic charts.", GREEN),
]
y = in_(1.7); rh = in_(0.66)
cc1, cc2, cc3 = in_(0.95), in_(4.15), in_(5.5)
wc1, wc2, wc3 = in_(3.0), in_(1.25), in_(6.9)
s.append(_txbox(i, "hh1", cc1, in_(1.42), wc1, in_(0.3), [_para(_run("COMPONENT", 1000, AMBER), space_after=0)])); i += 1
s.append(_txbox(i, "hh2", cc2, in_(1.42), wc2, in_(0.3), [_para(_run("LAYER", 1000, AMBER), space_after=0)])); i += 1
s.append(_txbox(i, "hh3", cc3, in_(1.42), wc3, in_(0.3), [_para(_run("ROLE IN THE SOLUTION", 1000, AMBER), space_after=0)])); i += 1
for r, (a, b, c, col) in enumerate(comps):
    yy = y + r*rh
    fill = NAVY if r % 2 == 0 else "1F2A3A"
    s.append(_rect(i, f"crow{r}", in_(0.85), yy, in_(11.6), rh-in_(0.07), fill, round_=True)); i += 1
    s.append(_txbox(i, f"cr{r}a", cc1+in_(0.1), yy, wc1, rh, [_para(_run(a, 1000, WHITE), space_after=0, line=108000)], anchor="ctr")); i += 1
    s.append(_rect(i, f"cr{r}tag", cc2, yy+in_(0.13), in_(1.05), in_(0.36), col, round_=True,
                   paras=[_para(_run(b, 850, WHITE), align="ctr", space_after=0)], anchor="ctr")); i += 1
    s.append(_txbox(i, f"cr{r}c", cc3, yy, wc3, rh, [_para(_run(c, 950, LIGHT, bold=False), space_after=0, line=110000)], anchor="ctr")); i += 1
slides.append(_slide_xml(s))

# Slide 8 — End to end flow
s, i, cy = header(2, "SECTION 07", "End-to-end: one question, start to finish",
                  "Example — “Why did NovaBaby share drop the last 4 weeks at Walmart?”")
steps = [
    ("1", "Ask", "User types the question in the AI Advisor tab."),
    ("2", "Phase 1 — Enrich & classify", "enrich_user_request → brand=NovaBaby, retailer=Walmart, window=4W, type=topline, complete=true."),
    ("3", "HITL Gate — confirm the plan", "App proposes route Topline Performance + context. User clicks ✅ Confirm & Run (or changes the route)."),
    ("4", "Phase 2 — Execute", "One supervisor call with ROUTE=topline → dispatches to MAS #3 → Genie queries share + decomposition."),
    ("5", "Answer + chart", "“NovaBaby share declined 1.3 ppt L4W at Walmart. Primary driver: distribution loss (−0.8 ppt, 61%)…” + Plotly chart."),
]
y = in_(2.55); rh = in_(0.82)
for n, (num, t, b) in enumerate(steps):
    yy = y + n*rh
    s.append(_rect(i, f"num{n}", in_(0.9), yy, in_(0.55), in_(0.55), RED, round_=True,
                   paras=[_para(_run(num, 1500, WHITE), align="ctr", space_after=0)], anchor="ctr")); i += 1
    s.append(_txbox(i, f"st{n}t", in_(1.7), yy-in_(0.02), in_(10.6), in_(0.35),
                    [_para(_run(t, 1300, WHITE), space_after=0)])); i += 1
    s.append(_txbox(i, f"st{n}b", in_(1.7), yy+in_(0.33), in_(10.6), in_(0.4),
                    [_para(_run(b, 1000, GRAY, bold=False), space_after=0, line=112000)])); i += 1
slides.append(_slide_xml(s))

# Slide 9 — Closing
s = []; i = 2
s.append(_rect(i, "lbar", 0, 0, in_(0.22), H, RED, round_=False)); i += 1
s.append(_txbox(i, "ck", in_(0.95), in_(0.95), in_(11), in_(0.4),
                [_para(_run("SUMMARY", 1250, RED), space_after=0)])); i += 1
s.append(_txbox(i, "ct", in_(0.9), in_(1.4), in_(11.5), in_(1.4),
                [_para(_run("Fast answers, the right data, and a human in control.", 3000, WHITE), space_after=0, line=104000)])); i += 1
cw3 = in_(3.72); cx0 = in_(0.85)
s.append(card(i, cx0, in_(3.1), cw3, in_(2.4), RED, "The problem",
              "Fragmented syndicated data and 2–3 day insight cycles let competitive threats go unnoticed for weeks.", "\U0001F3AF")); i += 1
s.append(card(i, cx0+cw3+in_(0.3), in_(3.1), cw3, in_(2.4), BLUE, "The architecture",
              "A Streamlit app orchestrates intake → HITL gate → one supervisor → Genie specialists, all native on Databricks.", "\U0001F3D7")); i += 1
s.append(card(i, cx0+2*(cw3+in_(0.3)), in_(3.1), cw3, in_(2.4), GREEN, "The result",
              "Decision-ready, quantified, charted answers in under 90 seconds — for every commercial persona.", "✅")); i += 1
s.append(_txbox(i, "foot", in_(0.95), in_(5.95), in_(11), in_(0.5),
                [_para(_run("Built with Databricks AgentBricks · Genie · Databricks Apps   |   NovaLife Nutrition — Analytics CoE",
                            1050, GRAY, bold=False), space_after=0)])); i += 1
slides.append(_slide_xml(s))


# ── Speaker notes (one entry per slide, in order) ───────────────────────────
NOTES = [
    # 1 — Title
    "Brand Performance Manager: ask a brand question in plain English, get a "
    "decision-ready answer in under 90 seconds — all on Databricks.\n\n"
    "• Replaces the 2–3 day 'ask an analyst, wait for a deck' cycle.\n"
    "• A human still confirms what runs.\n"
    "• Agenda: what it is, problems solved, hard challenges, architecture.",
    # 2 — What is BPM
    "What it really does: a NL-to-insight engine for three CPG questions — am I "
    "winning share, who's the insurgent threat, where are my distribution gaps.\n\n"
    "• It reads the question, extracts the entities (brand, retailer, time window).\n"
    "• Picks the right specialist and shows you the plan to confirm.\n"
    "• Queries governed data and answers with a number + a chart — not a dashboard to go dig through.\n"
    "• Use the two one-liners for a mixed room (exec vs. engineer).",
    # 3 — Problems it solves
    "Why it exists. Walk the five pains fast:\n\n"
    "• Data fragmented across Nielsen / IRI / Circana → days per request.\n"
    "• Weekly cadence → insurgent threats caught 2–3 weeks late (the revenue one — pause here).\n"
    "• Charts are manual; only senior analysts know the queries; users don't even know which question type they're asking.\n"
    "• Right column = the business cost of each.",
    # 4 — Outcome / value
    "Problem → outcome. Hit the four numbers:\n\n"
    "• <90s vs. 2–3 days · 4 personas · 3 routes · 0 external infra (100% Databricks — security & TCO win).\n"
    "• 'Who uses it' = breadth, VP to Sales Director.\n"
    "• 'What it's NOT' manages scope: not the BI layer, not forecasting, not supply chain. Tight scope = fast, trustworthy answers.",
    # 5 — Key challenges
    "The credibility slide — the design is earned. Four constraints, four decisions:\n\n"
    "• Agents can't pause mid-run → the app owns the human gate.\n"
    "• Nested supervisors add latency → 4 agents collapsed to 2.\n"
    "• LLM-generated chart JSON is fragile → charts render deterministically from SQL (>95% success).\n"
    "• Wrong table = wrong answer → enrichment classifies intent, ROUTE= guarantees the right specialist.",
    # 6 — Reference Architecture
    "Walk it top to bottom, naming the Databricks products:\n\n"
    "• User asks in the browser.\n"
    "• Databricks Apps (Streamlit) orchestrates: enrich via a UC Function + Mosaic AI, HITL gate in session_state, "
    "call the agent serving endpoint, render via the Statement Execution API.\n"
    "• Mosaic AI Agent Bricks — one Multi-Agent Supervisor dispatches to one specialist (Topline supervisor, or an AI/BI Genie Space).\n"
    "• All on Unity Catalog: Delta Lake, serverless SQL Warehouse, Vector Search, UC Volumes. Punchline: no external infra.",
    # 7 — Key components
    "Reference slide — don't read every row. Highlights:\n\n"
    "• Databricks Apps = the one deployable that orchestrates everything.\n"
    "• UC Function calls Mosaic AI for deterministic intake.\n"
    "• HITL gate lives in the app, not the agent.\n"
    "• Agent Bricks MAS reads ROUTE= and dispatches; AI/BI Genie does the NL-to-SQL over Delta. Colors map back to the architecture layers.",
    # 8 — End-to-end flow
    "Make it concrete — 'Why did NovaBaby share drop L4W at Walmart?'\n\n"
    "• Enrich: brand=NovaBaby, retailer=Walmart, 4W, type=topline.\n"
    "• Gate: app proposes Topline route → user clicks Confirm (the human checkpoint).\n"
    "• Execute: one supervisor call, ROUTE=topline → Genie returns share + decomposition.\n"
    "• Answer: 'down 1.3 ppt, 61% from distribution loss' + chart. Whole loop < 90s.",
    # 9 — Closing
    "Tie the three threads:\n\n"
    "• Problem — fragmented data, slow cycles, threats missed for weeks.\n"
    "• Architecture — Databricks Apps → HITL gate → Agent Bricks supervisor → Genie, all native.\n"
    "• Result — quantified, charted answers in <90s for every persona.\n"
    "Close on: fast answers, the right data, a human in control. Offer a live demo of the AI Advisor tab.",
]
assert len(NOTES) == len(slides), f"NOTES count {len(NOTES)} != slides {len(slides)}"


# ── OOXML package scaffolding ───────────────────────────────────────────────
N = len(slides)

content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
 '<Default Extension="xml" ContentType="application/xml"/>'
 '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
 '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>'
 '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
 '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
 '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
 '<Override PartName="/ppt/notesMasters/notesMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"/>'
 + ''.join(f'<Override PartName="/ppt/slides/slide{n}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for n in range(1, N+1))
 + ''.join(f'<Override PartName="/ppt/notesSlides/notesSlide{n}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>' for n in range(1, N+1))
 + '</Types>')

root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
 '</Relationships>')

sldIdLst = ''.join(f'<p:sldId id="{256+n}" r:id="rId{n+2}"/>' for n in range(N))
presentation = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" saveSubsetFonts="1">'
 '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
 f'<p:sldIdLst>{sldIdLst}</p:sldIdLst>'
 f'<p:sldSz cx="{W}" cy="{H}" type="screen16x9"/>'
 f'<p:notesSz cx="{H}" cy="{W}"/></p:presentation>')

pres_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
 '<Relationship Id="rIdTheme" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
 '<Relationship Id="rIdProps" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>'
 '<Relationship Id="rIdNotesMaster" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster" Target="notesMasters/notesMaster1.xml"/>'
 + ''.join(f'<Relationship Id="rId{n+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{n+1}.xml"/>' for n in range(N))
 + '</Relationships>')

pres_props = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<p:presentationPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>')

theme = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">'
 '<a:themeElements><a:clrScheme name="Office">'
 '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
 '<a:dk2><a:srgbClr val="1B2431"/></a:dk2><a:lt2><a:srgbClr val="F5F7FA"/></a:lt2>'
 '<a:accent1><a:srgbClr val="FF3621"/></a:accent1><a:accent2><a:srgbClr val="1E7FDB"/></a:accent2>'
 '<a:accent3><a:srgbClr val="00A972"/></a:accent3><a:accent4><a:srgbClr val="FFB300"/></a:accent4>'
 '<a:accent5><a:srgbClr val="8B9BAA"/></a:accent5><a:accent6><a:srgbClr val="9B7EDE"/></a:accent6>'
 '<a:hlink><a:srgbClr val="1E7FDB"/></a:hlink><a:folHlink><a:srgbClr val="9B7EDE"/></a:folHlink></a:clrScheme>'
 '<a:fontScheme name="Office"><a:majorFont><a:latin typeface="Segoe UI"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
 '<a:minorFont><a:latin typeface="Segoe UI"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
 '<a:fmtScheme name="Office"><a:fillStyleLst>'
 '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
 '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
 '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
 '<a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
 '<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
 '<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
 '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
 '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
 '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
 '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>'
 '</a:themeElements></a:theme>')

# Minimal slide master + layout (blank). Slides carry their own clrMapOvr.
slide_master = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
 '<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="1B2431"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
 '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
 '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
 '</p:spTree></p:cSld>'
 '<p:clrMap bg1="dk1" tx1="lt1" bg2="dk2" tx2="lt2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
 '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
 '<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>'
 '</p:sldMaster>')

slide_master_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
 '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
 '</Relationships>')

slide_layout = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">'
 '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
 '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
 '</p:spTree></p:cSld>'
 '<p:clrMapOvr><a:overrideClrMapping bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/></p:clrMapOvr>'
 '</p:sldLayout>')

slide_layout_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
 '</Relationships>')

def slide_rels(n):
    """Each slide links its layout AND its notes slide."""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
     '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
     f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide{n}.xml"/>'
     '</Relationships>')


# ── Notes master + per-slide notes parts ────────────────────────────────────
notes_master = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<p:notesMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
 '<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
 '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
 '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
 '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder 1"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
 '<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>'
 f'<p:spPr><a:xfrm><a:off x="457200" y="457200"/><a:ext cx="{H-914400}" cy="{W-914400}"/></a:xfrm>'
 '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
 '<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US"/><a:t></a:t></a:r></a:p></p:txBody></p:sp>'
 '</p:spTree></p:cSld>'
 '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
 '<p:notesStyle><a:lvl1pPr><a:defRPr sz="1200"/></a:lvl1pPr></p:notesStyle>'
 '</p:notesMaster>')

notes_master_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
 '</Relationships>')


def notes_slide(text):
    # Each line becomes its own paragraph so bullet lists render line-by-line.
    lines = text.split("\n")
    paras = ""
    for ln in lines:
        if ln == "":
            paras += '<a:p><a:endParaRPr lang="en-US" sz="1200"/></a:p>'
        else:
            paras += (f'<a:p><a:r><a:rPr lang="en-US" sz="1200" dirty="0"/>'
                      f'<a:t>{escape(ln)}</a:t></a:r></a:p>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
     '<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
     '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
     '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
     '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder 1"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
     '<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>'
     '<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>'
     f'{paras}</p:txBody></p:sp>'
     '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>')


def notes_slide_rels(n):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
     f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="../slides/slide{n}.xml"/>'
     '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster" Target="../notesMasters/notesMaster1.xml"/>'
     '</Relationships>')

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", root_rels)
    z.writestr("ppt/presentation.xml", presentation)
    z.writestr("ppt/_rels/presentation.xml.rels", pres_rels)
    z.writestr("ppt/presProps.xml", pres_props)
    z.writestr("ppt/theme/theme1.xml", theme)
    z.writestr("ppt/slideMasters/slideMaster1.xml", slide_master)
    z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels)
    z.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout)
    z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels)
    z.writestr("ppt/notesMasters/notesMaster1.xml", notes_master)
    z.writestr("ppt/notesMasters/_rels/notesMaster1.xml.rels", notes_master_rels)
    for n, xml in enumerate(slides, start=1):
        z.writestr(f"ppt/slides/slide{n}.xml", xml)
        z.writestr(f"ppt/slides/_rels/slide{n}.xml.rels", slide_rels(n))
        z.writestr(f"ppt/notesSlides/notesSlide{n}.xml", notes_slide(NOTES[n-1]))
        z.writestr(f"ppt/notesSlides/_rels/notesSlide{n}.xml.rels", notes_slide_rels(n))

print(f"Wrote {OUT} with {N} slides + {N} speaker-notes pages")
