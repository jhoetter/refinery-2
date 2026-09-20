"use client";
import { useCallback, useEffect, useState } from "react";
import { api, shortLabel, TaskDef } from "@/lib/api";
import { LabelEditor } from "@/components/editor";

type Votes = { source: string; label: unknown; confidence: number }[];
type Agg = { label: unknown; confidence: number } | null;

/** All task UIs for one record, stacked + collapsible (refinery-style).
 *  Digit keys label the first classification task. No animation on keys. */
export function AllTasks({ id, tasks, onSaved }: {
  id: string; tasks: Record<string, TaskDef>; onSaved?: () => void;
}) {
  const [data, setData] = useState<Record<string, { text: string; votes: Votes; agg: Agg; golden: unknown }>>({});
  const names = Object.keys(tasks);
  const hotkeyTask = names.find((n) => tasks[n].type === "classification");

  const load = useCallback(async () => {
    const out: typeof data = {};
    await Promise.all(names.map(async (t) => {
      const d = await api<{ record: { text: string }; votes: Votes; agg: Agg; golden: unknown }>(`/api/record/${id}?task=${t}`);
      out[t] = { text: d.record.text, votes: d.votes, agg: d.agg, golden: d.golden };
    }));
    setData(out);
  }, [id, names.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load().catch(() => {}); }, [load]);

  async function save(task: string, label: unknown) {
    await api("/api/labels", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ record_id: id, task, label }) });
    await load();
    onSaved?.();
  }

  useEffect(() => {
    if (!hotkeyTask) return;
    const h = (e: KeyboardEvent) => {
      const el = document.activeElement;
      if (el && /INPUT|TEXTAREA|SELECT/.test(el.tagName)) return;
      const labels = tasks[hotkeyTask].labels ?? [];
      const i = parseInt(e.key, 10);
      if (i >= 1 && i <= labels.length) save(hotkeyTask, labels[i - 1]).catch(() => {});
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  const text = data[names[0]]?.text ?? "";
  return (
    <div>
      <p className="labeltext">{text}</p>
      {names.map((t, i) => (
        <details key={t} open={i === 0} className="card" style={{ margin: "8px 0" }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            {t} <span className="muted">· {tasks[t].type}</span>{" "}
            {data[t]?.agg && <span className="pill acc">{shortLabel(data[t].agg!.label)}</span>}
            {data[t]?.golden !== undefined && data[t]?.golden !== null
              ? <span className="pill gold">gold {shortLabel(data[t].golden)}</span>
              : <span className="pill low">unlabeled</span>}
            {t === hotkeyTask && <span className="muted"> · keys 1–{tasks[t].labels?.length ?? 0}</span>}
          </summary>
          <div style={{ marginTop: 10 }}>
            <LabelEditor key={t + id} task={tasks[t]} text={text} golden={data[t]?.golden} onSave={(l) => save(t, l)} />
            <table className="grid" style={{ marginTop: 10 }}><tbody>
              {(data[t]?.votes ?? []).map((v, j) => <tr key={j}><td className="mono">{v.source}</td><td>{shortLabel(v.label)}</td><td>{v.confidence}</td></tr>)}
            </tbody></table>
          </div>
        </details>
      ))}
    </div>
  );
}
