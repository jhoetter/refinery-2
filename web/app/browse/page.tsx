"use client";
import { useCallback, useEffect, useState } from "react";
import { api, shortLabel, TaskDef } from "@/lib/api";
import { AllTasks } from "@/components/task_sections";
import { PageHeader } from "@/components/viz";
import { toPayload, ViewBuilder, ViewDef } from "@/components/view_builder";

type Rec = { id: string; text: string; votes: { source: string; label: unknown; confidence: number }[]; agg: { label: unknown; confidence: number } | null; golden: unknown };
type View = { name: string; description: string };

export default function Browse() {
  const [tasks, setTasks] = useState<Record<string, TaskDef>>({});
  const [task, setTask] = useState("topic");
  const [views, setViews] = useState<View[]>([]);
  const [activeView, setActiveView] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);
  const [rows, setRows] = useState<Rec[]>([]);
  const [total, setTotal] = useState(0);
  const [selId, setSelId] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [sources, setSources] = useState<string[]>([]);
  const [leftOpen, setLeftOpen] = useState(true);

  const loadMeta = useCallback(async () => {
    const p = await api<{ tasks: Record<string, TaskDef> }>("/api/project");
    setTasks(p.tasks);
    setViews((await api<{ views: View[] }>("/api/views")).views);
  }, []);

  const runAll = useCallback(async () => {
    const d = await api<{ records: Rec[] }>(`/api/records?task=${task}&limit=500`);
    setRows(d.records); setTotal(d.records.length);
    setSources([...new Set(d.records.flatMap((r) => r.votes.map((v) => v.source)))]);
  }, [task]);

  useEffect(() => { loadMeta().catch((e) => setMsg(String(e))); }, [loadMeta]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") setSelId(null); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  useEffect(() => { setActiveView(null); setBuilding(false); runAll().catch((e) => setMsg(String(e))); }, [runAll]);

  async function applyView(name: string | null, def?: Record<string, unknown>) {
    try {
      const r = await api<{ records: Rec[]; n: number }>("/api/views/run", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ view: name ?? undefined, definition: def, task, limit: 500 }),
      });
      setRows(r.records); setTotal(r.n); setActiveView(name);
      setSelId(null);
    } catch (e) { setMsg(String(e)); }
  }

  async function saveView(def: ViewDef) {
    if (!def.name.trim()) { setMsg("give the view a name first"); return; }
    try {
      await api("/api/views", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(toPayload(def)) });
      setViews((await api<{ views: View[] }>("/api/views")).views);
      setBuilding(false);
      setMsg(`saved view ${def.name}`);
    } catch (e) { setMsg(String(e)); }
  }

  async function deleteView(name: string) {
    await api(`/api/views/${name}`, { method: "DELETE" }).catch((e) => setMsg(String(e)));
    setViews((await api<{ views: View[] }>("/api/views")).views);
    if (activeView === name) { setActiveView(null); runAll(); }
  }

  return (
    <div>
      <PageHeader title="browse" desc="Filter records with saved views or build complex new ones. Click a row to label all tasks."
        actions={<>
          <select value={task} onChange={(e) => setTask(e.target.value)}>{Object.keys(tasks).map((k) => <option key={k}>{k}</option>)}</select>
          <button onClick={() => { setBuilding(!building); }}> {building ? "close builder" : "+ new view"}</button>
          <button onClick={() => setLeftOpen(!leftOpen)} title="toggle views rail">{leftOpen ? "« views" : "views »"}</button>
        </>} />
      {msg && <p className="muted">{msg}</p>}
      {building && <ViewBuilder tasks={tasks} sources={sources} onApply={(d) => applyView(null, d)} onSave={saveView} />}
      <p className="muted">{activeView ? `view “${activeView}” · ` : ""}{total} records</p>
      <div className={`browse2${leftOpen ? "" : " closed"}`}>
        {leftOpen ? (
        <div className="card detail-sticky" style={{ margin: 0 }}>
          <p className="side-title">views</p>
          <div className="btns" style={{ marginBottom: 8 }}>
            <button onClick={() => { setActiveView(null); runAll(); }}>all records</button>
          </div>
          {views.map((v) => (
            <div key={v.name} className="rec" style={{ cursor: "pointer", borderColor: activeView === v.name ? "var(--accent)" : undefined }} onClick={() => applyView(v.name)} title={v.description}>
              <div><b>{v.name}</b></div>
              <div className="muted" style={{ fontSize: 12 }}>{v.description}</div>
              <div className="btns"><button onClick={(e) => { e.stopPropagation(); deleteView(v.name); }}>delete</button></div>
            </div>
          ))}
          {views.length === 0 && <p className="muted">no saved views yet</p>}
        </div>
        ) : (
        <div className="rail detail-sticky">
          <button className="railbtn" onClick={() => setLeftOpen(true)} title="open views">views</button>
        </div>
        )}
        <div>
          <p className="muted">{activeView ? `view “${activeView}” · ` : ""}{total} records · click a row to label</p>
          <table className="grid">
            <thead><tr><th>id</th><th>text</th><th>consensus</th><th>conf</th><th>golden</th></tr></thead>
            <tbody>{rows.slice(0, 100).map((r) => (
              <tr key={r.id} className="rowlink" onClick={() => setSelId(r.id)}>
                <td className="mono muted">{r.id}</td>
                <td className="txtcell">{r.text.slice(0, 220)}…</td>
                <td>{r.agg ? <span className="pill acc">{shortLabel(r.agg.label)}</span> : <span className="muted">–</span>}</td>
                <td className="mono muted">{r.agg ? `${Math.round(100 * r.agg.confidence)}%` : "–"}</td>
                <td>{r.golden ? <span className="pill gold">{shortLabel(r.golden)}</span> : <span className="pill low">–</span>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </div>
      {selId && Object.keys(tasks).length > 0 && (
        <>
          <div className="scrim" onClick={() => setSelId(null)} />
          <div className="drawer">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="mono muted">{selId}</span>
              <button onClick={() => setSelId(null)} title="close (esc)">✕</button>
            </div>
            <AllTasks key={selId + activeView} id={selId} tasks={tasks} onSaved={() => setMsg(`saved golden for ${selId}`)} />
          </div>
        </>
      )}
    </div>
  );
}
