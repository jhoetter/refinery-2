"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Project = { name: string; dataset: string; n_records: number; tasks: Record<string, unknown>; slices: unknown[] };

export default function Overview() {
  const [p, setP] = useState<Project | null>(null);
  const [models, setModels] = useState<{ name: string; kind: string }[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<Project>("/api/project").then(setP).catch((e) => setErr(String(e)));
    api<{ models: { name: string; kind: string }[] }>("/api/models").then((m) => setModels(m.models)).catch(() => {});
  }, []);

  if (err) return <p>Backend nicht erreichbar ({err}). Läuft es auf :8000?</p>;
  if (!p) return <p className="muted">loading…</p>;
  return (
    <div>
      <h2>{p.name} <span className="muted">· {p.dataset}</span></h2>
      <div className="card">{p.n_records} records · {Object.keys(p.tasks).length} tasks · {models.length} registered models</div>
      <h3>tasks</h3>
      {Object.entries(p.tasks).map(([k, t]) => (
        <div className="card" key={k}><b>{k}</b> <span className="muted">{(t as { type: string }).type}</span></div>
      ))}
      <h3>models</h3>
      {models.length === 0 && <p className="muted">none yet – train a student or register an API teacher under /models</p>}
      {models.map((m) => <div className="card" key={m.name}><b>{m.name}</b> <span className="pill">{m.kind}</span></div>)}
      <h3>slices</h3>
      <p className="muted">{p.slices.map((s) => (s as { name: string }).name).join(", ") || "–"}</p>
      <p className="muted">Label flow: templates → teacher labels → review disagreements → train student → benchmark → /api/predict.</p>
    </div>
  );
}
