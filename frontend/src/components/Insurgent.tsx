import { useEffect, useState } from "react";
import { api, type InsurgentRow } from "../lib/api";
import { HBarChart } from "./Chart";
import { ContextPills, Loading, Notice } from "./common";

const NAVY = "#003087";
const ORANGE = "#E87722";
const CATEGORIES = ["Infant Formula", "Baby Food", "Toddler Snacks"];

function threatChip(score: number) {
  if (score >= 60) return <span className="chip hot">{score.toFixed(0)}</span>;
  if (score >= 40) return <span className="chip warm">{score.toFixed(0)}</span>;
  return <span>{score.toFixed(0)}</span>;
}

export default function Insurgent({ ctx, refreshKey }: { ctx: Record<string, any>; refreshKey: number }) {
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [rows, setRows] = useState<InsurgentRow[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.insurgents(category).then((r) => {
      if (!cancelled) {
        setRows(r.rows);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [category, refreshKey]);

  return (
    <div>
      <ContextPills ctx={ctx} />
      <div style={{ marginBottom: 16, maxWidth: 280 }}>
        <label className="muted" style={{ display: "block", marginBottom: 4, fontSize: 13, fontWeight: 600 }}>
          Category
        </label>
        <select className="select" value={category} onChange={(e) => setCategory(e.target.value)} style={{ width: "100%" }}>
          {CATEGORIES.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <Loading label="Loading insurgent brands…" />
      ) : !rows || rows.length === 0 ? (
        <Notice kind="info">No insurgent brand data available. Run notebook 01 first.</Notice>
      ) : (
        <>
          <div className="card">
            <h3>Insurgent Brand Performance Summary</h3>
            <table className="data">
              <thead>
                <tr>
                  <th>Brand</th>
                  <th>Avg Share %</th>
                  <th>52W Gain (ppt)</th>
                  <th>Threat Score</th>
                  <th>Avg ACV %</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.brand}>
                    <td style={{ fontWeight: 600 }}>{r.brand}</td>
                    <td>{Number(r.avg_share).toFixed(2)}</td>
                    <td style={{ color: r.gain_52w > 0 ? "#1a8f5b" : "#d6402c", fontWeight: 600 }}>
                      {r.gain_52w > 0 ? "+" : ""}
                      {Number(r.gain_52w).toFixed(2)}
                    </td>
                    <td>{threatChip(Number(r.threat_score))}</td>
                    <td>{Number(r.avg_acv).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="section-gap" />

          <div className="card">
            <h3>Insurgent Brand Threat Scores — {category}</h3>
            <HBarChart
              labels={rows.map((r) => r.brand)}
              values={rows.map((r) => Number(r.threat_score))}
              colors={rows.map((r) => (Number(r.threat_score) >= 40 ? ORANGE : NAVY))}
              xTitle="Threat Score (0–100)"
              textFmt={(v) => v.toFixed(0)}
            />
          </div>
        </>
      )}
    </div>
  );
}
