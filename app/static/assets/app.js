// Brand Performance Manager — React single-page app (no build step).
//
// Uses CDN React 18 (global `React`/`ReactDOM`), CDN Plotly (global `Plotly`), and
// `htm` for JSX-free templating. The canonical, type-checked source is in
// ../../frontend (Vite + TypeScript); this hand-authored bundle exists so the app
// deploys to Databricks Apps without a Node build (Apps cannot run `npm`).
//
// All data, the Phase-1 enrichment, the two-phase HITL gate, and the Phase-2
// supervisor call go through the FastAPI backend (server.py) over /api/*.

import htm from "https://unpkg.com/htm@3.1.1/dist/htm.module.js";

const { useState, useEffect, useRef, useCallback } = React;
const html = htm.bind(React.createElement);

const NAVY = "#003087";
const ORANGE = "#E87722";

// ── API client ────────────────────────────────────────────────────────────────

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
const api = {
  config: () => getJSON("/api/config"),
  kpis: () => getJSON("/api/kpis"),
  shareTrend: (brand, weeks = 52) =>
    getJSON(`/api/share-trend?brand=${encodeURIComponent(brand)}&weeks=${weeks}`),
  insurgents: (cat) => getJSON(`/api/insurgents?category=${encodeURIComponent(cat)}`),
  distribution: () => getJSON("/api/distribution"),
  refresh: () => postJSON("/api/refresh", {}),
  enrich: (question) => postJSON("/api/enrich", { question }),
  analyze: (question, route, ctx, sessionId, proposedRoute) =>
    postJSON("/api/analyze", { question, route, ctx, session_id: sessionId, proposed_route: proposedRoute }),
  // Lakebase audit log: gate outcomes that never reach Phase 2, and the confirmation rate.
  gateDecision: (decision, g) =>
    postJSON("/api/hitl/decision", {
      decision, question: g.question, proposed_route: g.proposedRoute, ctx: g.ctx, session_id: g.sessionId,
    }).catch(() => {}),
  hitlStats: () => getJSON("/api/hitl/stats"),
};

// ── Plotly chart component ──────────────────────────────────────────────────────

const PLOT_CONFIG = { displayModeBar: false, responsive: true };
const BASE_LAYOUT = {
  height: 340,
  margin: { l: 60, r: 24, t: 36, b: 48 },
  paper_bgcolor: "#FFFFFF",
  plot_bgcolor: "#FFFFFF",
  font: { family: "Inter, sans-serif", color: "#16213e", size: 12 },
  showlegend: false,
};

function Plot({ data, layout }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    Plotly.react(ref.current, data, { ...BASE_LAYOUT, ...layout }, PLOT_CONFIG);
    const el = ref.current;
    return () => Plotly.purge(el);
  }, [JSON.stringify(data), JSON.stringify(layout)]);
  return html`<div ref=${ref} style=${{ width: "100%" }}></div>`;
}

// Render a backend-produced ChartSpec (from chart_data()).
function SpecChart({ spec }) {
  let data;
  if (spec.kind === "line") {
    data = [
      {
        x: spec.x,
        y: spec.y,
        type: "scatter",
        mode: "lines+markers",
        line: { color: spec.color || NAVY, width: 2.5 },
        marker: { color: spec.color || NAVY, size: 6 },
      },
    ];
  } else {
    const horizontal = spec.orientation === "h";
    data = [
      {
        x: spec.x,
        y: spec.y,
        type: "bar",
        orientation: horizontal ? "h" : "v",
        marker: { color: spec.colors || spec.color || ORANGE },
        text: spec.x.map((v) => (typeof v === "number" ? `${v > 0 ? "+" : ""}${v}` : v)),
        textposition: "outside",
      },
    ];
  }
  const layout = {
    title: { text: spec.title, font: { size: 14, color: NAVY } },
    xaxis: { title: { text: spec.xTitle } },
    yaxis: { title: { text: spec.yTitle }, automargin: true },
  };
  if (spec.threshold != null) {
    layout.shapes = [
      { type: "line", x0: spec.threshold, x1: spec.threshold, yref: "paper", y0: 0, y1: 1,
        line: { color: "red", dash: "dash", width: 1.5 } },
    ];
    layout.annotations = [
      { x: spec.threshold, yref: "paper", y: 1, text: `${spec.threshold}% threshold`,
        showarrow: false, font: { size: 10, color: "red" }, xanchor: "left" },
    ];
  }
  return html`<${Plot} data=${data} layout=${layout} />`;
}

function MultiLineChart({ series, xTitle, yTitle }) {
  const palette = [NAVY, ORANGE, "#4f6db5", "#1a8f5b", "#9b59b6"];
  const data = series.map((s, i) => ({
    x: s.x, y: s.y, type: "scatter", mode: "lines+markers", name: s.name,
    line: { color: palette[i % palette.length], width: 2.5 }, marker: { size: 5 },
  }));
  const layout = {
    showlegend: true,
    legend: { orientation: "h", yanchor: "bottom", y: 1.04, x: 0 },
    xaxis: { title: { text: xTitle || "" } },
    yaxis: { title: { text: yTitle || "" }, automargin: true },
  };
  return html`<${Plot} data=${data} layout=${layout} />`;
}

function HBarChart({ labels, values, colors, xTitle, textFmt, threshold }) {
  const data = [
    {
      x: values, y: labels, type: "bar", orientation: "h",
      marker: { color: colors || ORANGE },
      text: textFmt ? values.map(textFmt) : undefined,
      textposition: "outside",
    },
  ];
  const layout = { xaxis: { title: { text: xTitle || "" } }, yaxis: { automargin: true } };
  if (threshold != null) {
    layout.shapes = [
      { type: "line", x0: threshold, x1: threshold, yref: "paper", y0: 0, y1: 1,
        line: { color: "red", dash: "dash", width: 1.5 } },
    ];
  }
  return html`<${Plot} data=${data} layout=${layout} />`;
}

// ── Shared bits ─────────────────────────────────────────────────────────────────

function ContextPills({ ctx }) {
  const pills = [];
  if (ctx.brand) pills.push(["Brand", ctx.brand, NAVY]);
  if (ctx.retailer) pills.push(["Retailer", ctx.retailer, "#555"]);
  if (ctx.time_window_weeks) pills.push(["Window", `${ctx.time_window_weeks}W`, ORANGE]);
  if (!pills.length) return null;
  return html`<div class="pills">
    ${pills.map(
      ([k, v, c]) => html`<span class="pill" style=${{ background: c }} key=${k}><b>${k}:</b> ${v}</span>`
    )}
  </div>`;
}

const Notice = ({ kind, children }) => html`<div class="notice ${kind}">${children}</div>`;
const Loading = ({ label }) => html`<div class="loading-row"><span class="spinner"></span> ${label}</div>`;

const num = (v) => (v == null ? 0 : Number(v));

// ── Dashboard ─────────────────────────────────────────────────────────────────

function Dashboard({ refreshKey }) {
  const [kpis, setKpis] = useState(null);
  const [kpiErr, setKpiErr] = useState(null);
  const [trend, setTrend] = useState([]);
  const [insurgents, setInsurgents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const k = await api.kpis();
        if (cancelled) return;
        setKpis(k.rows);
        setKpiErr(k.error);
        const top = k.rows.slice(0, 3).map((r) => r.brand);
        const series = await Promise.all(
          top.map(async (brand) => {
            const t = await api.shareTrend(brand, 52);
            return { name: brand, x: t.rows.map((r) => r.week_ending), y: t.rows.map((r) => num(r.value_share_pct)) };
          })
        );
        if (!cancelled) setTrend(series.filter((s) => s.y.length));
        const ins = await api.insurgents("Infant Formula");
        if (!cancelled) setInsurgents(ins.rows.map((r) => ({ brand: r.brand, gain: num(r.gain_52w) })));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [refreshKey]);

  if (loading && !kpis) return html`<${Loading} label="Loading dashboard…" />`;

  return html`<div>
    ${
      kpiErr
        ? html`<${Notice} kind="warn">⚠️ Could not load KPI data — ${kpiErr}</${Notice}>`
        : !kpis || kpis.length === 0
        ? html`<${Notice} kind="info">📊 KPI data is loading… Run notebook 01 to populate the data tables.</${Notice}>`
        : html`<div class="grid kpi">
            ${kpis.slice(0, 4).map((r) => {
              const t = num(r.share_trend_ppt);
              const dir = t > 0 ? "up" : t < 0 ? "down" : "flat";
              const icon = dir === "up" ? "▲" : dir === "down" ? "▼" : "—";
              return html`<div class="kpi-tile ${dir}" key=${r.brand}>
                <div class="label">${r.brand}</div>
                <div class="value">${num(r.value_share_pct).toFixed(1)}%</div>
                <div class="delta ${dir}">${icon} ${t > 0 ? "+" : ""}${t.toFixed(2)} ppt (4W trend)</div>
              </div>`;
            })}
          </div>`
    }
    <div class="section-gap"></div>
    <div class="grid two">
      <div class="card">
        <h3>Value Share Trend — Top Brands</h3>
        ${
          trend.length
            ? html`<${MultiLineChart} series=${trend} xTitle="Week Ending" yTitle="Value Share (%)" />`
            : html`<${Notice} kind="info">Run notebook 01 to populate share trend data.</${Notice}>`
        }
      </div>
      <div class="card">
        <h3>Top Insurgent Brands — 52W Share Gain</h3>
        ${
          insurgents.length
            ? html`<${HBarChart}
                labels=${insurgents.map((d) => d.brand)}
                values=${insurgents.map((d) => d.gain)}
                colors=${insurgents.map((d) => (d.gain > 0 ? ORANGE : "#AAAAAA"))}
                xTitle="52W Share Gain (ppt)"
                textFmt=${(v) => `${v > 0 ? "+" : ""}${v.toFixed(2)} ppt`}
              />`
            : html`<${Notice} kind="info">Run notebook 01 to populate insurgent brand data.</${Notice}>`
        }
      </div>
    </div>
  </div>`;
}

// ── AI Advisor (two-phase HITL) ─────────────────────────────────────────────────

function Advisor({ config, ctx, setCtx }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [gate, setGate] = useState(null);
  const [chosenRoute, setChosenRoute] = useState("");
  const [remaining, setRemaining] = useState(config.hitlTimeoutSecs);
  const [hitl, setHitl] = useState(null);
  const bottomRef = useRef(null);
  const routes = Object.keys(config.routeLabel);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, gate]);

  // HITL confirmation rate from the Lakebase audit log (refreshed after each decision).
  const refreshHitl = useCallback(() => {
    api.hitlStats().then((r) => setHitl(r && r.stats ? r.stats : null)).catch(() => setHitl(null));
  }, []);
  useEffect(() => { refreshHitl(); }, [refreshHitl]);

  const addAssistant = useCallback((content, chart) => {
    setMessages((m) => [...m, { role: "assistant", content, chart }]);
  }, []);

  useEffect(() => {
    if (!gate) return;
    const id = setInterval(() => {
      const elapsed = (Date.now() - gate.startedAt) / 1000;
      const left = Math.max(0, config.hitlTimeoutSecs - elapsed);
      setRemaining(left);
      if (left <= 0) {
        api.gateDecision("timed_out", gate).then(() => setTimeout(refreshHitl, 1500));
        setGate(null);
        addAssistant("⏰ Routing confirmation timed out. Please re-send your question.");
      }
    }, 1000);
    return () => clearInterval(id);
  }, [gate, config.hitlTimeoutSecs, addAssistant, refreshHitl]);

  async function ask(question) {
    if (!question.trim() || busy || gate) return;
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.enrich(question);
      if (res.status === "error") {
        addAssistant(`Couldn't reach the enrichment service. Detail: \`${res.detail}\``);
      } else if (res.status === "out_of_scope") {
        addAssistant("I can only help with brand performance — share trends, insurgent brand analysis, and distribution/velocity. Please name a brand and category.");
      } else if (res.status === "incomplete") {
        if (res.ctx) setCtx(res.ctx);
        addAssistant(`I need a bit more to route this accurately — please specify: **${(res.missing || []).join(", ")}**.`);
      } else if (res.status === "gate") {
        setCtx(res.ctx || {});
        setChosenRoute(res.route || routes[0]);
        setGate({ question, ctx: res.ctx || {}, sessionId: res.sessionId || "", proposedRoute: res.route || routes[0], startedAt: Date.now() });
        setRemaining(config.hitlTimeoutSecs);
      }
    } catch (e) {
      addAssistant(`Request failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!gate) return;
    const g = gate;
    setGate(null);
    setBusy(true);
    try {
      const res = await api.analyze(g.question, chosenRoute, g.ctx, g.sessionId, g.proposedRoute);
      addAssistant(res.text, res.chart);
      setTimeout(refreshHitl, 1500);
    } catch (e) {
      addAssistant(`Analysis failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  function cancel() {
    if (gate) api.gateDecision("cancelled", gate).then(() => setTimeout(refreshHitl, 1500));
    setGate(null);
    addAssistant("Cancelled. Rephrase your question or ask a new one.");
  }

  return html`<div class="chat-wrap">
    <${ContextPills} ctx=${ctx} />
    ${
      hitl && hitl.total
        ? html`<p class="muted" style=${{ fontSize: "12px", margin: "4px 0 10px" }}>
            🗄️ Lakebase audit log · HITL confirmation rate
            <b>${Math.round(hitl.confirmation_rate * 100)}%</b> of ${hitl.total} gate decisions (last ${hitl.days} days)
          </p>`
        : null
    }
    ${
      messages.length === 0 && !gate
        ? html`<div>
            <p class="muted" style=${{ fontWeight: 600, marginBottom: "10px" }}>Suggested questions</p>
            <div class="suggestions">
              ${config.suggested.map(
                (q) => html`<button class="suggestion" key=${q} onClick=${() => ask(q)}>${q}</button>`
              )}
            </div>
          </div>`
        : null
    }
    <div class="bubbles">
      ${messages.map(
        (m, i) => html`<div class="bubble ${m.role}" key=${i}>
          <div class="role">${m.role === "user" ? "You" : "🤖 BPM Advisor"}</div>
          ${m.content}
          ${m.chart ? html`<div style=${{ marginTop: "12px", background: "#fff", borderRadius: "12px" }}><${SpecChart} spec=${m.chart} /></div>` : null}
        </div>`
      )}
      ${busy ? html`<div class="bubble assistant"><span class="spinner"></span> ${gate ? "Analysing…" : "Understanding your question…"}</div>` : null}
    </div>
    ${
      gate
        ? html`<div class="gate">
            <h4>🔀 Confirm Routing</h4>
            <div class="row"><b>Question:</b> ${gate.question.slice(0, 140)}${gate.question.length > 140 ? "…" : ""}</div>
            <div class="row"><b>Proposed route:</b> <code>${config.routeLabel[chosenRoute] || chosenRoute}</code></div>
            <div class="why">Why: ${config.routeWhy[chosenRoute] || ""}</div>
            <div class="why">Context — ${gate.ctx.brand} · ${gate.ctx.category} · ${gate.ctx.retailer} · ${gate.ctx.time_window_weeks}W</div>
            <div class="progress-track"><div class="progress-fill" style=${{ width: `${(remaining / config.hitlTimeoutSecs) * 100}%` }}></div></div>
            <div class="why">⏱ ${Math.round(remaining)}s remaining</div>
            <div style=${{ marginTop: "12px" }}>
              <label class="why" style=${{ display: "block", marginBottom: "4px" }}>Route</label>
              <select class="select" style=${{ width: "100%" }} value=${chosenRoute} onChange=${(e) => setChosenRoute(e.target.value)}>
                ${routes.map((r) => html`<option value=${r} key=${r}>${config.routeLabel[r]}</option>`)}
              </select>
            </div>
            <div class="actions">
              <button class="btn primary" onClick=${confirm}>✅ Confirm & Run</button>
              <button class="btn" onClick=${cancel}>✖ Cancel</button>
            </div>
          </div>`
        : null
    }
    ${
      gate
        ? html`<${Notice} kind="info">⏳ Confirm the routing above to run the analysis.</${Notice}>`
        : html`<div class="composer">
            <input class="text-input" placeholder="Ask about brand performance, insurgent brands, or distribution…"
              value=${input} disabled=${busy}
              onInput=${(e) => setInput(e.target.value)}
              onKeyDown=${(e) => e.key === "Enter" && ask(input)} />
            <button class="btn navy" onClick=${() => ask(input)} disabled=${busy || !input.trim()}>Send</button>
          </div>`
    }
    <div ref=${bottomRef}></div>
  </div>`;
}

// ── Insurgent ───────────────────────────────────────────────────────────────────

const CATEGORIES = ["Infant Formula", "Baby Food", "Toddler Snacks"];

function threatChip(score) {
  if (score >= 60) return html`<span class="chip hot">${score.toFixed(0)}</span>`;
  if (score >= 40) return html`<span class="chip warm">${score.toFixed(0)}</span>`;
  return html`<span>${score.toFixed(0)}</span>`;
}

function Insurgent({ ctx, refreshKey }) {
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.insurgents(category).then((r) => {
      if (!cancelled) { setRows(r.rows); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [category, refreshKey]);

  return html`<div>
    <${ContextPills} ctx=${ctx} />
    <div style=${{ marginBottom: "16px", maxWidth: "280px" }}>
      <label class="muted" style=${{ display: "block", marginBottom: "4px", fontSize: "13px", fontWeight: 600 }}>Category</label>
      <select class="select" style=${{ width: "100%" }} value=${category} onChange=${(e) => setCategory(e.target.value)}>
        ${CATEGORIES.map((c) => html`<option key=${c}>${c}</option>`)}
      </select>
    </div>
    ${
      loading
        ? html`<${Loading} label="Loading insurgent brands…" />`
        : !rows || rows.length === 0
        ? html`<${Notice} kind="info">No insurgent brand data available. Run notebook 01 first.</${Notice}>`
        : html`<div>
            <div class="card">
              <h3>Insurgent Brand Performance Summary</h3>
              <table class="data">
                <thead><tr><th>Brand</th><th>Avg Share %</th><th>52W Gain (ppt)</th><th>Threat Score</th><th>Avg ACV %</th></tr></thead>
                <tbody>
                  ${rows.map(
                    (r) => html`<tr key=${r.brand}>
                      <td style=${{ fontWeight: 600 }}>${r.brand}</td>
                      <td>${num(r.avg_share).toFixed(2)}</td>
                      <td style=${{ color: num(r.gain_52w) > 0 ? "#1a8f5b" : "#d6402c", fontWeight: 600 }}>${num(r.gain_52w) > 0 ? "+" : ""}${num(r.gain_52w).toFixed(2)}</td>
                      <td>${threatChip(num(r.threat_score))}</td>
                      <td>${num(r.avg_acv).toFixed(2)}</td>
                    </tr>`
                  )}
                </tbody>
              </table>
            </div>
            <div class="section-gap"></div>
            <div class="card">
              <h3>Insurgent Brand Threat Scores — ${category}</h3>
              <${HBarChart}
                labels=${rows.map((r) => r.brand)}
                values=${rows.map((r) => num(r.threat_score))}
                colors=${rows.map((r) => (num(r.threat_score) >= 40 ? ORANGE : NAVY))}
                xTitle="Threat Score (0–100)"
                textFmt=${(v) => v.toFixed(0)}
              />
            </div>
          </div>`
    }
  </div>`;
}

// ── Distribution ─────────────────────────────────────────────────────────────────

function Distribution({ ctx, refreshKey }) {
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.distribution().then((r) => {
      if (!cancelled) { setRows(r.rows); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [refreshKey]);

  if (loading) return html`<${Loading} label="Loading distribution data…" />`;
  if (!rows || rows.length === 0)
    return html`<div><${ContextPills} ctx=${ctx} /><${Notice} kind="info">No distribution data available. Run notebook 01 first.</${Notice}></div>`;

  const totalUs = rows.filter((r) => r.retailer === "Total US").sort((a, b) => num(a.avg_acv_pct) - num(b.avg_acv_pct));

  return html`<div>
    <${ContextPills} ctx=${ctx} />
    <div class="card">
      <h3>ACV Distribution & Velocity by Brand & Retailer</h3>
      <table class="data">
        <thead><tr><th>Brand</th><th>Retailer</th><th>Avg ACV %</th><th>Velocity / $1M ACV</th><th>OOS Rate %</th></tr></thead>
        <tbody>
          ${rows.map(
            (r, i) => html`<tr key=${r.brand + r.retailer + i}>
              <td style=${{ fontWeight: 600 }}>${r.brand}</td>
              <td>${r.retailer}</td>
              <td>${num(r.avg_acv_pct) < 60 ? html`<span class="chip low">${num(r.avg_acv_pct).toFixed(1)}</span>` : num(r.avg_acv_pct).toFixed(1)}</td>
              <td>${num(r.avg_velocity).toFixed(0)}</td>
              <td>${num(r.avg_oos_pct).toFixed(2)}</td>
            </tr>`
          )}
        </tbody>
      </table>
    </div>
    ${
      totalUs.length
        ? html`<div><div class="section-gap"></div>
            <div class="card">
              <h3>ACV Distribution % — Total US (Latest 4W)</h3>
              <${HBarChart}
                labels=${totalUs.map((r) => r.brand)}
                values=${totalUs.map((r) => num(r.avg_acv_pct))}
                colors=${totalUs.map((r) => (num(r.avg_acv_pct) >= 60 ? NAVY : ORANGE))}
                xTitle="ACV %"
                threshold=${60}
              />
            </div></div>`
        : null
    }
  </div>`;
}

// ── App shell ─────────────────────────────────────────────────────────────────

const NAV = [
  { key: "dashboard", icon: "📊", label: "Dashboard" },
  { key: "advisor", icon: "💬", label: "AI Advisor" },
  { key: "insurgent", icon: "🏃", label: "Insurgent Brands" },
  { key: "distribution", icon: "📦", label: "Distribution" },
];
const SUBTITLE = {
  dashboard: "KPI overview, value-share trends, and emerging brand threats",
  advisor: "Ask a question — Phase 1 enriches, you confirm the route, Phase 2 runs",
  insurgent: "Challenger-brand tracking with threat scores",
  distribution: "ACV distribution and velocity gaps",
};

function App() {
  const [config, setConfig] = useState(null);
  const [view, setView] = useState("dashboard");
  const [ctx, setCtx] = useState({});
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => { api.config().then(setConfig).catch(() => setConfig(null)); }, []);

  async function refresh() {
    await api.refresh().catch(() => {});
    setRefreshKey((k) => k + 1);
  }

  if (!config) return html`<div class="center-empty"><span class="spinner"></span> Loading Brand Performance Manager…</div>`;

  const current = NAV.find((n) => n.key === view);

  return html`<div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="logo">${config.icon}</div>
        <div>
          <div class="title">${config.title}</div>
          <div class="sub">Databricks AgentBricks</div>
        </div>
      </div>
      ${NAV.map(
        (n) => html`<button class="nav-item ${view === n.key ? "active" : ""}" key=${n.key} onClick=${() => setView(n.key)}>
          <span class="ic">${n.icon}</span> ${n.label}
        </button>`
      )}
      ${
        Object.keys(ctx).length
          ? html`<button class="nav-item" style=${{ marginTop: "12px", fontSize: "12px", opacity: 0.8 }} onClick=${() => setCtx({})}>
              <span class="ic">🧹</span> Clear Context
            </button>`
          : null
      }
      <div class="sidebar-foot">
        Agent: <code>${config.agent}</code><br />
        Catalog: <code>${config.catalog}</code>
      </div>
    </aside>
    <main class="main">
      <div class="topbar">
        <div>
          <h1>${config.icon} ${current?.label}</h1>
          <p>${SUBTITLE[view]}</p>
        </div>
        <button class="btn" onClick=${refresh}>🔄 Refresh Data</button>
      </div>
      ${view === "dashboard" ? html`<${Dashboard} refreshKey=${refreshKey} />` : null}
      ${view === "advisor" ? html`<${Advisor} config=${config} ctx=${ctx} setCtx=${setCtx} />` : null}
      ${view === "insurgent" ? html`<${Insurgent} ctx=${ctx} refreshKey=${refreshKey} />` : null}
      ${view === "distribution" ? html`<${Distribution} ctx=${ctx} refreshKey=${refreshKey} />` : null}
    </main>
  </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
