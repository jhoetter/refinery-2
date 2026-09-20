"use client";
import { useCallback, useEffect, useState } from "react";
import { api, TaskDef } from "@/lib/api";
import { AllTasks } from "@/components/task_sections";
import { PageHeader } from "@/components/viz";

export default function Label() {
  const [tasks, setTasks] = useState<Record<string, TaskDef>>({});
  const [task, setTask] = useState("topic");
  const [queue, setQueue] = useState<string[]>([]);
  const [idx, setIdx] = useState(0);
  const [done, setDone] = useState(0);
  const [msg, setMsg] = useState("");
  const [leftOpen, setLeftOpen] = useState(true);

  const refresh = useCallback(async () => {
    const p = await api<{ tasks: Record<string, TaskDef> }>("/api/project");
    setTasks(p.tasks);
    if (!p.tasks[task]) setTask(Object.keys(p.tasks)[0]);
    const qq = await api<{ queue: { record_id: string }[] }>(`/api/queue?task=${task}`);
    setQueue(qq.queue.map((x) => x.record_id));
    const q0 = await api<{ golden_n: number }>(`/api/quality?task=${task}`).catch(() => ({ golden_n: 0 }));
    setDone(q0.golden_n);
  }, [task]);

  useEffect(() => { refresh().then(() => setIdx(0)).catch((e) => setMsg(String(e))); }, [refresh]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const el = document.activeElement;
      if (el && /INPUT|TEXTAREA|SELECT/.test(el.tagName)) return;
      if (/^[1-9]$/.test(e.key)) return; // digits belong to the classification editor
      if (e.key === "ArrowRight") setIdx((i) => Math.min(queue.length - 1, i + 1));
      if (e.key === "ArrowLeft") setIdx((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [queue.length]);

  const cur = queue[Math.min(idx, queue.length - 1)];
  return (
    <div>
      <PageHeader title="label" desc="Keyboard-first review. All task UIs at once – digits label, arrows navigate."
        actions={<>
          <label className="flt">queue <select value={task} onChange={(e) => setTask(e.target.value)}>{Object.keys(tasks).map((k) => <option key={k}>{k}</option>)}</select></label>
          <span className="muted">{queue.length ? `${idx + 1} / ${queue.length}` : "empty 🎉"} · {done} golden</span>
          <button onClick={() => setLeftOpen(!leftOpen)} title="toggle queue rail">{leftOpen ? "« queue" : "queue »"}</button>
        </>} />
      <div className="progress" style={{ marginBottom: 14 }}><div style={{ width: `${queue.length ? Math.round(100 * idx / queue.length) : 100}%` }} /></div>
      {msg && <p className="muted">{msg}</p>}
      {!queue.length && <p className="muted">Nothing to review – teachers agree everywhere.</p>}
      {!!queue.length && cur && (
        <div className={`label3${leftOpen ? "" : " noleft"}`}>
          {leftOpen ? (
          <div className="card detail-sticky" style={{ margin: 0 }}>
            <p className="side-title">queue · {task}</p>
            <div className="queueside">
              {queue.slice(0, 200).map((id, i) => (
                <button key={id} className={`qitem${i === idx ? " on" : ""}`} onClick={() => setIdx(i)}>
                  {i + 1}. {id}
                </button>
              ))}
            </div>
          </div>
          ) : (
          <div className="rail detail-sticky">
            <button className="railbtn" onClick={() => setLeftOpen(true)} title="open queue">queue</button>
          </div>
          )}
          <div>
            <div className="row">
              <button onClick={() => setIdx((i) => Math.max(0, i - 1))}>← prev</button>
              <button onClick={() => setIdx((i) => Math.min(queue.length - 1, i + 1))}>next →</button>
              <span className="muted mono">{cur}</span>
            </div>
            <AllTasks key={cur} id={cur} tasks={tasks} onSaved={() => setMsg(`saved ✓ (←/→ navigate, 1–9 choose)`)} />
          </div>
        </div>
      )}
    </div>
  );
}
