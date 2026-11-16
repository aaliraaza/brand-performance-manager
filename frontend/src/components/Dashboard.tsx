import { useEffect, useState } from "react";
import { api, type KpiRow } from "../lib/api";
import { MultiLineChart, HBarChart } from "./Chart";
import { Loading, Notice } from "./common";

const ORANGE = "#E87722";

export default function Dashboard({ refreshKey }: { refreshKey: number }) {
  const [kpis, setKpis] = useState<KpiRow[] | null>(null);
  const [kpiErr, setKpiErr] = useState<string | null>(null);
  const [trend, setTrend] = useState<{ name: string; x: string[]; y: number[] }[]>([]);
  const [insurgents, setInsurgents] = useState<{ brand: string; gain: number }[]>([]);
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
            return {
              name: brand,
              x: t.rows.map((r) => r.week_ending),
              y: t.rows.map((r) => r.value_share_pct),
            };
          })
        );
        if (!cancelled) setTrend(series.filter((s) => s.y.length));

        const ins = await api.insurgents("Infant Formula");
        if (!cancelled)
          setInsurgents(ins.rows.map((r) => ({ brand: r.brand, gain: r.gain_52w })));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  if (loading && !kpis) return <Loading label="Loading dashboard…" />;

  return (
    <div>
      {kpiErr ? (
        <Notice kind="warn">⚠️ Could not load KPI data — {kpiErr}</Notice>
      ) : !kpis || kpis.length === 0 ? (
        <Notice kind="info">📊 KPI data is loading… Run notebook 01 to populate the data tables.</Notice>
      ) : (
        <div className="grid kpi">
          {kpis.slice(0, 4).map((r) => {
            const trendPpt = Number(r.share_trend_ppt) || 0;
            const dir = trendPpt > 0 ? "up" : trendPpt < 0 ? "down" : "flat";
            const icon = dir === "up" ? "▲" : dir === "down" ? "▼" : "—";
            return (
              <div key={r.brand} className={`kpi-tile ${dir}`}>
                <div className="label">{r.brand}</div>
                <div className="value">{Number(r.value_share_pct).toFixed(1)}%</div>
                <div className={`delta ${dir}`}>
                  {icon} {trendPpt > 0 ? "+" : ""}
                  {trendPpt.toFixed(2)} ppt (4W trend)
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="section-gap" />

      <div className="grid two">
        <div className="card">
          <h3>Value Share Trend — Top Brands</h3>
          {trend.length ? (
            <MultiLineChart series={trend} xTitle="Week Ending" yTitle="Value Share (%)" />
          ) : (
            <Notice kind="info">Run notebook 01 to populate share trend data.</Notice>
          )}
        </div>
        <div className="card">
          <h3>Top Insurgent Brands — 52W Share Gain</h3>
          {insurgents.length ? (
            <HBarChart
              labels={insurgents.map((d) => d.brand)}
              values={insurgents.map((d) => d.gain)}
              colors={insurgents.map((d) => (d.gain > 0 ? ORANGE : "#AAAAAA"))}
              xTitle="52W Share Gain (ppt)"
              textFmt={(v) => `${v > 0 ? "+" : ""}${v.toFixed(2)} ppt`}
            />
          ) : (
            <Notice kind="info">Run notebook 01 to populate insurgent brand data.</Notice>
          )}
        </div>
      </div>
    </div>
  );
}
