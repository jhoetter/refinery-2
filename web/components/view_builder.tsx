"use client";
import { useState } from "react";
import type { TaskDef } from "@/lib/api";

export type Cond = { field: string; task: string; source: string; op: string; value: string };
export type Group = { logic: "and" | "or"; negate: boolean; conditions: Cond[] };
export type ViewDef = { name: string; description: string; logic: "and" | "or"; groups: Group[] };

const FIELDS = [
  { id: "text_contains", label: "Text contains", ops: ["contains"], task: false, value: "text" },
  { id: "text_regex", label: "Text matches regex", ops: ["regex"], task: false, value: "text" },
  { id: "agg_label", label: "Consensus label", ops: ["eq", "ne", "in"], task: true, value: "label" },
  { id: "golden", label: "Golden label", ops: ["present", "missing"], task: true, value: "none" },
  { id: "golden_label", label: "Golden label value", ops: ["eq", "ne"], task: true, value: "label" },
  { id: "confidence", label: "Confidence", ops: ["lt", "lte", "gt", "gte"], task: true, value: "number" },
  { id: "disagreement", label: "Sources disagree", ops: ["true", "false"], task: true, value: "none" },
  { id: "slice", label: "In slice", ops: ["eq", "ne"], task: false, value: "text" },
  { id: "source_label", label: "Source label", ops: ["eq", "ne"], task: true, value: "text", source: true },
] as const;

const blankCond = (task: string): Cond => ({ field: "agg_label", task, source: "", op: "eq", value: "" });

export function toPayload(v: ViewDef) {
  const conv = (c: Cond) => {
    const base: Record<string, unknown> = { field: c.field, op: c.op };
    if (c.task) base.task = c.task;
    if (c.source) base.source = c.source;
    if (!["present", "missing", "true", "false", "regex", "contains"].includes(c.op) || c.field.startsWith("text")) {
      base.value = c.op === "in" ? c.value.split(",").map((s) => s.trim()).filter(Boolean) : isNum(c.value) ? parseFloat(c.value) : c.value;
    }
    if (c.op === "true" || c.op === "false") base.value = c.op === "true";
    if (c.field === "text_contains") base.value = c.value;
    if (c.field === "text_regex") base.value = c.value;
    return base;
  };
  return { name: v.name, description: v.description, logic: v.logic, groups: v.groups.map((g) => ({ logic: g.logic, negate: g.negate, conditions: g.conditions.map(conv) })) };
}
function isNum(s: string) { return s !== "" && !isNaN(Number(s)); }

export function ViewBuilder({ tasks, sources, initial, onApply, onSave }: {
  tasks: Record<string, TaskDef>; sources: string[]; initial?: ViewDef;
  onApply: (def: Record<string, unknown>) => void; onSave: (def: ViewDef) => void;
}) {
  const firstTask = Object.keys(tasks)[0] ?? "topic";
  const [v, setV] = useState<ViewDef>(initial ?? {
    name: "", description: "", logic: "and",
    groups: [{ logic: "and", negate: false, conditions: [blankCond(firstTask)] }],
  });
  const set = (nv: ViewDef) => { setV(nv); };
  const updGroup = (gi: number, g: Group) => set({ ...v, groups: v.groups.map((x, i) => (i === gi ? g : x)) });

  return (
    <div className="card">
      <div className="row">
        <label className="flt">combine groups
          <select value={v.logic} onChange={(e) => set({ ...v, logic: e.target.value as "and" | "or" })}>
            <option value="and">AND</option><option value="or">OR</option>
          </select>
        </label>
        <button onClick={() => set({ ...v, groups: [...v.groups, { logic: "and", negate: false, conditions: [blankCond(firstTask)] }] })}>+ group</button>
      </div>
      {v.groups.map((g, gi) => (
        <div key={gi} className="card" style={{ background: "var(--bg)" }}>
          <div className="row">
            <b>Group {gi + 1}</b>
            <select value={g.logic} onChange={(e) => updGroup(gi, { ...g, logic: e.target.value as "and" | "or" })}>
              <option value="and">ALL (and)</option><option value="or">ANY (or)</option>
            </select>
            <label className="flt"><input type="checkbox" checked={g.negate} onChange={(e) => updGroup(gi, { ...g, negate: e.target.checked })} /> negate</label>
            <button onClick={() => set({ ...v, groups: v.groups.filter((_, i) => i !== gi) })}>remove</button>
            <button onClick={() => updGroup(gi, { ...g, conditions: [...g.conditions, blankCond(firstTask)] })}>+ condition</button>
          </div>
          {g.conditions.map((c, ci) => {
            const f = FIELDS.find((x) => x.id === c.field)!;
            const upd = (cc: Cond) => updGroup(gi, { ...g, conditions: g.conditions.map((x, i) => (i === ci ? cc : x)) });
            return (
              <div className="row" key={ci}>
                <select value={c.field} onChange={(e) => {
                  const nf = FIELDS.find((x) => x.id === e.target.value)!;
                  upd({ ...c, field: nf.id, op: nf.ops[0], task: nf.task ? (c.task || firstTask) : "", source: "" });
                }}>
                  {FIELDS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                </select>
                {f.task && (
                  <select value={c.task} onChange={(e) => upd({ ...c, task: e.target.value })}>
                    {Object.keys(tasks).map((t) => <option key={t}>{t}</option>)}
                  </select>
                )}
                {"source" in f && f.source && (
                  <select value={c.source} onChange={(e) => upd({ ...c, source: e.target.value })}>
                    <option value="">source…</option>{sources.map((s) => <option key={s}>{s}</option>)}
                  </select>
                )}
                <select value={c.op} onChange={(e) => upd({ ...c, op: e.target.value })}>
                  {f.ops.map((o) => <option key={o}>{o}</option>)}
                </select>
                {f.value !== "none" && (
                  tasks[c.task]?.labels && f.value === "label" ? (
                    <select value={c.value} onChange={(e) => upd({ ...c, value: e.target.value })}>
                      <option value="">label…</option>{(tasks[c.task].labels ?? []).map((l) => <option key={l}>{l}</option>)}
                    </select>
                  ) : (
                    <input value={c.value} size={f.value === "number" ? 6 : 18} placeholder={f.value === "number" ? "0.7" : f.value === "text" && c.op === "in" ? "a, b" : "value"} onChange={(e) => upd({ ...c, value: e.target.value })} />
                  )
                )}
                <button onClick={() => updGroup(gi, { ...g, conditions: g.conditions.filter((_, i) => i !== ci) })}>×</button>
              </div>
            );
          })}
        </div>
      ))}
      <div className="row">
        <button className="primary" onClick={() => onApply(toPayload(v))}>apply preview</button>
        <input value={v.name} onChange={(e) => set({ ...v, name: e.target.value })} placeholder="view name to save…" size={22} />
        <button onClick={() => onSave(v)}>save view</button>
      </div>
    </div>
  );
}
