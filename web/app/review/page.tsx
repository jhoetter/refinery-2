"use client";
import { useCallback, useEffect, useState } from "react";
import { api, shortLabel, TaskDef } from "@/lib/api";

type Rec = { id: string; text: string; votes: { source: string; label: unknown; confidence: number }[]; agg: { label: unknown; confidence: number } | null; golden: unknown };

export default function Review() {
  const [tasks, setTasks] = useState<Record<string, TaskDef>>({});
  const [task, setTask] = useState("topic");
  const [q, setQ] = useState("");
  const [queueOnly, setQueueOnly] = useState(false);
  const [rows, setRows] = useState<Rec[]>([]);
  const [sel, setSel] = useState<Rec & { full?: string } | null>(null);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    const p = await api<{ tasks: Record<string, TaskDef> }>("/api/project");
    setTasks(p.tasks);
    let recs: Rec[];
    if (queueOnly) {
      const qq = await api<{ queue: { record_id: string }[] }>(`/api/queue?task=${task}`);
      const ids = new Set(qq.queue.map((x) => x.record_id));
      const all = await api<{ records: Rec[] }>(`/api/records?task=${task}&limit=500`);
      recs = all.records.filter((r) => ids.has(r.id));
    } else {
      const d = await api<{ records: Rec[] }>(`/api/records?task=${task}&limit=60&q=${encodeURIComponent(q)}`);
      recs = d.records;
    }
    setRows(recs);
  }, [task, q, queueOnly]);

  useEffect(() => { load().catch((e) => setMsg(String(e))); }, [load]);

  async function open(id: string) {
    const d = await api<{ record: { id: string; text: string }; votes: Rec["votes"]; agg: Rec["agg"]; golden: unknown }>(`/api/record/${id}?task=${task}`);
    setSel({ id: d.record.id, text: d.record.text, votes: d.votes, agg: d.agg, golden: d.golden, full: d.record.text });
  }

  async function save(label: unknown) {
    if (!sel) return;
    await api("/api/labels", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ record_id: sel.id, task, label }) });
    setMsg(`saved golden for ${sel.id}`);
    load().then(() => open(sel.id)).catch(() => {});
  }

  const t = tasks[task];

  return (
    <div>
      <div className="row">
        <select value={task} onChange={(e) => setTask(e.target.value)}>{Object.keys(tasks).map((k) => <option key={k}>{k}</option>)}</select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="search…" />
        <label><input type="checkbox" checked={queueOnly} onChange={(e) => setQueueOnly(e.target.checked)} /> needs review only</label>
      </div>
      {msg && <p className="muted">{msg}</p>}
      <div className="split">
        <div>
          {rows.map((r) => (
            <div key={r.id} className="rec" onClick={() => open(r.id)}>
              <div className="t">{r.text.slice(0, 180)}…</div>
              <div>{r.agg && <span className="pill">agg {shortLabel(r.agg.label)}</span>}{r.golden ? <span className="pill gold">gold {shortLabel(r.golden)}</span> : <span className="pill low">unlabeled</span>}</div>
            </div>
          ))}
        </div>
        <div>
          {!sel && <p className="muted">Select a record to label it.</p>}
          {sel && t && (
            <div className="card">
              <h3>{sel.id}</h3>
              <h4>label as golden</h4>
              <Editor key={t.name} task={t} text={sel.full ?? sel.text} golden={sel.golden} onSave={save} />
              <p>{sel.full}</p>
              <p>agg <b>{JSON.stringify(sel.agg)}</b> · golden <b className="gold">{JSON.stringify(sel.golden)}</b></p>
              <table className="grid"><tbody>{sel.votes.map((v, i) => <tr key={i}><td>{v.source}</td><td>{shortLabel(v.label)}</td><td>{v.confidence}</td></tr>)}</tbody></table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Editor({ task, text, golden, onSave }: { task: TaskDef; text: string; golden: unknown; onSave: (l: unknown) => void }) {
  const [sel, setSel] = useState<number[]>([]);
  const [ent, setEnt] = useState(task.entities?.[0] ?? "");
  const [fields, setFields] = useState<Record<string, string>>((golden as Record<string, string>) ?? {});

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (task.type !== "classification") return;
      const el = document.activeElement;
      if (el && /INPUT|TEXTAREA|SELECT/.test(el.tagName)) return;
      const i = parseInt(e.key, 10);
      if (i >= 1 && task.labels && i <= task.labels.length) onSave(task.labels[i - 1]);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [task, onSave]);

  if (task.type === "classification")
    return <div className="btns">{(task.labels ?? []).map((l, i) => <button key={l} onClick={() => onSave(l)}><b>{i + 1}</b> {l}</button>)}</div>;
  if (task.type === "spans") {
    const parts = text.split(/(\s+)/);
    const starts: number[] = [];
    let pos = 0;
    for (const p of parts) { starts.push(pos); pos += p.length; }
    const toggle = (i: number) => setSel(sel.includes(i) ? sel.filter((x) => x !== i) : [...sel, i]);
    const save = () => onSave(sel.filter((i) => parts[i].trim()).map((i) => ({ start: starts[i], end: starts[i] + parts[i].length, entity: ent })));
    return (
      <div>
        <div className="row">
          <select value={ent} onChange={(e) => setEnt(e.target.value)}>{(task.entities ?? []).map((e) => <option key={e}>{e}</option>)}</select>
          <button onClick={save}>save spans</button>
          <button onClick={() => setSel([])}>clear</button>
        </div>
        <p style={{ lineHeight: 1.9 }}>{parts.map((w, i) => <span key={i} className={sel.includes(i) ? "tok ent" : "tok"} onClick={() => toggle(i)}>{w}</span>)}</p>
      </div>
    );
  }
  return (
    <div>
      {(task.fields ?? []).map((f) => (
        <label key={f.name}>{f.name}<input className="txt" value={fields[f.name] ?? ""} onChange={(e) => setFields({ ...fields, [f.name]: e.target.value })} /></label>
      ))}
      <div className="btns"><button onClick={() => onSave(fields)}>save</button></div>
    </div>
  );
}
