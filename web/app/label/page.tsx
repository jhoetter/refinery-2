"use client";
import { useCallback, useEffect, useState } from "react";
import { api, shortLabel, TaskDef } from "@/lib/api";
import { LabelEditor } from "@/components/editor";

type Item = { id: string; text: string };

export default function Label() {
  const [tasks, setTasks] = useState<Record<string, TaskDef>>({});
  const [task, setTask] = useState("topic");
  const [queue, setQueue] = useState<string[]>([]);
  const [idx, setIdx] = useState(0);
  const [detail, setDetail] = useState<{ id: string; text: string; votes: { source: string; label: unknown; confidence: number }[]; golden: unknown } | null>(null);
  const [done, setDone] = useState(0);
  const [msg, setMsg] = useState("");

  const refresh = useCallback(async () => {
    const p = await api<{ tasks: Record<string, TaskDef> }>("/api/project");
    setTasks(p.tasks);
    const qq = await api<{ queue: { record_id: string }[] }>(`/api/queue?task=${task}`);
    setQueue(qq.queue.map((x) => x.record_id));
    const q0 = await api<{ golden_n: number }>("/api/quality?task=" + task).catch(() => ({ golden_n: 0 }));
    setDone(q0.golden_n);
  }, [task]);

  const open = useCallback(async (id: string) => {
    const d = await api<{ record: Item; votes: { source: string; label: unknown; confidence: number }[]; golden: unknown }>(`/api/record/${id}?task=${task}`);
    setDetail({ id: d.record.id, text: d.record.text, votes: d.votes, golden: d.golden });
  }, [task]);

  useEffect(() => { refresh().then(() => setIdx(0)).catch((e) => setMsg(String(e))); }, [refresh]);
  useEffect(() => { if (queue.length) open(queue[Math.min(idx, queue.length - 1)]).catch((e) => setMsg(String(e))); }, [queue, idx, open]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const el = document.activeElement;
      if (el && /INPUT|TEXTAREA|SELECT/.test(el.tagName)) return;
      if (e.key === "ArrowRight") setIdx((i) => Math.min(queue.length - 1, i + 1));
      if (e.key === "ArrowLeft") setIdx((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [queue.length]);

  async function save(label: unknown) {
    if (!detail) return;
    await api("/api/labels", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ record_id: detail.id, task, label }) });
    setDone((d) => d + (detail.golden ? 0 : 1));
    setIdx((i) => Math.min(queue.length - 1, i + 1));
    setMsg(`saved ${detail.id} ✓ (←/→ navigate, 1–9 choose)`);
  }

  const t = tasks[task];
  return (
    <div>
      <div className="row">
        <h2 style={{ margin: 0 }}>label</h2>
        <select value={task} onChange={(e) => setTask(e.target.value)}>{Object.keys(tasks).map((k) => <option key={k}>{k}</option>)}</select>
        <span className="muted">{queue.length ? `${idx + 1} / ${queue.length} in queue` : "queue empty 🎉"} · {done} golden total</span>
      </div>
      <div className="progress" style={{ marginBottom: 14 }}><div style={{ width: `${queue.length ? Math.round(100 * idx / queue.length) : 100}%` }} /></div>
      {msg && <p className="muted">{msg}</p>}
      {!queue.length && <p className="muted">Nothing to review – teachers agree everywhere.</p>}
      {!!queue.length && detail && t && (
        <div className="split">
          <div>
            <p className="labeltext">{detail.text}</p>
            <div className="row">
              <button onClick={() => setIdx((i) => Math.max(0, i - 1))}>← prev</button>
              <button onClick={() => setIdx((i) => Math.min(queue.length - 1, i + 1))}>next →</button>
              <span className="muted mono">{detail.id}</span>
            </div>
            <table className="grid"><tbody>{detail.votes.map((v, i) => <tr key={i}><td className="mono">{v.source}</td><td>{shortLabel(v.label)}</td><td>{v.confidence}</td></tr>)}</tbody></table>
          </div>
          <div className="card">
            <h4>your label {detail.golden ? <span className="pill gold">golden: {shortLabel(detail.golden)}</span> : null}</h4>
            <LabelEditor key={task + detail.id} task={t} text={detail.text} golden={detail.golden} onSave={save} />
          </div>
        </div>
      )}
    </div>
  );
}
