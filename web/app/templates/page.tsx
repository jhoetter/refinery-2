"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Tpl = { template: string; name: string; description: string; tasks: string[] };

export default function Templates() {
  const [tpls, setTpls] = useState<Tpl[]>([]);
  const [prefix, setPrefix] = useState("");
  const [vibe, setVibe] = useState('{\n  "name": "my-task",\n  "type": "classification",\n  "description": "what I want",\n  "labels": ["yes", "no"],\n  "model": "api-teacher"\n}');
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api<{ templates: Tpl[] }>("/api/templates").then((t) => setTpls(t.templates)).catch((e) => setMsg(String(e)));
  }, []);

  async function apply(template: string) {
    try {
      const r = await api<{ tasks: string[] }>("/api/tasks/from-template", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template, prefix }),
      });
      setMsg(`created: ${r.tasks.join(", ")} (versioned YAML in tasks/)`);
    } catch (e) { setMsg(String(e)); }
  }

  async function vibecode() {
    try {
      const def = JSON.parse(vibe);
      const r = await api<{ task: string }>("/api/tasks", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(def),
      });
      setMsg(`vibecoded task: ${r.task}`);
    } catch (e) { setMsg(String(e)); }
  }

  return (
    <div>
      <h2>templates</h2>
      <div className="row"><label>prefix <input value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder="optional" /></label></div>
      {tpls.map((t) => (
        <div className="card" key={t.template}>
          <b>{t.name}</b> <span className="muted">{t.description}</span>
          <div>{t.tasks.map((x) => <span className="pill" key={x}>{x}</span>)}</div>
          <div className="btns"><button className="primary" onClick={() => apply(t.template)}>use template</button></div>
        </div>
      ))}
      <h3>vibecode a task (paste TaskDef JSON – or let an agent do it via MCP)</h3>
      <textarea className="txt" rows={10} value={vibe} onChange={(e) => setVibe(e.target.value)} />
      <div className="btns"><button className="primary" onClick={vibecode}>create task</button></div>
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
