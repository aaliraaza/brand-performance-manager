import { useEffect, useState } from "react";
import { api, type AppConfig } from "./lib/api";
import Dashboard from "./components/Dashboard";
import Advisor from "./components/Advisor";
import Insurgent from "./components/Insurgent";
import Distribution from "./components/Distribution";

type View = "dashboard" | "advisor" | "insurgent" | "distribution";

const NAV: { key: View; icon: string; label: string }[] = [
  { key: "dashboard", icon: "📊", label: "Dashboard" },
  { key: "advisor", icon: "💬", label: "AI Advisor" },
  { key: "insurgent", icon: "🏃", label: "Insurgent Brands" },
  { key: "distribution", icon: "📦", label: "Distribution" },
];

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [ctx, setCtx] = useState<Record<string, any>>({});
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    api.config().then(setConfig).catch(() => setConfig(null));
  }, []);

  async function refresh() {
    await api.refresh().catch(() => {});
    setRefreshKey((k) => k + 1);
  }

  if (!config) {
    return (
      <div className="center-empty">
        <span className="spinner" /> Loading Brand Performance Manager…
      </div>
    );
  }

  const subtitle: Record<View, string> = {
    dashboard: "KPI overview, value-share trends, and emerging brand threats",
    advisor: "Ask a question — Phase 1 enriches, you confirm the route, Phase 2 runs",
    insurgent: "Challenger-brand tracking with threat scores",
    distribution: "ACV distribution and velocity gaps",
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">{config.icon}</div>
          <div>
            <div className="title">{config.title}</div>
            <div className="sub">Databricks AgentBricks</div>
          </div>
        </div>

        {NAV.map((n) => (
          <button
            key={n.key}
            className={`nav-item ${view === n.key ? "active" : ""}`}
            onClick={() => setView(n.key)}
          >
            <span className="ic">{n.icon}</span>
            {n.label}
          </button>
        ))}

        {Object.keys(ctx).length > 0 && (
          <button
            className="nav-item"
            style={{ marginTop: 12, fontSize: 12, opacity: 0.8 }}
            onClick={() => setCtx({})}
          >
            <span className="ic">🧹</span> Clear Context
          </button>
        )}

        <div className="sidebar-foot">
          Agent: <code>{config.agent}</code>
          <br />
          Catalog: <code>{config.catalog}</code>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div>
            <h1>
              {config.icon} {NAV.find((n) => n.key === view)?.label}
            </h1>
            <p>{subtitle[view]}</p>
          </div>
          <button className="btn" onClick={refresh}>
            🔄 Refresh Data
          </button>
        </div>

        {view === "dashboard" && <Dashboard refreshKey={refreshKey} />}
        {view === "advisor" && <Advisor config={config} ctx={ctx} setCtx={setCtx} />}
        {view === "insurgent" && <Insurgent ctx={ctx} refreshKey={refreshKey} />}
        {view === "distribution" && <Distribution ctx={ctx} refreshKey={refreshKey} />}
      </main>
    </div>
  );
}
