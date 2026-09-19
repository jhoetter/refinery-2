"use client";
import { useCallback, useEffect, useState } from "react";
import { api, shortLabel, TaskDef } from "@/lib/api";
import { LabelEditor } from "@/components/editor";

type Rec = { id: string; text: string; votes: { source: string; label: unknown; confidence: number }[]; agg: { label: unknown; confidence: number } | null; golden: unknown };

export default function Browse() {
  const [tasks, setTasks] = useState<Record<string, TaskDef>>({});
  const [task, setTask] = useState("topic");
  const [q, setQ] = useState("");
  const [gold, setGold] = useState("all");
  const [labelF, setLabelF] = useState("all");
  const [rows, setRows] = useState<Rec[]>([]);
  const [sel, setSel] = useState<{ id: string; text: string; votes: Rec["votes"]; agg: Rec["agg"]; golden: unknown } | null>(null);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    const p = await api<{ tasks: Record<string, TaskDef> }>("/api/project");
    setTasks(p.tasks);
    const d = await api<{ records: Rec[] }>(`/api/records?task=${task}&limit=500&q=${encodeURIComponent(q)}`);
    setRows(d.records);
  }, [task, q]);

  useEffect(() => { load().catch((e) => setMsg(String(e))); }, [load]);

  const labels = tasks[task]?.labels ?? [];
  const shown = rows.filter((r) => {
    if (gold === "golden" && !r.golden) return false;
    if (gold === "unlabeled" && r.golden) return false;
    if (labelF !== "all" && String((r.agg as { label: unknown } | null)?.label ?? "") !== labelF) return false;
    return true;
  });

  async function open(id: string) {
    const d = await api<{ record: { id: string; text: string }; votes: Rec["votes"]; agg: Rec["agg"]; golden: unknown }>(`/api/record/${id}?task=${task}`);
    setSel({ id: d.record.id, text: d.record.text, votes: d.votes, agg: d.agg, golden: d.golden });
  }
  async function save(label: unknown) {
    if (!sel) return;
    await api("/api/labels", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ record_id: sel.id, task, label }) });
    setMsg(`saved golden for ${sel.id}`);
    await load();
    open(sel.id).catch(() => {});
  }

  return (
    <div>
      <h2 style={{ marginTop: 4 }}>browse</h2>
      <div className="row">
        <select value={task} onChange={(e) => setTask(e.target.value)}>{Object.keys(tasks).map((k) => <option key={k}>{k}</option>)}</select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="search…" size={28} />
        <label className="flt">status <select value={gold} onChange={(e) => setGold(e.target.value)}>
          <option value="all">all</option><option value="golden">golden</option><option value="unlabeled">unlabeled</option>
        </select></label>
        {labels.length > 0 && (
          <label className="flt">label <select value={labelF} onChange={(e) => setLabelF(e.target.value)}>
            <option value="all">all</option>{labels.map((l) => <option key={l}>{l}</option>)}
          </select></label>
        )}
        <span className="muted">{shown.length} / {rows.length}</span>
      </div>
      {msg && <p className="muted">{msg}</p>}
      <div className="split">
        <table className="grid">
          <thead><tr><th>id</th><th>text</th><th>consensus</th><th>conf</th><th>golden</th></tr></thead>
          <tbody>{shown.slice(0, 100).map((r) => (
            <tr key={r.id} className="rowlink" onClick={() => open(r.id)}>
              <td className="mono muted">{r.id}</td>
              <td>{r.text.slice(0, 90)}…</td>
              <td>{r.agg ? <span className="pill acc">{shortLabel(r.agg.label)}</span> : <span className="muted">–</span>}</td>
              <td>{r.agg ? <span className="confbar"><div style={{ width: `${Math.round(100 * r.agg.confidence)}%` }} /></span> : "–"}</td>
              <td>{r.golden ? <span className="pill gold">{shortLabel(r.golden)}</span> : <span className="pill low">–</span>}</td>
            </tr>
          ))}</tbody>
        </table>
        <div>
          {!sel && <p className="muted">Select a row to inspect + label.</p>}
          {sel && tasks[task] && (
            <div className="card">
              <h3 style={{ marginTop: 0 }}>{sel.id}</h3>
              <h4>label as golden</h4>
              <LabelEditor key={task + sel.id} task={tasks[task]} text={sel.text} golden={sel.golden} onSave={save} />
              <p>{sel.text}</p>
              <table className="grid"><tbody>{sel.votes.map((v, i) => <tr key={i}><td className="mono">{v.source}</td><td>{shortLabel(v.label)}</td><td>{v.confidence}</td></tr>)}</tbody></table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
