#!/usr/bin/env python3
"""
Build the Brand Performance Manager **submission deck** (reference architecture +
value case) as an editable .pptx (OOXML ZIP, stdlib only), in the Databricks cream
house style (DM Sans, #F9F7F4 background).

Order follows the submission + AI role-play guidance — frame, value, tell-show-tell:
  1. Outcome            — customer (NovaLife Nutrition), problem, headline numbers
  2. Value case         — quantified, with explicit assumptions
  3. What you'll see    — the "tell" before the live demo (3 moments → 3 KPIs)
     [live demo in the app]
  4. End-to-end journey — raw CSV → Lakeflow → UC → Gen AI → Genie/Agents → App → Lakebase
  5. Reference architecture — service-labeled swimlanes
  6. Decisions & trade-offs
  7. Built with AI as a teammate — tools, prompts, patterns
  8. Close              — what it means + pilot criteria + the ask
  9. Appendix — Databricks services used

Speaker notes carry the timed role-play talk track; full script in ROLEPLAY_SCRIPT.md.

Run:  python3 _build_reference_architecture.py
Out:  brand-performance-manager-reference-architecture.pptx
"""
from __future__ import annotations
import zipfile
from xml.sax.saxutils import escape

OUT = "brand-performance-manager-reference-architecture.pptx"

# ── Slide geometry (16:9 EMUs) ──────────────────────────────────────────────
EMU = 914400
W, H = 12192000, 6858000  # 13.333in x 7.5in

# ── House palette (cream brand look) ────────────────────────────────────────
CREAM   = "F9F7F4"
LAVA    = "FF3621"   # eyebrow + small-caps labels
CORAL   = "FF5F46"   # arrows / accents
TEAL    = "1B3139"   # titles, card headers, dark accent card
BODY    = "3A3838"
SUB     = "5A5755"
LTEAL   = "B9C6CB"   # text on dark
DIV     = "E4E2DD"
WHITE   = "FFFFFF"
FONT    = "DM Sans"

M  = 0.7            # left/right margin (in)
CW = 13.333 - 2 * M  # content width (in)


def in_(v: float) -> int:
    return int(v * EMU)


# ── Low-level shape builders (DrawingML) ────────────────────────────────────
def R(text, sz, color, bold=False, italic=False, spc=0):
    b = ' b="1"' if bold else ' b="0"'
    i = ' i="1"' if italic else ''
    s = f' spc="{spc}"' if spc else ''
    return (
        f'<a:r><a:rPr lang="en-US" sz="{int(sz*100)}"{b}{i}{s} dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{FONT}"/></a:rPr>'
        f'<a:t>{escape(text)}</a:t></a:r>'
    )


def P(runs, align="l", after=0, line=None, bullet=False):
    if isinstance(runs, (list, tuple)):
        runs = ''.join(runs)
    buf = ('<a:buFont typeface="Arial"/><a:buChar char="•"/>' if bullet else '<a:buNone/>')
    ind = ' marL="171450" indent="-171450"' if bullet else ''
    ln = f'<a:lnSpc><a:spcPct val="{line}"/></a:lnSpc>' if line else ''
    return (f'<a:p><a:pPr algn="{align}"{ind}>{ln}<a:spcAft><a:spcPts val="{int(after*100)}"/></a:spcAft>'
            f'{buf}</a:pPr>{runs}</a:p>')


class Slide:
    def __init__(self):
        self.shapes, self.i = [], 2

    def _id(self):
        self.i += 1
        return self.i

    def text(self, x, y, w, h, paras, anchor="t"):
        sid = self._id()
        self.shapes.append(f'''<p:sp>
  <p:nvSpPr><p:cNvPr id="{sid}" name="t{sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{in_(x)}" y="{in_(y)}"/><a:ext cx="{in_(w)}" cy="{in_(h)}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
  <p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="{anchor}"/><a:lstStyle/>{''.join(paras)}</p:txBody>
</p:sp>''')

    def box(self, x, y, w, h, fill=WHITE, line=DIV, paras=None, anchor="t",
            round_=True, dash=False, line_w=9525, pad=0.16):
        sid = self._id()
        geom = "roundRect" if round_ else "rect"
        adj = '<a:gd name="adj" fmla="val 7000"/>' if round_ else ''
        fx = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else '<a:noFill/>'
        dx = '<a:prstDash val="dash"/>' if dash else ''
        lx = (f'<a:ln w="{line_w}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill>{dx}</a:ln>'
              if line else '<a:ln><a:noFill/></a:ln>')
        body = ''.join(paras) if paras else '<a:p><a:endParaRPr lang="en-US"/></a:p>'
        p = in_(pad)
        self.shapes.append(f'''<p:sp>
  <p:nvSpPr><p:cNvPr id="{sid}" name="b{sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{in_(x)}" y="{in_(y)}"/><a:ext cx="{in_(w)}" cy="{in_(h)}"/></a:xfrm>
    <a:prstGeom prst="{geom}"><a:avLst>{adj}</a:avLst></a:prstGeom>{fx}{lx}</p:spPr>
  <p:txBody><a:bodyPr wrap="square" lIns="{p}" tIns="{p}" rIns="{p}" bIns="{p}" anchor="{anchor}"/><a:lstStyle/>{body}</p:txBody>
</p:sp>''')

    def arrow(self, x1, y1, x2, y2, color=CORAL, w=19050, dash=False):
        sid = self._id()
        cx, cy = x2 - x1, y2 - y1
        flipH = ' flipH="1"' if cx < 0 else ''
        flipV = ' flipV="1"' if cy < 0 else ''
        ax, ay = min(x1, x2), min(y1, y2)
        dx = '<a:prstDash val="dash"/>' if dash else ''
        self.shapes.append(f'''<p:cxnSp>
  <p:nvCxnSpPr><p:cNvPr id="{sid}" name="a{sid}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
  <p:spPr><a:xfrm{flipH}{flipV}><a:off x="{in_(ax)}" y="{in_(ay)}"/><a:ext cx="{in_(abs(cx))}" cy="{in_(abs(cy))}"/></a:xfrm>
    <a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>
    <a:ln w="{w}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{dx}<a:headEnd type="none"/><a:tailEnd type="triangle" w="med" len="med"/></a:ln></p:spPr>
</p:cxnSp>''')

    def line(self, x1, y1, x2, y2, color=DIV, w=9525):
        sid = self._id()
        self.shapes.append(f'''<p:cxnSp>
  <p:nvCxnSpPr><p:cNvPr id="{sid}" name="l{sid}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
  <p:spPr><a:xfrm><a:off x="{in_(x1)}" y="{in_(y1)}"/><a:ext cx="{in_(x2-x1)}" cy="{in_(y2-y1)}"/></a:xfrm>
    <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
    <a:ln w="{w}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln></p:spPr>
</p:cxnSp>''')

    def header(self, eyebrow, title, subtitle=None, title_sz=36):
        self.text(M, 0.42, CW, 0.3, [P(R(eyebrow, 11, LAVA, bold=True, spc=50))])
        self.text(M, 0.72, CW, 0.75, [P(R(title, title_sz, TEAL, bold=True), line=95000)])
        if subtitle:
            self.text(M, 1.42, CW, 0.5, [P(R(subtitle, 14, SUB), line=115000)])

    def footer(self, n, note=None):
        self.line(M, 7.02, 13.333 - M, 7.02)
        self.text(M, 7.1, 9.5, 0.25, [P(R(note or "Brand Performance Manager  ·  Built on the Databricks Data Intelligence Platform", 9, SUB))])
        self.text(13.333 - M - 1.0, 7.1, 1.0, 0.25, [P(R(str(n), 9, SUB), align="r")])

    def xml(self):
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{CREAM}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
{''.join(self.shapes)}
</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'''


def lbl(text, color=LAVA, sz=9.5, after=3):
    """Small-caps style red label."""
    return P(R(text.upper(), sz, color, bold=True, spc=60), after=after)


def card(s, x, y, w, h, label, value, body=None, dark=False, value_sz=26, body_sz=11, anchor="t"):
    fill, line = (TEAL, None) if dark else (WHITE, DIV)
    vcol, bcol, lcol = (WHITE, LTEAL, CORAL) if dark else (TEAL, BODY, LAVA)
    paras = [lbl(label, lcol, after=4), P(R(value, value_sz, vcol, bold=True), after=4, line=95000)]
    if body:
        for b in (body if isinstance(body, list) else [body]):
            paras.append(P(R(b, body_sz, bcol), after=3, line=112000))
    s.box(x, y, w, h, fill=fill, line=line, paras=paras, anchor=anchor)


slides, NOTES = [], []

# ═════════════════════════════════════════════════════════════════════════════
# 1 · OUTCOME — lead with the business problem and the value
# ═════════════════════════════════════════════════════════════════════════════
s = Slide()
s.header("NovaLife Nutrition  ·  Brand Performance Manager",
         "Brand insight in 90 seconds, not 3 days",
         None, title_sz=44)
s.text(M, 1.6, 11.4, 1.0, [P([
    R("CPG commercial teams wait ", 15, BODY),
    R("2–3 days", 15, TEAL, bold=True),
    R(" for an analyst to answer a share question from fragmented syndicated data, and spot insurgent "
      "brands ", 15, BODY),
    R("2–3 weeks late", 15, TEAL, bold=True),
    R(". Brand Performance Manager lets a brand manager ask in plain English, confirm how it will be "
      "answered, and get a governed, charted answer from one Databricks platform.", 15, BODY)],
    line=125000)])

cy, ch, gap = 3.05, 2.35, 0.22
cw = (CW - 3 * gap) / 4
card(s, M + 0 * (cw + gap), cy, cw, ch, "Time to insight", "3 days → <90 s",
     ["Analyst request replaced by a self-serve question (p90 target)."], value_sz=24)
card(s, M + 1 * (cw + gap), cy, cw, ch, "Analyst time returned", "~5,800 hrs / yr",
     ["≈ 3 FTE of report-pulling redirected to higher-value analysis (est.)."], value_sz=24)
card(s, M + 2 * (cw + gap), cy, cw, ch, "Capacity value", "≈ $0.5M / yr",
     ["5,760 hrs × $85/hr loaded analyst cost (est.)."], value_sz=24)
card(s, M + 3 * (cw + gap), cy, cw, ch, "Revenue protected", "$2M / yr",
     ["per 0.1 ppt of share defended in a $2B category by reacting to insurgents weeks earlier (illustrative)."],
     dark=True, value_sz=24)

s.text(M, 5.7, CW, 1.1, [
    lbl("How it gets there", after=5),
    P([R("One question, end to end:  ", 12, TEAL, bold=True),
       R("“Why did our share drop at Walmart over the last 4 weeks?”  →  Gen AI enriches & classifies  →  "
         "user confirms the route (logged to Lakebase)  →  Agent Bricks supervisor dispatches to a Genie agent  →  "
         "governed SQL on Lakeflow-ingested Unity Catalog tables  →  answer + chart in a Databricks App.", 12, BODY)], line=118000)])
s.footer(len(slides) + 1, "Estimates — assumptions on the next slide. Demo runs on synthetic CPG data.")
slides.append(s.xml())
NOTES.append(
    "Lead with the outcome.\n\n"
    "• Problem: share questions take analysts 2–3 days; insurgent threats are spotted 2–3 weeks late.\n"
    "• Outcome: a brand manager self-serves the answer in under 90 seconds, with a human confirmation step.\n"
    "• Headline numbers are estimates — the next slide shows the assumptions so they can be challenged.\n"
    "• The bottom line traces one real question through the whole platform — this is one integrated "
    "journey, not stitched demos.")

# ═════════════════════════════════════════════════════════════════════════════
# 2 · VALUE CASE — quantified with explicit assumptions
# ═════════════════════════════════════════════════════════════════════════════
s = Slide()
s.header("The value  ·  Quantified",
         "Where the value comes from",
         "Three problems with today's syndicated-data workflow, and an estimate of what solving them is worth.")

# Left: problem → impact → BPM answer
lx, lw = M, 6.55
rows = [
    ("Data fragmentation", "Topline, insurgent and distribution data sit in separate feeds",
     "2–3 days per insight", "One governed query layer: 5 Delta tables in Unity Catalog"),
    ("Insight latency", "Weekly reporting cadence",
     "Threats seen 2–3 wks late", "Ask any time; insurgent tracking on demand"),
    ("Expert dependency", "Only senior analysts know which SQL to run",
     "Doesn't scale", "Genie agents write the SQL; supervisor picks the agent"),
]
s.text(lx, 2.12, 1.9, 0.25, [lbl("Problem")])
s.text(lx + 2.0, 2.12, 1.9, 0.25, [lbl("Impact today")])
s.text(lx + 3.95, 2.12, 2.6, 0.25, [lbl("With BPM")])
ry, rh = 2.45, 1.38
for k, (prob, why, impact, fix) in enumerate(rows):
    y = ry + k * (rh + 0.12)
    s.box(lx, y, lw, rh, paras=[], anchor="t")
    s.text(lx + 0.18, y + 0.16, 1.75, rh - 0.3, [P(R(prob, 13, TEAL, bold=True), after=3, line=100000),
                                                P(R(why, 10, SUB), line=110000)])
    s.text(lx + 2.0, y + 0.16, 1.85, rh - 0.3, [P(R(impact, 13, LAVA, bold=True), line=105000)])
    s.text(lx + 3.95, y + 0.16, 2.45, rh - 0.3, [P(R(fix, 11, BODY), line=112000)])

# Right: value model (dark accent card)
rx, rw = M + lw + 0.3, CW - lw - 0.3
s.box(rx, 2.12, rw, 4.66, fill=TEAL, line=None, pad=0.26, paras=[
    lbl("Value model  ·  estimated", CORAL, after=8),
    P(R("Analyst capacity", 14, WHITE, bold=True), after=4),
    P(R("10 analysts × 3 requests / wk × 4 hrs hands-on", 11, LTEAL), after=1, line=112000),
    P(R("= 120 hrs / wk × 48 wks = 5,760 hrs / yr (≈ 3 FTE)", 11, LTEAL), after=1, line=112000),
    P([R("× $85 / hr loaded  →  ", 11, LTEAL), R("≈ $490K / yr", 13, WHITE, bold=True)], after=12),
    P(R("Revenue protected", 14, WHITE, bold=True), after=4),
    P(R("Insurgents spotted 2–3 weeks earlier → faster price / promo / distribution response.", 11, LTEAL),
      after=1, line=112000),
    P([R("0.1 ppt of share in a $2B category  →  ", 11, LTEAL), R("$2M / yr", 13, WHITE, bold=True)], after=12),
    P(R("Validate with the customer's analyst headcount, request volume and category size — every "
        "input above is a lever.", 10, LTEAL, italic=True), line=112000),
])
s.footer(len(slides) + 1, "Problem statement and targets from the BPM PRD; dollar figures are estimates, not measured savings.")
slides.append(s.xml())
NOTES.append(
    "Quantify the value — and show the working.\n\n"
    "• Capacity: 10 analysts × 3 requests/week × 4 hours = 120 hrs/week → 5,760 hrs/yr ≈ 3 FTE → ≈ $490K at $85/hr.\n"
    "• Revenue: in a $2B category every 0.1 ppt of share is $2M/yr. Catching an insurgent 2–3 weeks earlier "
    "is how you defend it.\n"
    "• These are estimates. Swap in the customer's headcount and category size live if asked.")

# ═════════════════════════════════════════════════════════════════════════════
# 3 · WHAT YOU'LL SEE — the "tell" before the live demo
# ═════════════════════════════════════════════════════════════════════════════
s = Slide()
s.header("Live demo  ·  What you'll see",
         "Three moments, three KPIs",
         "NovaLife Nutrition's Monday morning: NovaBaby share slipped at Walmart. Here's how the brand team gets the answer.")
moments = [
    ("1 · Ask", "“Why did NovaBaby share drop at Walmart?”",
     ["Plain English, no analyst ticket", "Answer: 34.0% → 33.0% in 4 weeks; distribution is the #1 driver"],
     "KPI · time to insight", "3 days → <90 s", False),
    ("2 · Confirm", "The brand manager approves the route",
     ["App proposes Topline analysis and shows why", "Every decision is logged in Lakebase"],
     "KPI · trust & adoption", ">80% confirm first time", True),
    ("3 · Act", "Spot the insurgent before it hurts",
     ["Happy Roots: +2.4 ppt share in 52 weeks", "Distribution gaps: SKU at 26% ACV in the Northeast"],
     "KPI · revenue protected", "weeks earlier", False),
]
mw = (CW - 2 * 0.25) / 3
for k, (lab, head, body, kl, kv, dark) in enumerate(moments):
    x = M + k * (mw + 0.25)
    fill, line = (TEAL, None) if dark else (WHITE, DIV)
    hc, bc, lc = (WHITE, LTEAL, CORAL) if dark else (TEAL, BODY, LAVA)
    s.box(x, 2.15, mw, 3.4, fill=fill, line=line, pad=0.22, paras=[
        lbl(lab, lc, after=6),
        P(R(head, 17, hc, bold=True), after=10, line=100000),
        *[P(R(b, 11.5, bc), bullet=True, after=4, line=112000) for b in body]])
    s.line(x + 0.22, 4.55, x + mw - 0.22, 4.55, color=SUB if dark else DIV)
    s.text(x + 0.22, 4.66, mw - 0.44, 0.8, [lbl(kl, lc, after=2), P(R(kv, 18, hc, bold=True))])
    if k < 2:
        s.arrow(x + mw + 0.03, 3.85, x + mw + 0.22, 3.85)
s.box(M, 5.8, CW, 0.95, fill=None, line=DIV, anchor="ctr", pad=0.2, paras=[P([
    R("WHY IT MATTERS  ", 9.5, LAVA, bold=True, spc=60),
    R("On this data, one point of NovaBaby Infant Formula share at Walmart is worth ≈ $80M a year. Knowing ", 13, BODY),
    R("why", 13, TEAL, bold=True),
    R(" on Monday, not Thursday, is the product.", 13, BODY)], line=115000)])
s.footer(len(slides) + 1, "Demo data is synthetic. Figures are what the live app returns.")
slides.append(s.xml())
NOTES.append("")

# ═════════════════════════════════════════════════════════════════════════════
# 3 · END-TO-END JOURNEY — one integrated data flow
# ═════════════════════════════════════════════════════════════════════════════
s = Slide()
s.header("The journey  ·  End to end",
         "One integrated flow, raw data to business app",
         "Every stage is a native Databricks service and every hop is governed by Unity Catalog — not stitched-together demos.")

stages = [
    ("1 · Raw data", "CSV drops", ["Synthetic Nielsen/Circana-style, 104 weeks", "landed in a UC volume"], False),
    ("2 · Lakeflow", "Declarative pipeline", ["Auto Loader → 5 streaming tables", "data-quality expectations"], False),
    ("3 · Govern", "Unity Catalog", ["5 tables · 172,640 rows", "grants scoped to the app's SP"], False),
    ("4 · Gen AI", "Intake function", ["ai_extract + ai_classify", "brand · retailer · window · intent"], False),
    ("5 · Agents", "Genie + Agent Bricks", ["4 Genie spaces · 2 supervisors", "3 routes, one dispatch"], True),
    ("6 · App", "Databricks App", ["React + FastAPI", "HITL gate · Plotly charts"], False),
    ("7 · Lakebase", "Decision log", ["every gate decision in Postgres", "registered back in UC"], False),
]
n = len(stages); gap = 0.2
sw = (CW - (n - 1) * gap) / n
sy, sh = 2.25, 2.35
for k, (lab, val, body, dark) in enumerate(stages):
    x = M + k * (sw + gap)
    card(s, x, sy, sw, sh, lab, val, body, dark=dark, value_sz=14, body_sz=9.5)
    if k < n - 1:
        s.arrow(x + sw + 0.03, sy + sh / 2, x + sw + gap - 0.03, sy + sh / 2)

# Trace row — the same question through each stage
s.text(M, 4.85, CW, 0.3, [lbl("One question, traced through every stage")])
s.box(M, 5.18, CW, 0.9, paras=[P([
    R("“Why did our share drop at Walmart over the last 4 weeks?”   ", 12, TEAL, bold=True),
    R("Phase 1: enrich_user_request → {brand, retailer=Walmart, window=4w, type=topline}  →  app proposes "
      "ROUTE=topline  →  user confirms  →  Phase 2: one supervisor call  →  Topline agent queries Genie over "
      "brand_topline_metrics + market_share_decomposition  →  answer + deterministic chart  →  decision row "
      "written to Lakebase (confirmed vs. overridden).", 11, BODY)],
    line=115000)], anchor="ctr")

# Optional / next
s.box(M, 6.24, CW, 0.6, fill=None, line=SUB, dash=True, anchor="ctr", pad=0.14, paras=[P([
    R("NEXT  ", 9.5, LAVA, bold=True, spc=60),
    R("Point Lakeflow at live syndicated feeds  ·  Lakebase synced tables for sub-second KPI tiles  ·  "
      "Knowledge Assistant over methodology PDFs", 11, SUB)])])
s.footer(len(slides) + 1)
slides.append(s.xml())
NOTES.append(
    "Show the journey as one system.\n\n"
    "• Left to right: synthetic raw data → Delta → Unity Catalog → Gen AI intake (ai_extract/ai_classify) → "
    "Genie agents behind an Agent Bricks supervisor → a Databricks App.\n"
    "• The trace row is the proof of integration: the same question touches every stage.\n"
    "• Lakeflow: raw CSV drops in a UC volume are ingested incrementally by Auto Loader into the exact tables "
    "Genie reads, with data-quality expectations.\n"
    "• Lakebase: every human-in-the-loop decision is written to Postgres and the database is registered in Unity "
    "Catalog, so the confirmation-rate metric is queryable with SQL alongside everything else.")

# ═════════════════════════════════════════════════════════════════════════════
# 4 · REFERENCE ARCHITECTURE — service-labeled swimlanes
# ═════════════════════════════════════════════════════════════════════════════
s = Slide()
s.header("Architecture  ·  Services & request flow",
         "Reference architecture",
         "One question flows top to bottom. Every box is a native Databricks service — no external infrastructure.")


def lane(y, h, label, nodes, dark_idx=None):
    s.box(M, y, CW, h, fill=WHITE, line=DIV, pad=0.12, paras=[lbl(label, sz=9)])
    n = len(nodes); pad, g = 0.16, 0.16
    nw = (CW - 2 * pad - (n - 1) * g) / n
    for k, (badge, title, desc) in enumerate(nodes):
        x = M + pad + k * (nw + g)
        dark = (k == dark_idx)
        fill, line = (TEAL, None) if dark else (CREAM, DIV)
        s.box(x, y + 0.36, nw, h - 0.48, fill=fill, line=line, pad=0.1, anchor="ctr", paras=[
            P(R(badge, 8, CORAL if dark else LAVA, bold=True, spc=40), align="ctr", after=2),
            P(R(title, 12, WHITE if dark else TEAL, bold=True), align="ctr", after=1),
            P(R(desc, 9.5, LTEAL if dark else SUB), align="ctr", line=105000)])


lane(2.0, 0.95, "User", [("BROWSER", "Brand manager · VP Commercial · Category analyst",
                          "asks a plain-English brand question")])
s.arrow(6.667, 2.97, 6.667, 3.13)
lane(3.15, 1.25, "Orchestration  ·  Databricks Apps (React + FastAPI)", [
    ("① UC FUNCTION + GEN AI", "Enrich & classify", "ai_extract + ai_classify via SQL warehouse"),
    ("② APP-OWNED HITL GATE", "Confirm the route", "Confirm · change route · cancel"),
    ("③ AGENT SERVING CALL", "Execute", "one call carrying ROUTE= to the supervisor"),
    ("④ STATEMENT EXECUTION API", "Render", "deterministic Plotly chart from SQL")], dark_idx=1)
s.arrow(6.667, 4.42, 6.667, 4.58)
lane(4.6, 1.15, "Agent layer  ·  Mosaic AI Agent Bricks — multi-agent supervisor dispatches on ROUTE=", [
    ("AGENT BRICKS SUB-SUPERVISOR", "Topline agent", "Brand Analysis + Topline Genie spaces"),
    ("AI/BI GENIE SPACE", "Insurgent brands", "challenger share gain, velocity, threat score"),
    ("AI/BI GENIE SPACE", "Distribution & velocity", "ACV gaps, SKU velocity, out-of-stock")])
s.arrow(6.667, 5.77, 6.667, 5.93)
lane(5.95, 1.0, "Data, governance & observability  ·  Unity Catalog", [
    ("LAKEFLOW", "Ingest pipeline", "Auto Loader + expectations"),
    ("DELTA LAKE", "5 governed tables", "172,640 rows · 104 weeks"),
    ("DATABRICKS SQL", "Serverless warehouse", "intake, KPI tiles, charts"),
    ("LAKEBASE", "HITL decision log", "Postgres, registered in UC"),
    ("OPENTELEMETRY → UC", "App telemetry", "latency + agent-call timings")])
s.footer(len(slides) + 1)
slides.append(s.xml())
NOTES.append(
    "Walk top to bottom, naming each product.\n\n"
    "• The Databricks App runs a two-phase flow: ① enrich/classify with a UC function using ai_extract and "
    "ai_classify, ② the human confirms the route in the app (dark card — the key design choice), "
    "③ one serving call carrying ROUTE=, ④ a deterministic chart from SQL.\n"
    "• Agent Bricks: one supervisor dispatches to exactly one specialist; topline is itself a sub-supervisor "
    "over two Genie spaces.\n"
    "• Everything sits on Unity Catalog: Lakeflow feeds the Delta tables, Lakebase holds the decision log, and app "
    "telemetry lands via OpenTelemetry.")

# ═════════════════════════════════════════════════════════════════════════════
# 5 · DECISIONS & TRADE-OFFS
# ═════════════════════════════════════════════════════════════════════════════
s = Slide()
s.header("Design  ·  Decisions & trade-offs",
         "Why this approach, and not another",
         "The first design was 4 nested supervisors and a polling loop. Simplifying it is what made it work.")
cols = [("Decision", 2.05), ("We chose", 2.75), ("Instead of", 2.55), ("Why", CW - 2.05 - 2.75 - 2.55)]
rows = [
    ("Human-in-the-loop", "App-owned two-phase gate: propose → confirm → run",
     "Router agent pausing on a Lakebase row + polling",
     "A deployed supervisor endpoint is synchronous and can't pause for a human. The app owning the gate makes resume real."),
    ("Agent topology", "2 supervisors, 0 custom serving endpoints",
     "4 nested supervisors + 2 custom endpoints",
     "Fewer hops = lower latency and fewer failure points. Intake moved out of the agent layer."),
    ("Request intake", "UC SQL function with ai_extract + ai_classify",
     "An LLM intake agent",
     "Deterministic, governed, one warehouse round-trip, unit-testable."),
    ("Charts", "Deterministic Plotly built from SQL",
     "LLM visualization adapter emitting Plotly JSON",
     "Removes a model call and malformed-JSON risk; supports the >95% render-success target."),
    ("Ingest", "Lakeflow pipeline: Auto Loader + expectations",
     "A notebook overwriting Delta tables",
     "Weekly drops load incrementally, data quality shows in the event log, and lineage runs file → table."),
    ("Lakebase", "Decision log, written after the response is sent",
     "Lakebase as the pause/resume state store",
     "Transactional writes without adding latency; registered in UC so the confirmation rate is just SQL."),
]
x0, ty = M, 2.1
xs = []
x = x0
for name, w in cols:
    xs.append((x, w)); x += w
for (name, w), (x, _) in zip(cols, xs):
    s.text(x + 0.14, ty, w - 0.2, 0.25, [lbl(name)])
rh = 0.72; y = ty + 0.32
for k, row in enumerate(rows):
    yy = y + k * (rh + 0.06)
    s.box(M, yy, CW, rh, fill=WHITE, line=DIV, paras=[])
    for c, ((x, w), val) in enumerate(zip(xs, row)):
        col, b, sz = [(TEAL, True, 12), (TEAL, False, 10.5), (SUB, False, 10.5), (BODY, False, 10)][c]
        s.text(x + 0.14, yy + 0.06, w - 0.24, rh - 0.12, [P(R(val, sz, col, bold=b), line=108000)], anchor="ctr")
s.footer(len(slides) + 1)
slides.append(s.xml())
NOTES.append(
    "Document the trade-offs.\n\n"
    "• Biggest lesson: the original 'agent writes PENDING to Lakebase, app polls, agent resumes' design dead-ended "
    "— a deployed supervisor can't pause mid-request. Moving the gate into the app fixed it.\n"
    "• Net simplification: supervisors 4 → 2, custom serving endpoints 2 → 0.\n"
    "• Lakebase is deliberately off the critical path: if it is suspended or unreachable the analysis still runs.")

# ═════════════════════════════════════════════════════════════════════════════
# 6 · AI AS A FORCE MULTIPLIER
# ═════════════════════════════════════════════════════════════════════════════
s = Slide()
s.header("How it was built  ·  AI as a teammate",
         "Built with AI as a force multiplier",
         "Claude Code plus the Databricks AI Dev Kit took the work from spec to a deployed, verified app.")

c3 = (CW - 2 * 0.22) / 3
yy, hh = 2.1, 2.75
s.box(M, yy, c3, hh, paras=[
    lbl("Tools", after=6),
    P(R("Claude Code", 13, TEAL, bold=True), after=1), P(R("agentic coding, deploys and debugging in the terminal", 10.5, BODY), after=6, line=110000),
    P(R("Databricks AI Dev Kit", 13, TEAL, bold=True), after=1), P(R("MCP tools + skills for Genie, Agent Bricks, UC and Apps", 10.5, BODY), after=6, line=110000),
    P(R("Databricks CLI + REST", 13, TEAL, bold=True), after=1), P(R("bundle / apps deploy, grants, supervisor API", 10.5, BODY), line=110000)])
s.box(M + c3 + 0.22, yy, c3, hh, paras=[
    lbl("Patterns", after=6),
    P(R("Spec first: PRD → SDD → SPECS, then code", 11, BODY), bullet=True, after=4, line=110000),
    P(R("AI-generated synthetic data + methodology PDFs", 11, BODY), bullet=True, after=4, line=110000),
    P(R("Deploy → verify → fix loop against the live workspace", 11, BODY), bullet=True, after=4, line=110000),
    P(R("AI keeps the runbook (DEPLOY_STATUS.md) current", 11, BODY), bullet=True, line=110000)])
s.box(M + 2 * (c3 + 0.22), yy, c3, hh, fill=TEAL, line=None, paras=[
    lbl("Prompts that did real work", CORAL, after=6),
    P(R("“deploy brand performance manager to databricks workspace”", 11.5, WHITE, bold=True), after=2, line=110000),
    P(R("→ found app + both supervisors deleted, rebuilt them, re-applied 6 grants, deployed, verified", 10, LTEAL), after=8, line=110000),
    P(R("“what's lakebase used for?”", 11.5, WHITE, bold=True), after=2, line=110000),
    P(R("→ surfaced spec-vs-code drift (unused dependency, stale binding)", 10, LTEAL), line=110000)])

# Numbers row
s.text(M, 5.08, CW, 0.3, [lbl("What AI caught or produced")])
stats = [("3", "platform bugs found", "ai_extract / ai_classify signatures, Responses API shape, missing sub-agent grant"),
         ("24", "unit tests", "HITL flow, routing, UC functions, visualization"),
         ("172,640", "synthetic rows", "5 tables, 104 weeks, generated from spec"),
         ("1 prompt", "full redeploy", "app + 2 supervisors + grants, end-to-end verified")]
sw4 = (CW - 3 * 0.22) / 4
for k, (v, l, d) in enumerate(stats):
    x = M + k * (sw4 + 0.22)
    s.box(x, 5.4, sw4, 1.45, pad=0.14, paras=[
        P([R(v, 22, TEAL, bold=True), R("  " + l, 11, LAVA, bold=True)], after=3),
        P(R(d, 10, SUB), line=108000)])
s.footer(len(slides) + 1)
slides.append(s.xml())
NOTES.append(
    "Use AI as a force multiplier — and show it.\n\n"
    "• Tools: Claude Code driving the Databricks AI Dev Kit (MCP tools + skills) and the Databricks CLI.\n"
    "• Pattern: write the PRD/SDD/SPECS first, let the agent build against them, then run deploy-verify-fix loops "
    "against the live workspace.\n"
    "• Real example: one prompt ('deploy brand performance manager…') found the app and supervisors deleted, "
    "rebuilt both supervisors, recreated the app, re-applied grants including the easy-to-miss sub-agent grant, "
    "and verified an answer end to end.")

# ═════════════════════════════════════════════════════════════════════════════
# CLOSE · What this means + proposed next step
# ═════════════════════════════════════════════════════════════════════════════
s = Slide()
s.header("Next step  ·  What this means for NovaLife",
         "Prove it on one category in six weeks",
         "Same platform, your data: point Lakeflow at the real Circana feed and measure against the PRD targets.")
c3 = (CW - 2 * 0.22) / 3
for k, (lab, val, body, dark) in enumerate([
    ("Outcome", "Answers in <90 s", ["Brand managers self-serve share questions instead of queuing for analysts."], False),
    ("Value", "≈ $0.5M + $2M / yr", ["Analyst capacity returned, plus share defended by reacting to insurgents weeks earlier."], True),
    ("Risk", "Governed by design", ["Unity Catalog permissions end to end; a human approves every route; every decision audited."], False)]):
    card(s, M + k * (c3 + 0.22), 2.15, c3, 1.9, lab, val, body, dark=dark, value_sz=22, body_sz=11.5)

s.text(M, 4.32, CW, 0.3, [lbl("6-week pilot  ·  success criteria agreed up front")])
crit = [("< 90 s", "p90 time to answer"), ("> 90%", "routing accuracy"),
        ("> 80%", "HITL confirmation rate (Lakebase)"), ("> 20", "sessions / week")]
cw4 = (CW - 3 * 0.22) / 4
for k, (v, l) in enumerate(crit):
    x = M + k * (cw4 + 0.22)
    s.box(x, 4.65, cw4, 1.05, pad=0.16, anchor="ctr", paras=[P(R(v, 22, TEAL, bold=True), after=2), P(R(l, 11, SUB))])
s.box(M, 5.92, CW, 0.88, fill=TEAL, line=None, anchor="ctr", pad=0.22, paras=[P([
    R("THE ASK  ", 9.5, CORAL, bold=True, spc=60),
    R("Pick the pilot category, grant read access to its syndicated feed, and name one brand team as design "
      "partner. We stand it up in your workspace in week one.", 13, WHITE)], line=112000)])
s.footer(len(slides) + 1)
slides.append(s.xml())
NOTES.append("")

# ═════════════════════════════════════════════════════════════════════════════
# 7 · APPENDIX — Databricks services
# ═════════════════════════════════════════════════════════════════════════════
s = Slide()
s.header("Appendix  ·  What's used", "Databricks services in this implementation", None)
rows = [
    ("Databricks Apps", "Hosts the React UI + FastAPI backend; owns the two-phase HITL flow — one governed deployable."),
    ("Mosaic AI Agent Bricks — supervisor", "Reads ROUTE= and dispatches the pre-confirmed request to exactly one specialist."),
    ("Agent Bricks — Topline sub-supervisor", "Orchestrates the Brand Analysis and Topline Performance Genie spaces."),
    ("AI/BI Genie spaces (×4)", "Natural-language-to-SQL over Delta: brand, topline, insurgent brands, distribution."),
    ("UC Functions + AI Functions", "enrich_user_request: SQL function using ai_extract / ai_classify for deterministic intake."),
    ("Delta Lake + Databricks SQL", "5 governed tables (172,640 rows, 104 weeks); serverless warehouse via Statement Execution API."),
    ("Unity Catalog", "One permission + lineage boundary across tables, functions, agents and app telemetry."),
    ("Lakeflow Declarative Pipelines", "Auto Loader ingests raw CSV drops from a UC volume into the 5 tables, with expectations."),
    ("Lakebase (Postgres)", "HITL decision log for the confirmation-rate metric; registered in Unity Catalog."),
    ("Knowledge Assistant · synced tables", "Next: RAG over methodology PDFs; Lakebase synced tables for KPI tiles."),
]
y0 = 1.75; rh = 0.46
s.text(M + 0.18, y0 - 0.32, 4.0, 0.25, [lbl("Databricks service")])
s.text(M + 4.5, y0 - 0.32, 7.0, 0.25, [lbl("Role in the solution")])
for k, (a, b) in enumerate(rows):
    y = y0 + k * (rh + 0.04)
    last = k == len(rows) - 1
    assert y + rh < 7.0, 'appendix overflows'
    s.box(M, y, CW, rh, fill=None if last else WHITE, line=SUB if last else DIV, dash=last, paras=[])
    s.text(M + 0.18, y, 4.2, rh, [P(R(a, 12, SUB if last else TEAL, bold=True))], anchor="ctr")
    s.text(M + 4.5, y, CW - 4.7, rh, [P(R(b, 11, SUB if last else BODY), line=108000)], anchor="ctr")
s.footer(len(slides) + 1)
slides.append(s.xml())
NOTES.append("Appendix — use for follow-up questions; don't read every row. The dashed row is the roadmap.")

# ── Speaker notes: role-play talk track (tell → show → tell) ────────────────
# Overrides the per-slide notes above. Timings target a ~25-minute session.
NOTES = [
# 1 · Outcome
"[0:00–2:00 · DEMO SETUP — frame customer, problem, what you'll show]\n\n"
"SAY: \"Thanks both. Before I show anything, let me frame why we're here. NovaLife Nutrition's brand teams make "
"share decisions every Monday, but the answer to 'why did NovaBaby slip at Walmart?' takes an analyst two to "
"three days, and insurgent brands like Happy Roots show up in the weekly deck two to three weeks after they "
"started taking share.\"\n\n"
"SAY: \"In the next 20 minutes I'll do three things: show you the value case in numbers, show you the app "
"answering that exact question live, and then walk your architect through how it's built and governed.\"\n\n"
"CHECK IN (exec): \"Does that match what you're seeing, or is there a sharper version of the problem I should "
"be solving?\"  Let them answer; reuse their words for the rest of the session.",

# 2 · Value
"[2:00–5:00 · VALUE — executive altitude, their KPIs]\n\n"
"SAY: \"Two sources of value. First, capacity: ten analysts doing three requests a week at four hours each is "
"about 5,800 hours a year, roughly three people, about half a million dollars, redirected from pulling numbers "
"to acting on them.\"\n\n"
"SAY: \"Second, and bigger: revenue. In a two-billion-dollar category every tenth of a point of share is two "
"million dollars a year. Reacting to an insurgent weeks earlier is how you keep it.\"\n\n"
"SAY: \"These are estimates. Every input is on the slide so we can swap in your numbers. What's your analyst "
"headcount on this category?\"\n\n"
"IF CHALLENGED ON THE NUMBERS: agree they're assumptions, offer to halve them (\"even at half, it pays for "
"itself\"), and propose measuring them in the pilot.",

# 3 · What you'll see
"[5:00–6:00 · TELL — what the demo will prove]\n\n"
"SAY: \"Here's what you're about to see: three moments, and the KPI each one moves. One, a brand manager asks "
"the Monday question in plain English. Time to insight. Two, they approve how it's answered before anything "
"runs. Trust and adoption. Three, they spot the insurgent and the distribution gap. Revenue protected.\"\n\n"
"SAY: \"Keep one number in mind: on this data, one point of NovaBaby share at Walmart is worth about eighty "
"million dollars a year.\"\n\n"
"→ SWITCH TO THE APP (pre-opened, AI Advisor tab). Full click path in ROLEPLAY_SCRIPT.md.",

# 4 · Journey
"[13:00–15:00 · TELL (land) + bridge to technical]\n\n"
"LAND FOR EXEC: \"So what you just saw: the question went from three days to under ninety seconds, a human "
"approved the route, and the decision was logged. That's the outcome. Now let me show your architect why "
"it's trustworthy.\"\n\n"
"FOR ARCHITECT: \"It's one flow, not stitched demos. Raw CSV drops land in a Unity Catalog volume. A Lakeflow "
"pipeline ingests them incrementally with Auto Loader into five governed tables, with data-quality "
"expectations. A UC function uses ai_extract and ai_classify to understand the question. Genie agents behind "
"an Agent Bricks supervisor write the SQL. The Databricks App renders it, and every human decision goes to "
"Lakebase, which is registered back in Unity Catalog.\"\n\n"
"KEEP THE EXEC: end with \"In business terms: one platform, one set of permissions, nothing to stitch together.\"",

# 5 · Architecture
"[15:00–17:00 · TECHNICAL DEPTH — aim at the architect]\n\n"
"Walk top to bottom, about 20 seconds per layer:\n"
"• App: two-phase flow. Phase 1 enriches and classifies; the app owns the human gate; Phase 2 is ONE "
"supervisor call carrying ROUTE=.\n"
"• Agents: the supervisor dispatches to exactly one specialist. Topline is itself a sub-supervisor over two "
"Genie spaces.\n"
"• Data: Lakeflow → Delta → serverless SQL; Lakebase for the decision log; OpenTelemetry metrics land in UC.\n\n"
"IDENTITY (likely question): the app calls the warehouse and agents as its own service principal with "
"least-privilege UC grants. Lakebase uses a short-lived OAuth credential, so no stored passwords.",

# 6 · Trade-offs
"[17:00–19:00 · DECISIONS — shows judgment]\n\n"
"SAY: \"The first design had four nested supervisors and an agent that paused on a Lakebase row while the "
"app polled. It dead-ended, because a deployed supervisor endpoint is synchronous and can't wait for a "
"human. So we moved the gate into the app and cut it to two supervisors and zero custom endpoints.\"\n\n"
"Pick 2–3 rows based on what the architect has asked about. Don't read all six.\n\n"
"FOR EXEC (one line): \"Every simplification here means fewer things that break and a faster answer.\"",

# 7 · Built with AI
"[19:00–20:00 · AI AS A FORCE MULTIPLIER — keep it short]\n\n"
"SAY: \"I built this with Claude Code and the Databricks AI Dev Kit as a teammate: specs first, then the "
"agent builds, deploys and verifies against the live workspace. When the endpoints were deleted, one prompt "
"rebuilt and re-verified everything, including the easy-to-miss permission grant.\"\n\n"
"FOR EXEC: \"The same approach is how your team would extend this to the next category in weeks, not quarters.\"",

# 8 · Close
"[20:00–22:00 · TELL (land) + ASK]\n\n"
"SAY: \"Let me bring it back to NovaLife. Outcome: answers in under ninety seconds. Value: about half a "
"million in capacity, and two million for every tenth of a point you defend. Risk: governed end to end, "
"with a human approving every route.\"\n\n"
"ASK: \"I'd propose a six-week pilot on one category with these four success criteria agreed today. "
"Which category would you pick, and who on your side owns the Circana feed?\"\n\n"
"Then stop talking. Leave the remaining time for questions.",

# 9 · Appendix
"[Q&A · reference only]\n\n"
"Use this slide only if asked \"what exactly does this use?\" Don't present it.\n"
"Dashed row = roadmap: Knowledge Assistant (RAG over methodology PDFs) and Lakebase synced tables for KPI tiles.",
]

assert len(NOTES) == len(slides), f"NOTES {len(NOTES)} != slides {len(slides)}"

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
 '<a:fontScheme name="Office"><a:majorFont><a:latin typeface="DM Sans"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
 '<a:minorFont><a:latin typeface="DM Sans"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
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

slide_master = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
 '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
 '<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="F9F7F4"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
 '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
 '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
 '</p:spTree></p:cSld>'
 '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
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
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
     '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
     f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide{n}.xml"/>'
     '</Relationships>')

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
