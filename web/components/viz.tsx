"use client";

export function Stat({ v, k }: { v: string; k: string }) {
  return <div className="stat"><div className="v">{v}</div><div className="k">{k}</div></div>;
}

export function DistBar({ dist, total }: { dist: Record<string, number>; total: number }) {
  const max = Math.max(1, ...Object.values(dist));
  const colors = ["#5e6ad2", "#0ca678", "#e8890c", "#e03131", "#1098ad", "#7048e8"];
  const keys = Object.keys(dist).sort();
  return (
    <div>{keys.map((k, i) => (
      <div className="distrow" key={k}>
        <span>{k}</span>
        <div className="bar"><div style={{ width: `${(100 * (dist[k] / max)).toFixed(1)}%`, background: colors[i % colors.length] }} /></div>
        <span className="n">{dist[k]} · {total ? Math.round(100 * dist[k] / total) : 0}%</span>
      </div>
    ))}</div>
  );
}

export function PageHeader({ title, desc, actions }: { title: string; desc: string; actions?: React.ReactNode }) {
  return (
    <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-end" }}>
      <div><h2 style={{ margin: 0 }}>{title}</h2><p className="muted" style={{ margin: "2px 0 0" }}>{desc}</p></div>
      <div className="row" style={{ margin: 0 }}>{actions}</div>
    </div>
  );
}

export function Hist({ buckets }: { buckets: number[] }) {
  const max = Math.max(1, ...buckets);
  return (
    <div>
      <div className="hist">{buckets.map((b, i) => (
        <div key={i} className={b === max && b > 0 ? "hot" : ""} style={{ height: `${Math.max(5, Math.round(100 * b / max))}%` }} title={`${(i / 10).toFixed(1)}–${((i + 1) / 10).toFixed(1)}: ${b}`} />
      ))}</div>
      <div className="muted" style={{ fontSize: 11, display: "flex", justifyContent: "space-between" }}><span>low conf</span><span>high conf</span></div>
    </div>
  );
}
