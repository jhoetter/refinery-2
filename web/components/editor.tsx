"use client";
import { useState } from "react";
import type { TaskDef } from "@/lib/api";

/** Label-Studio-style editors: choices with hotkeys, span tagging with region list, extraction form. */
export function LabelEditor({ task, text, golden, onSave }: {
  task: TaskDef; text: string; golden: unknown; onSave: (l: unknown) => void;
}) {
  const [sel, setSel] = useState<number[]>([]);
  const [ent, setEnt] = useState(task.entities?.[0] ?? "");
  const [fields, setFields] = useState<Record<string, string>>((golden as Record<string, string>) ?? {});
  // NOTE: digit hotkeys are handled once in AllTasks (first classification task).

  if (task.type === "classification")
    return (
      <div>
        {(task.labels ?? []).map((l, i) => (
          <button key={l} className={`choice ${golden === l ? "picked" : ""}`} onClick={() => onSave(l)}>
            <span className="hk">{i + 1}</span> {l}
          </button>
        ))}
      </div>
    );

  if (task.type === "spans") {
    const parts = text.split(/(\s+)/);
    const starts: number[] = [];
    let pos = 0;
    for (const p of parts) { starts.push(pos); pos += p.length; }
    const toggle = (i: number) => setSel(sel.includes(i) ? sel.filter((x) => x !== i) : [...sel, i]);
    const regions = sel.filter((i) => parts[i].trim()).map((i) => ({ i, start: starts[i], end: starts[i] + parts[i].length, word: parts[i] }));
    const save = () => onSave(regions.map((r) => ({ start: r.start, end: r.end, entity: ent })));
    return (
      <div>
        <div className="row">
          <select value={ent} onChange={(e) => setEnt(e.target.value)}>{(task.entities ?? []).map((e) => <option key={e}>{e}</option>)}</select>
          <button className="primary" onClick={save}>save {regions.length} region{regions.length === 1 ? "" : "s"}</button>
          <button onClick={() => setSel([])}>clear</button>
        </div>
        <p style={{ lineHeight: 2 }}>{parts.map((w, i) => <span key={i} className={sel.includes(i) ? "tok ent" : "tok"} onClick={() => toggle(i)}>{w}</span>)}</p>
        {regions.length > 0 && <h4>regions</h4>}
        {regions.map((r) => (
          <div className="region" key={r.i}>
            <span>{ent} · “{r.word}” · {r.start}–{r.end}</span>
            <button onClick={() => toggle(r.i)}>×</button>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div>
      {(task.fields ?? []).map((f) => (
        <label key={f.name}>{f.name}<input className="txt" value={fields[f.name] ?? ""} onChange={(e) => setFields({ ...fields, [f.name]: e.target.value })} /></label>
      ))}
      <div className="btns"><button className="primary" onClick={() => onSave(fields)}>save</button></div>
    </div>
  );
}
