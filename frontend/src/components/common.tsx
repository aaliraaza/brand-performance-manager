const NAVY = "#003087";
const ORANGE = "#E87722";

export function ContextPills({ ctx }: { ctx: Record<string, any> }) {
  const pills: { label: string; value: string; color: string }[] = [];
  if (ctx.brand) pills.push({ label: "Brand", value: ctx.brand, color: NAVY });
  if (ctx.retailer) pills.push({ label: "Retailer", value: ctx.retailer, color: "#555" });
  if (ctx.time_window_weeks)
    pills.push({ label: "Window", value: `${ctx.time_window_weeks}W`, color: ORANGE });
  if (!pills.length) return null;
  return (
    <div className="pills">
      {pills.map((p) => (
        <span key={p.label} className="pill" style={{ background: p.color }}>
          <b>{p.label}:</b> {p.value}
        </span>
      ))}
    </div>
  );
}

export function Notice({ kind, children }: { kind: "info" | "warn" | "err"; children: React.ReactNode }) {
  return <div className={`notice ${kind}`}>{children}</div>;
}

export function Loading({ label }: { label: string }) {
  return (
    <div className="loading-row">
      <span className="spinner" /> {label}
    </div>
  );
}
