let TASKS = {}, CUR = "topic", SEL = null, ROWS = [];

function toast(msg, ok) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = ok ? "ok" : "err";
  clearTimeout(el._t);
  el._t = setTimeout(() => el.className = "hidden", 3500);
}
window.addEventListener("unhandledrejection", e => toast("error: " + (e.reason && e.reason.message || e.reason)));

async function api(p, o) {
  let r;
  try { r = await fetch(p, o); }
  catch (e) { toast("network error: " + e.message); throw e; }
  if (!r.ok) { const t = await r.text(); toast("server: " + t); throw new Error(t); }
  return r.json();
}
function esc(s){ return String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
function short(l){ if(l==null) return "–"; if(typeof l==="string") return l; if(Array.isArray(l)) return l.length+" spans"; return Object.keys(l).slice(0,2).map(x=>x+"="+String(l[x]).slice(0,24)).join(" "); }

document.querySelectorAll("nav.tabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll("nav.tabs button").forEach(x => x.classList.remove("on"));
  b.classList.add("on");
  document.querySelectorAll(".tab").forEach(t => t.classList.add("hidden"));
  document.getElementById("tab-" + b.dataset.tab).classList.remove("hidden");
  if (b.dataset.tab === "review") loadQueue();
  if (b.dataset.tab === "sources") quality();
});

async function init() {
  const p = await api("/api/project");
  document.getElementById("proj").textContent = "· " + p.name;
  TASKS = p.tasks;
  const t = document.getElementById("task");
  t.innerHTML = Object.keys(TASKS).map(k => `<option>${k}</option>`).join("");
  t.onchange = () => { CUR = t.value; load(); };
  document.getElementById("q").oninput = load;
  document.getElementById("btn-run").onclick = async () => {
    toast("running sources…", true);
    await api("/api/run-sources", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({limit: 500})});
    toast("sources done", true);
    refresh();
  };
  document.getElementById("btn-distill").onclick = async () => {
    const mc = parseFloat(document.getElementById("minconf").value || "0.8");
    const d = await api("/api/distill", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({task:"topic", train_on:"agg", min_conf: mc})});
    document.getElementById("distill").textContent = JSON.stringify(d, null, 1);
    toast("student trained: acc " + (d.overall.accuracy ?? "–"), true);
  };
  document.addEventListener("keydown", e => {
    if (!SEL || document.getElementById("tab-browse").classList.contains("hidden")) return;
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    const t = TASKS[CUR];
    if (t.type !== "classification") return;
    const i = parseInt(e.key, 10);
    if (i >= 1 && i <= t.labels.length) saveLabel(SEL, CUR, t.labels[i-1], true);
  });
  refresh();
}

async function refresh() {
  const p = await api("/api/project");
  const q = await api("/api/quality?task=" + CUR).catch(() => null);
  const golden = q ? q.golden_n : "?";
  const queue = await api("/api/queue?task=" + CUR).catch(() => ({n: "?"}));
  document.getElementById("stats").textContent =
    `${p.n_records} records · ${Object.keys(p.tasks).length} tasks · ${golden} golden · ${queue.n} need review`;
  document.getElementById("qcount").textContent = `(${queue.n})`;
  load();
}

async function load() {
  const q = document.getElementById("q").value;
  const data = await api(`/api/records?task=${CUR}&limit=60&q=${encodeURIComponent(q)}`);
  ROWS = data.records;
  renderRows(document.getElementById("list"), ROWS, "detail");
}

function renderRows(el, rows, pane) {
  el.innerHTML = rows.map(r => {
    const agg = r.agg ? `<span class="pill">agg ${esc(short(r.agg.label))} ${r.agg.confidence}</span>` : "";
    const g = r.golden ? `<span class="pill gold">gold ${esc(short(r.golden))}</span>` : `<span class="pill low">unlabeled</span>`;
    return `<div class="rec" data-id="${r.id}"><div class="t">${esc(r.text.slice(0,180))}…</div><div>${agg} ${g}</div></div>`;
  }).join("") || `<p class="muted">no records</p>`;
  el.querySelectorAll(".rec").forEach(d => d.onclick = () => {
    el.querySelectorAll(".rec").forEach(x => x.classList.remove("sel"));
    d.classList.add("sel");
    detail(d.dataset.id, pane);
  });
}

async function loadQueue() {
  const qq = await api(`/api/queue?task=${CUR}`);
  const byId = {};
  ROWS.forEach(r => byId[r.id] = r);
  let recs = (await api(`/api/records?task=${CUR}&limit=500`)).records;
  const ids = new Set(qq.queue.map(x => x.record_id));
  recs = recs.filter(r => ids.has(r.id));
  const why = Object.fromEntries(qq.queue.map(x => [x.record_id, x.confidence]));
  const el = document.getElementById("qlist");
  el.innerHTML = recs.map(r =>
    `<div class="rec" data-id="${r.id}"><div class="t">${esc(r.text.slice(0,180))}…</div>
     <div><span class="pill low">conf ${why[r.id] ?? "–"}</span>
     ${r.votes.map(v => `<span class="pill">${v.source}: ${esc(short(v.label))}</span>`).join("")}</div></div>`
  ).join("") || `<p class="muted">nothing to review 🎉</p>`;
  el.querySelectorAll(".rec").forEach(d => d.onclick = () => {
    el.querySelectorAll(".rec").forEach(x => x.classList.remove("sel"));
    d.classList.add("sel");
    detail(d.dataset.id, "qdetail");
  });
}

async function detail(id, pane) {
  SEL = id;
  const d = await api(`/api/record/${id}?task=${CUR}`);
  const t = TASKS[CUR];
  let editor = "";
  if (t.type === "classification") {
    editor = `<div class="btns">${t.labels.map((l, i) => `<button data-l="${esc(l)}"><b>${i+1}</b> ${esc(l)}</button>`).join("")}</div>`;
  } else if (t.type === "spans") {
    const toks = d.record.text.split(/(\s+)/).map((w,i) => `<span class="tok" data-i="${i}">${esc(w)}</span>`).join("");
    editor = `<div class="row"><select id="ent">${t.entities.map(e => `<option>${e}</option>`).join("")}</select>
      <button id="save-spans">save spans</button> <button id="clear-spans">clear</button></div>
      <p class="tokp">${toks}</p><p class="muted">click tokens to tag with the selected entity</p>`;
  } else {
    editor = t.fields.map(f => `<label>${esc(f.name)}<input class="txt" id="f-${esc(f.name)}" value="${esc((d.golden||{})[f.name]||"")}"></label>`).join("")
      + `<div class="btns"><button id="save-extr">save</button></div>`;
  }
  const votes = d.votes.map(v => `<tr><td>${esc(v.source)}</td><td>${esc(short(v.label))}</td><td>${v.confidence}</td></tr>`).join("");
  document.getElementById(pane).innerHTML =
    `<h3>${id}</h3>
     <div class="editor"><h4>label as golden</h4>${editor}</div>
     <p class="fulltext">${esc(d.record.text)}</p>
     <p>agg <b>${esc(JSON.stringify(d.agg))}</b> · golden <b class="gold">${esc(JSON.stringify(d.golden))}</b></p>
     <table class="votes"><tr><th>source</th><th>label</th><th>conf</th></tr>${votes}</table>`;
  document.querySelectorAll(`#${pane} [data-l]`).forEach(b => b.onclick = () => saveLabel(id, CUR, b.dataset.l, false, pane));
  const ss = document.getElementById("save-spans");
  if (ss) {
    let sel = [];
    document.querySelectorAll(`#${pane} .tok`).forEach(el => el.onclick = () => {
      el.classList.toggle("ent"); const i = +el.dataset.i;
      sel = sel.includes(i) ? sel.filter(x => x !== i) : [...sel, i];
    });
    document.getElementById("clear-spans").onclick = () => { sel = []; document.querySelectorAll(`#${pane} .tok.ent`).forEach(e=>e.classList.remove("ent")); };
    ss.onclick = async () => {
      const parts = d.record.text.split(/(\s+)/); const starts = []; let pos = 0;
      for (const p of parts) { starts.push(pos); pos += p.length; }
      const ent = document.getElementById("ent").value;
      const spans = sel.filter(i => parts[i].trim()).map(i => ({start: starts[i], end: starts[i]+parts[i].length, entity: ent}));
      await saveLabel(id, CUR, spans, false, pane);
    };
  }
  const se = document.getElementById("save-extr");
  if (se) se.onclick = async () => {
    const label = {}; TASKS[CUR].fields.forEach(f => label[f.name] = document.getElementById("f-"+f.name).value);
    await saveLabel(id, CUR, label, false, pane);
  };
}

async function saveLabel(id, task, label, advance, pane) {
  await api("/api/labels", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({record_id:id, task, label})});
  toast("saved golden ✓", true);
  refresh();
  if (advance) {
    const ids = ROWS.map(r => r.id);
    const next = ids[ids.indexOf(id) + 1];
    if (next) detail(next, pane || "detail");
  } else {
    detail(id, pane || "detail");
  }
}

async function quality() {
  try {
    const q = await api(`/api/quality?task=${CUR}`);
    document.getElementById("quality").textContent = JSON.stringify(q, null, 1);
  } catch(e) { /* toast already shown */ }
}
init();
