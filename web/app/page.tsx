"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DistBar, Hist, Stat } from "@/components/viz";

type Stats = {
  task: string; n_records: number; n_golden: number; coverage: number;
  dist_agg: Record<string, number>; dist_golden: Record<string, number>;
  conf_hist: number[]; sources: Record<string, { accuracy: number | null; coverage: number }>;
  slices: Record<string, number>;
};

export default function Overview() {
  const [tasks, setTasks] = useState<string[]>(["topic"]);
  const [task, setTask] = useState("topic");
  const [taskType, setTaskType] = useState("classification");
  const [s, setS] = useState<Stats | null>(null);
  const [queueN, setQueueN] = useState(0);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<{ tasks: Record<string, { type: string }> }>("/api/project")
      .then((p) => {
        setTasks(Object.keys(p.tasks));
        setTaskType(p.tasks[task]?.type ?? "classification");
      })
      .catch((e) => setErr(String(e)));
  }, [task]);
  useEffect(() => {
    api<Stats>(`/api/stats?task=${task}`).then(setS).catch((e) => setErr(String(e)));
    api<{ n: number }>(`/api/queue?task=${task}`).then((q) => setQueueN(q.n)).catch(() => {});
  }, [task]);

  if (err) return <p>Backend nicht erreichbar ({err}). Läuft die API auf :8000?</p>;
  if (!s) return <p className="muted">loading…</p>;
  return (
    <div>
      <div className="row">
        <h2 style={{ margin: 0 }}>overview</h2>
        <select value={task} onChange={(e) => setTask(e.target.value)}>{tasks.map((t) => <option key={t}>{t}</option>)}</select>
      </div>
      <div className="grid4">
        <Stat v={String(s.n_records)} k="records" />
        <Stat v={`${Math.round(100 * s.coverage)}%`} k="golden coverage" />
        <Stat v={String(queueN)} k="need review" />
        <Stat v={String(Object.keys(s.sources).length)} k="sources" />
      </div>
      <div className="grid2">
        <div className="card">
          <h4>label distribution · consensus ({s.n_records})</h4>
          {taskType === "classification"
            ? <DistBar dist={s.dist_agg} total={s.n_records} />
            : <p>{Object.keys(s.dist_agg).length} distinct {taskType} values across {s.n_records} records with consensus – inspect them in browse.</p>}
        </div>
        <div className="card">
          <h4>label distribution · golden ({s.n_golden})</h4>
          {s.n_golden ? <DistBar dist={s.dist_golden} total={s.n_golden} /> : <p className="muted">no golden labels yet – label in the review queue</p>}
        </div>
      </div>
      <div className="grid2">
        <div className="card">
          <h4>confidence histogram</h4>
          <Hist buckets={s.conf_hist} />
        </div>
        <div className="card">
          <h4>slices</h4>
          {Object.entries(s.slices).map(([k, v]) => (
            <div className="distrow" key={k}><span>{k}</span>
              <div className="bar"><div style={{ width: `${Math.round(100 * v / s.n_records)}%` }} /></div>
              <span className="n">{v}</span></div>
          ))}
        </div>
      </div>
      <h3>source quality vs golden</h3>
      <table className="grid">
        <thead><tr><th>source</th><th>accuracy</th><th>coverage</th></tr></thead>
        <tbody>{Object.entries(s.sources).map(([k, v]) => (
          <tr key={k}><td className="mono">{k}</td><td>{v.accuracy ?? "–"}</td><td>{v.coverage}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}
