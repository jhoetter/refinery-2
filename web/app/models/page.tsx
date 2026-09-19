"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Entry = { name: string; kind: string; task: string; params: Record<string, unknown>; metrics: Record<string, unknown> };

export default function Models() {
  const [models, setModels] = useState<Entry[]>([]);
  const [bench, setBench] = useState<Record<string, { accuracy?: number; f1_macro?: number; latency_ms?: number; error?: string; kind?: string }>>({});
  const [msg, setMsg] = useState("");
  const [trainName, setTrainName] = useState("student-v1");
  const [apiForm, setApiForm] = useState({ name: "gpt-teacher", task: "topic", base_url: "https://api.openai.com/v1", model: "gpt-4o-mini" });
  const [pv, setPv] = useState({ model: "", text: "" });
  const [pvOut, setPvOut] = useState("");

  async function refresh() {
    const m = await api<{ models: Entry[] }>("/api/models");
    setModels(m.models);
  }
  useEffect(() => { refresh().catch((e) => setMsg(String(e))); }, []);

  async function registerApi() {
    try {
      await api("/api/models/api", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(apiForm) });
      setMsg(`registered API teacher ${apiForm.name}`); refresh();
    } catch (e) { setMsg(String(e)); }
  }
  async function train() {
    try {
      setMsg("training…");
      await api("/api/models/train", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task: "topic", name: trainName, min_conf: 0.8 }) });
      setMsg(`trained ${trainName}`); refresh();
    } catch (e) { setMsg(String(e)); }
  }
  async function benchmark() {
    try {
      setMsg("benchmarking…");
      const b = await api<{ models: typeof bench }>("/api/models/benchmark", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task: "topic" }),
      });
      setBench(b.models); setMsg("");
    } catch (e) { setMsg(String(e)); }
  }
  async function predict() {
    try {
      const r = await api<{ label: unknown; confidence: number; latency_ms: number }>("/api/predict", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: pv.model || models[0]?.name, task: "topic", text: pv.text }),
      });
      setPvOut(JSON.stringify(r));
    } catch (e) { setPvOut(String(e)); }
  }

  return (
    <div>
      <h2>models <span className="muted">teachers (API) vs students (local, fast, cheap)</span></h2>
      {models.map((m) => (
        <div className="card" key={m.name}><b>{m.name}</b> <span className="pill">{m.kind}</span> <span className="muted">task {m.task} · {JSON.stringify(m.metrics)}</span></div>
      ))}
      {models.length === 0 && <p className="muted">no models yet</p>}

      <h3>register API teacher</h3>
      <div className="row">
        <input value={apiForm.name} onChange={(e) => setApiForm({ ...apiForm, name: e.target.value })} placeholder="name" />
        <input value={apiForm.base_url} onChange={(e) => setApiForm({ ...apiForm, base_url: e.target.value })} placeholder="base_url" size={30} />
        <input value={apiForm.model} onChange={(e) => setApiForm({ ...apiForm, model: e.target.value })} placeholder="model" />
        <button onClick={registerApi}>register</button>
      </div>

      <h3>train student (distill)</h3>
      <div className="row">
        <input value={trainName} onChange={(e) => setTrainName(e.target.value)} />
        <button className="primary" onClick={train}>train on confident consensus + golden</button>
        <button onClick={benchmark}>benchmark all</button>
      </div>

      {Object.keys(bench).length > 0 && (
        <table className="grid">
          <thead><tr><th>model</th><th>kind</th><th>acc</th><th>f1</th><th>latency ms</th><th>note</th></tr></thead>
          <tbody>{Object.entries(bench).map(([k, v]) => (
            <tr key={k}><td>{k}</td><td>{v.kind ?? "–"}</td><td>{v.accuracy ?? "–"}</td><td>{v.f1_macro ?? "–"}</td><td>{v.latency_ms ?? "–"}</td><td>{v.error ?? ""}</td></tr>
          ))}</tbody>
        </table>
      )}

      <h3>predict playground (serve via API)</h3>
      <div className="row">
        <select value={pv.model} onChange={(e) => setPv({ ...pv, model: e.target.value })}>
          <option value="">auto</option>{models.map((m) => <option key={m.name} value={m.name}>{m.name}</option>)}
        </select>
        <input value={pv.text} onChange={(e) => setPv({ ...pv, text: e.target.value })} placeholder="text…" size={50} />
        <button className="primary" onClick={predict}>predict</button>
      </div>
      {pvOut && <pre className="card">{pvOut}</pre>}
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
