let TASKS = {}, CUR = "topic", SEL = null;

async function api(p, o) {
  const r = await fetch(p, o);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
async function init() {
  const p = await api("/api/project");
  document.getElementById("proj").textContent = "· " + p.name + " · " + p.n_records + " records";
  TASKS = p.tasks;
  const t = document.getElementById("task");
  t.innerHTML = Object.keys(TASKS).map(k => `<option>${k}</option>`).join("");
  t.onchange = () => { CUR = t.value; load(); };
  document.getElementById("view").onchange = load;
  document.getElementById("q").oninput = load;
  document.getElementById("btn-run").onclick = async () => {
    await api("/api/run-sources", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({limit: 500})});
    load(); quality();
  };
  document.getElementById("btn-distill").onclick = async () => {
    const d = await api("/api/distill", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({task:"topic", train_on:"agg"})});
    document.getElementById("distill").textContent = JSON.stringify(d, null, 1);
  };
  load(); quality();
}
async function load() {
  const q = document.getElementById("q").value;
  let data;
  if (document.getElementById("view").value === "queue") {
    const qq = await api(`/api/queue?task=${CUR}`);
    const ids = new Set(qq.queue.map(x => x.record_id));
    data = await api(`/api/records?task=${CUR}&limit=500`);
    data.records = data.records.filter(r => ids.has(r.id));
  } else {
    data = await api(`/api/records?task=${CUR}&limit=30&q=${encodeURIComponent(q)}`);
  }
  const el = document.getElementById("list");
  el.innerHTML = data.records.map(r => {
    const votes = r.votes.map(v => `<span class="pill">${v.source}: ${esc(short(v.label))} (${v.confidence})</span>`).join("");
    const agg = r.agg ? `<span class="pill">agg: ${esc(short(r.agg.label))}</span>` : "";
    const g = r.golden ? `<span class="pill gold">gold: ${esc(short(r.golden))}</span>` : `<span class="pill low">no gold</span>`;
    return `<div class="rec" data-id="${r.id}"><div class="t">${esc(r.text.slice(0,220))}…</div>${votes}<br>${agg} ${g}</div>`;
  }).join("");
  el.querySelectorAll(".rec").forEach(d => d.onclick = () => detail(d.dataset.id));
}
function short(l){ if(l==null) return "–"; if(typeof l==="string") return l; if(Array.isArray(l)) return l.length+" spans"; const k=Object.keys(l); return k.slice(0,2).map(x=>x+"="+String(l[x]).slice(0,24)).join(" "); }
function esc(s){ return String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
async function detail(id) {
  SEL = id;
  const d = await api(`/api/record/${id}?task=${CUR}`);
  const t = TASKS[CUR];
  let editor = "";
  if (t.type === "classification") {
    editor = `<div class="btns">${t.labels.map(l => `<button data-l="${l}">${l}</button>`).join("")}</div>`;
  } else if (t.type === "spans") {
    const toks = d.record.text.split(/(\s+)/).map((w,i) => `<span class="tok" data-i="${i}">${esc(w)}</span>`).join("");
    editor = `<p class="muted">click tokens to toggle ORG, then save:</p><p>${toks}</p><div class="btns"><button id="save-spans">save spans</button> <button id="clear-spans">clear</button></div>`;
  } else {
    const f = t.fields.map(f => `<label>${f.name}<input class="txt" id="f-${f.name}" value="${esc((d.golden||{})[f.name]||"")}"></label>`).join("");
    editor = `${f}<div class="btns"><button id="save-extr">save extraction</button></div>`;
  }
  document.getElementById("detail").innerHTML =
    `<h3>${id} · ${CUR}</h3><p>${esc(d.record.text)}</p>
     <p class="muted">votes: ${esc(JSON.stringify(d.votes))}</p>
     <p>agg: <b>${esc(JSON.stringify(d.agg))}</b> · golden: <b class="gold">${esc(JSON.stringify(d.golden))}</b></p>
     <h3>label as golden (ground truth)</h3>${editor}`;
  document.querySelectorAll("#detail [data-l]").forEach(b => b.onclick = async () => {
    await api("/api/labels", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({record_id:id, task:CUR, label:b.dataset.l})});
    detail(id); load(); quality();
  });
  const ss = document.getElementById("save-spans");
  if (ss) {
    let sel = new Set();
    document.querySelectorAll(".tok").forEach(el => el.onclick = () => { el.classList.toggle("ent"); const i=+el.dataset.i; sel.has(i)?sel.delete(i):sel.add(i); });
    document.getElementById("clear-spans").onclick = () => { sel.clear(); document.querySelectorAll(".tok.ent").forEach(e=>e.classList.remove("ent")); };
    ss.onclick = async () => {
      const text = d.record.text; let off = 0; const idx=[]; const parts = text.split(/(\s+)/);
      let pos = 0; const starts = [];
      for (const p of parts) { starts.push(pos); pos += p.length; }
      const spans = [...sel].filter(i => parts[i].trim()).map(i => ({start: starts[i], end: starts[i]+parts[i].length, entity:"ORG"}));
      await api("/api/labels", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({record_id:id, task:CUR, label:spans})});
      detail(id); load();
    };
  }
  const se = document.getElementById("save-extr");
  if (se) se.onclick = async () => {
    const label = {}; TASKS[CUR].fields.forEach(f => label[f.name] = document.getElementById("f-"+f.name).value);
    await api("/api/labels", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({record_id:id, task:CUR, label})});
    detail(id); load(); quality();
  };
}
async function quality() {
  try {
    const q = await api(`/api/quality?task=${CUR}`);
    document.getElementById("quality").textContent = JSON.stringify(q, null, 1);
  } catch(e) { document.getElementById("quality").textContent = String(e); }
}
init();
