import { useEffect, useState } from "react";
import { api, type DistributionRow } from "../lib/api";
import { HBarChart } from "./Chart";
import { ContextPills, Loading, Notice } from "./common";

const NAVY = "#003087";
const ORANGE = "#E87722";

export default function Distribution({ ctx, refreshKey }: { ctx: Record<string, any>; refreshKey: number }) {
  const [rows, setRows] = useState<DistributionRow[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.distribution().then((r) => {
      if (!cancelled) {
        setRows(r.rows);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  if (loading) return <Loading label="Loading distribution data…" />;
  if (!rows || rows.length === 0)
    return (
      <div>
        <ContextPills ctx={ctx} />
        <Notice kind="info">No distribution data available. Run notebook 01 first.</Notice>
      </div>
    );

  const totalUs = rows
    .filter((r) => r.retailer === "Total US")
    .sort((a, b) => Number(a.avg_acv_pct) - Number(b.avg_acv_pct));

  return (
    <div>
      <ContextPills ctx={ctx} />
      <div className="card">
        <h3>ACV Distribution &amp; Velocity by Brand &amp; Retailer</h3>
        <table className="data">
          <thead>
            <tr>
              <th>Brand</th>
              <th>Retailer</th>
              <th>Avg ACV %</th>
              <th>Velocity / $1M ACV</th>
              <th>OOS Rate %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.brand}-${r.retailer}-${i}`}>
                <td style={{ fontWeight: 600 }}>{r.brand}</td>
                <td>{r.retailer}</td>
                <td>
                  {Number(r.avg_acv_pct) < 60 ? (
                    <span className="chip low">{Number(r.avg_acv_pct).toFixed(1)}</span>
                  ) : (
                    Number(r.avg_acv_pct).toFixed(1)
                  )}
                </td>
                <td>{Number(r.avg_velocity).toFixed(0)}</td>
                <td>{Number(r.avg_oos_pct).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalUs.length > 0 && (
        <>
          <div className="section-gap" />
          <div className="card">
            <h3>ACV Distribution % — Total US (Latest 4W)</h3>
            <HBarChart
              labels={totalUs.map((r) => r.brand)}
              values={totalUs.map((r) => Number(r.avg_acv_pct))}
              colors={totalUs.map((r) => (Number(r.avg_acv_pct) >= 60 ? NAVY : ORANGE))}
              xTitle="ACV %"
              threshold={60}
            />
          </div>
        </>
      )}
    </div>
  );
}
