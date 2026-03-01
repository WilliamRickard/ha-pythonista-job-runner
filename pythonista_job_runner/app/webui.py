from __future__ import annotations

"""
Web UI generator.

Important: return a normal string, NOT a Python f-string.
Ingress proxies under a path prefix and absolute URLs break, so the UI must use relative URLs.
See HA Ingress docs: X-Ingress-Path and base URL behaviour.
"""

from typing import Optional


def html_page(addon_version: str) -> bytes:
    html_text = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Pythonista Job Runner</title>
<style>
:root{
  --bg: #0f1115;
  --panel: #141824;
  --panel2: #0b0d12;
  --line: #242c3d;
  --text: #e6e6e6;
  --muted: #b0b0b0;
  --link: #8ab4ff;
  --chip: #1f2633;
}
@media (prefers-color-scheme: light){
  :root{
    --bg: #f5f7fb;
    --panel: #ffffff;
    --panel2: #f0f3f8;
    --line: #d9e1ef;
    --text: #0d1117;
    --muted: #4b5563;
    --link: #1d4ed8;
    --chip: #eef2ff;
  }
}
body{
  font-family: -apple-system, system-ui, sans-serif;
  margin: 0;
  padding: 16px;
  background: var(--bg);
  color: var(--text);
}
a{ color: var(--link); }
h1{ margin: 0 0 6px 0; font-size: 20px; letter-spacing: 0.2px; }
small{ color: var(--muted); }
button{
  background: var(--chip);
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 8px 12px;
}
button:hover{ filter: brightness(1.05); }
button:active{ transform: translateY(1px); }
.actions{ margin-top: 12px; display:flex; gap:8px; flex-wrap: wrap; align-items:center; }
.statuschip{
  display:inline-block;
  padding:2px 10px;
  border:1px solid var(--line);
  border-radius:999px;
  background: var(--panel);
  margin-left: 6px;
}
input[type="text"], input[type="search"], input[type="number"]{
  padding:10px 12px;
  border-radius:10px;
  border:1px solid var(--line);
  background:var(--panel);
  color:var(--text);
}
table{
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
}
th, td{
  padding: 10px;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
  vertical-align: top;
}
th{
  text-align:left;
  color: var(--muted);
  font-weight: 600;
}
tr:hover{ background: rgba(120, 140, 180, 0.10); }
.badge{
  display:inline-block;
  padding:2px 10px;
  border-radius:999px;
  font-size: 12px;
  border: 1px solid var(--line);
  background: var(--chip);
}
.badge.running{ border-color: rgba(49,130,206,0.6); }
.badge.done{ border-color: rgba(31,139,76,0.6); }
.badge.error{ border-color: rgba(197,48,48,0.6); }
.rowbtn{ font-size: 12px; padding: 6px 10px; }
#empty{
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed var(--line);
  border-radius: 12px;
  background: var(--panel);
  color: var(--muted);
}
#stats{
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel);
}
.kv{ display:flex; gap:10px; flex-wrap: wrap; }
.kv .item{ padding:6px 10px; border:1px solid var(--line); border-radius:999px; background: var(--chip); font-size: 12px; color: var(--muted); }
#detail{
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
pre{
  background: var(--panel2);
  color: var(--text);
  padding: 12px;
  overflow-x: auto;
  max-height: 45vh;
  white-space: pre-wrap;
  border: 1px solid var(--line);
  border-radius: 12px;
}
textarea{
  width: 100%;
  background: var(--panel2);
  color: var(--text);
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
@media (max-width: 520px){
  th:nth-child(4), td:nth-child(4){ display:none; }
}
</style>
</head>
<body>
<h1>Pythonista Job Runner</h1>
<small>v__ADDON_VERSION__ · <span id="statusline" class="statuschip">loading…</span></small>

<div id="stats" style="display:none;">
  <div class="kv" id="stats_kv"></div>
</div>

<div class="actions">
  <button onclick="refreshAll()">Refresh</button>
  <button onclick="toggleAuto()">Auto refresh: <span id="autostate">on</span></button>
  <label style="display:flex;align-items:center;gap:6px;color:var(--muted);">
    poll <input type="number" id="pollms" min="250" max="10000" step="250" value="2000" style="width:90px;" onchange="setPollMs()"/> ms
  </label>
  <span style="flex:1 1 240px;"></span>
  <input id="search" type="search" placeholder="Search job id or user…" style="flex:1 1 220px;min-width:160px;" oninput="applyFilters()"/>
</div>
<div class="actions" style="margin-top:8px;">
  <button class="rowbtn" onclick="setView('all')">All</button>
  <button class="rowbtn" onclick="setView('running')">Running</button>
  <button class="rowbtn" onclick="setView('error')">Errors</button>
  <button class="rowbtn" onclick="setView('done')">Done</button>
  <span style="flex:1 1 240px;"></span>
  <button class="rowbtn" onclick="purgeState('done')">Purge done</button>
  <button class="rowbtn" onclick="purgeState('error')">Purge errors</button>
</div>

<table id="jobtable">
  <thead>
    <tr>
      <th>Job</th>
      <th>State</th>
      <th>Exit</th>
      <th>User</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>

<div id="empty" style="display:none;">No jobs yet. Run something from Pythonista and hit Refresh.</div>

<div id="detail" style="display:none;">
  <h2 style="font-size:16px;margin:0 0 8px 0;">Job <span id="jobid"></span></h2>
  <div class="actions" style="margin-bottom:8px;">
    <button onclick="downloadZip()">Download zip</button>
    <button onclick="downloadText('stdout')">stdout.txt</button>
    <button onclick="downloadText('stderr')">stderr.txt</button>
    <button onclick="cancelJob()">Cancel</button>
    <button onclick="deleteJob()">Delete</button>
  </div>
  <div><small id="meta"></small></div>

  <div class="actions" style="margin-top:10px;">
    <button class="rowbtn" onclick="setTab('stdout')">stdout</button>
    <button class="rowbtn" onclick="setTab('stderr')">stderr</button>
    <button class="rowbtn" onclick="setTab('overview')">overview</button>
    <span style="flex:1 1 240px;"></span>
    <label style="display:flex;align-items:center;gap:6px;color:var(--muted);">
      <input type="checkbox" id="follow" checked onchange="onFollowChange()"/> follow
    </label>
    <label style="display:flex;align-items:center;gap:6px;color:var(--muted);">
      <input type="checkbox" id="wrap" checked onchange="onWrapChange()"/> wrap
    </label>
    <label style="display:flex;align-items:center;gap:6px;color:var(--muted);">
      font <input type="range" id="font" min="11" max="18" value="13" oninput="onFontChange()"/>
    </label>
  </div>

  <div class="actions" style="margin-top:8px;">
    <input id="logsearch" type="search" placeholder="Find in log…" style="flex:1 1 220px;min-width:160px;" oninput="onLogSearch()"/>
    <button class="rowbtn" onclick="findNext()">Next</button>
    <button class="rowbtn" onclick="findPrev()">Prev</button>
    <button class="rowbtn" onclick="clearHighlights()">Clear</button>
  </div>

  <div id="overview" style="display:none;margin-top:10px;">
    <div style="padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--panel);">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
        <div style="flex:1 1 220px;"><small id="overview_text"></small></div>
        <button class="rowbtn" onclick="copyCurl()">Copy curl snippet</button>
      </div>
      <div style="margin-top:10px;">
        <textarea id="curl_snippet" rows="8" readonly></textarea>
      </div>
    </div>
  </div>

  <div id="logpanel" style="margin-top:10px;">
    <pre id="logview"></pre>
  </div>
</div>

<script>
let auto = true;
let pollMs = 2000;
let currentJob = null;
let currentTab = "stdout";
let view = "all";
let jobsCache = [];
let follow = true;
let wrap = true;
let fontSize = 13;
let logSearch = "";
let matchIdx = -1;
let matches = [];
let offsets = {stdout: 0, stderr: 0};

function qs(name) { return new URLSearchParams(window.location.search).get(name); }
function esc(s) { return (s || "").toString().replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function badge(state) { const cls = state || "queued"; return '<span class="badge ' + cls + '">' + esc(state) + '</span>'; }

async function api(path, opts) {
  const url = new URL(path, window.location.href);
  const r = await fetch(url.toString(), opts || {});
  if (!r.ok) {
    const t = await r.text();
    throw new Error(r.status + " " + t);
  }
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("application/json")) return await r.json();
  return await r.text();
}

function setPollMs(){
  const v = parseInt(document.getElementById("pollms").value || "2000", 10);
  if (!isNaN(v) && v >= 250 && v <= 10000){
    pollMs = v;
    localStorage.setItem("pjr_pollms", String(v));
  }
}

function setView(v) { view = v; localStorage.setItem("pjr_view", v); applyFilters(); }

function applyFilters() {
  const q = (document.getElementById("search")?.value || "").toLowerCase().trim();
  const filtered = jobsCache.filter(j => {
    if (view !== "all" && (j.state || "") !== view) return false;
    if (!q) return true;
    const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name)) || "";
    return (j.job_id || "").toLowerCase().includes(q) || user.toLowerCase().includes(q);
  });
  renderJobs(filtered);
}

function renderJobs(jobs) {
  const tbody = document.querySelector("#jobtable tbody");
  tbody.innerHTML = "";
  const empty = document.getElementById("empty");
  if (empty) empty.style.display = (jobs.length === 0) ? "block" : "none";
  for (const j of jobs) {
    const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name)) || "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><button class="rowbtn" onclick="selectJob('${j.job_id}')">${esc(j.job_id)}</button></td>
      <td>${badge(j.state)}</td>
      <td>${esc(j.exit_code)}</td>
      <td>${esc(user)}</td>
      <td>
        <button class="rowbtn" onclick="selectJob('${j.job_id}')">View</button>
        <a class="rowbtn" href="result/${j.job_id}.zip" target="_blank">Zip</a>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

async function refreshStats() {
  try {
    const s = await api("stats.json");
    const kv = document.getElementById("stats_kv");
    if (!kv) return;
    const items = [];
    items.push(`jobs=${s.jobs_total}`);
    items.push(`running=${s.jobs_running}`);
    items.push(`errors=${s.jobs_error}`);
    items.push(`retention_h=${s.job_retention_hours}`);
    items.push(`disk_free_mb=${Math.floor(s.disk_free_bytes/1024/1024)}`);
    items.push(`jobs_mb=${Math.floor(s.jobs_dir_bytes/1024/1024)}`);
    kv.innerHTML = items.map(t => `<div class="item">${esc(t)}</div>`).join("");
    document.getElementById("stats").style.display = "block";
  } catch (e) {
    // ignore
  }
}

async function refreshJobs() {
  try {
    const data = await api("jobs.json");
    jobsCache = data.jobs || [];
    document.getElementById("statusline").textContent = `ok (${jobsCache.length} jobs)`;
    applyFilters();
  } catch (e) {
    document.getElementById("statusline").textContent = "error: " + e.message;
  }
}

async function purgeState(state) {
  const older = prompt(`Purge '${state}' jobs older than how many hours?`, "24");
  if (older === null) return;
  const hours = parseInt(older, 10);
  if (isNaN(hours) || hours < 0) return alert("Please enter a non-negative whole number.");
  try {
    const res = await api("purge", {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({states:[state], older_than_hours: hours})});
    alert(`Deleted ${res.count} jobs`);
    await refreshAll();
  } catch (e) {
    alert("Purge failed: " + e.message);
  }
}

function setTab(t) {
  currentTab = t;
  localStorage.setItem("pjr_tab", t);
  document.getElementById("overview").style.display = (t === "overview") ? "block" : "none";
  document.getElementById("logpanel").style.display = (t === "overview") ? "none" : "block";
  const pre = document.getElementById("logview");
  if (pre && t !== "overview") pre.textContent = "";
  resetSearch();
}

function onFollowChange() { follow = !!document.getElementById("follow")?.checked; }
function onWrapChange() { wrap = !!document.getElementById("wrap")?.checked; applyLogStyle(); }
function onFontChange() { fontSize = parseInt(document.getElementById("font")?.value || "13", 10) || 13; applyLogStyle(); }

function applyLogStyle() {
  const pre = document.getElementById("logview");
  if (!pre) return;
  pre.style.whiteSpace = wrap ? "pre-wrap" : "pre";
  pre.style.fontSize = `${fontSize}px`;
}

function resetSearch() { matches = []; matchIdx = -1; }

function onLogSearch() {
  logSearch = (document.getElementById("logsearch")?.value || "").trim();
  resetSearch();
  highlightMatches();
}

function highlightMatches() {
  const pre = document.getElementById("logview");
  if (!pre) return;
  const txt = pre.textContent || "";
  if (!logSearch) return;
  const needle = logSearch.toLowerCase();
  let idx = 0;
  matches = [];
  while (true) {
    const found = txt.toLowerCase().indexOf(needle, idx);
    if (found === -1) break;
    matches.push(found);
    idx = found + needle.length;
    if (matches.length > 500) break;
  }
  matchIdx = matches.length ? 0 : -1;
  scrollToMatch();
}

function scrollToMatch() {
  const pre = document.getElementById("logview");
  if (!pre || matchIdx < 0 || matchIdx >= matches.length) return;
  const txt = pre.textContent || "";
  const before = txt.slice(0, matches[matchIdx]);
  const lines = before.split("\n").length;
  const approxLineHeight = fontSize * 1.35;
  pre.scrollTop = Math.max(0, (lines - 3) * approxLineHeight);
}

function findNext() { if (!matches.length) { highlightMatches(); return; } matchIdx = (matchIdx + 1) % matches.length; scrollToMatch(); }
function findPrev() { if (!matches.length) { highlightMatches(); return; } matchIdx = (matchIdx - 1 + matches.length) % matches.length; scrollToMatch(); }
function clearHighlights() { document.getElementById("logsearch").value = ""; logSearch = ""; resetSearch(); }

async function selectJob(job_id) {
  currentJob = job_id;
  offsets = {stdout: 0, stderr: 0};
  document.getElementById("detail").style.display = "block";
  document.getElementById("jobid").textContent = job_id;
  setTab(localStorage.getItem("pjr_tab") || "stdout");
  await refreshMetaAndTail(true);
  await refreshOverview();
}

async function refreshOverview(){
  if (!currentJob) return;
  try{
    const j = await api(`job/${currentJob}.json`);
    const st = j || {};
    const dur = (st.duration_seconds !== null && st.duration_seconds !== undefined) ? st.duration_seconds : "";
    const who = (st.submitted_by && (st.submitted_by.display_name || st.submitted_by.name)) || "";
    const ip = st.client_ip || "";
    document.getElementById("overview_text").textContent =
      `created=${st.created_utc} started=${st.started_utc} finished=${st.finished_utc} duration_s=${dur} ip=${ip} user=${who}`;

    const base = window.location.origin + window.location.pathname;
    const curl = [
      "# Direct access requires X-Runner-Token unless you are using Ingress",
      `BASE="${base.replace(/\/$/, "")}"`,
      `JOB="${currentJob}"`,
      "TOKEN=\"YOUR_TOKEN_HERE\"",
      "",
      "curl -H \"X-Runner-Token: $TOKEN\" \"$BASE/job/$JOB.json\"",
      "curl -H \"X-Runner-Token: $TOKEN\" \"$BASE/tail/$JOB.json\"",
      "curl -H \"X-Runner-Token: $TOKEN\" -L \"$BASE/result/$JOB.zip\" -o result.zip",
      "curl -H \"X-Runner-Token: $TOKEN\" -X POST \"$BASE/cancel/$JOB\"",
      "curl -H \"X-Runner-Token: $TOKEN\" -X DELETE \"$BASE/job/$JOB\"",
    ].join("\\n");
    document.getElementById("curl_snippet").value = curl;
  }catch(e){
    document.getElementById("overview_text").textContent = "overview error: " + e.message;
  }
}

async function copyCurl(){
  const t = document.getElementById("curl_snippet");
  if (!t) return;
  try{
    await navigator.clipboard.writeText(t.value);
    alert("Copied");
  }catch(e){
    // fallback
    t.select();
    document.execCommand("copy");
    alert("Copied");
  }
}

async function refreshMetaAndTail(full) {
  if (!currentJob) return;
  try {
    const data = await api(`tail/${currentJob}.json?stdout_from=${offsets.stdout}&stderr_from=${offsets.stderr}&max_bytes=65536`);
    const st = data.status || {};
    const lim = (st.limits || {});
    const cpu = lim.cpu_percent;
    const mode = lim.cpu_limit_mode;
    const eff = lim.cpu_cpulimit_pct;
    const mem = lim.mem_mb;
    const thr = lim.threads;
    document.getElementById("meta").textContent = `state=${st.state} exit=${st.exit_code} error=${st.error} cpu=${cpu} mode=${mode} eff=${eff} mem_mb=${mem} thr=${thr}`;
    if (data.offsets) {
      offsets.stdout = data.offsets.stdout_next || offsets.stdout;
      offsets.stderr = data.offsets.stderr_next || offsets.stderr;
    }
    const tail = data.tail || {};
    const pre = document.getElementById("logview");
    if (!pre || currentTab === "overview") return;

    if (full) pre.textContent = "";
    if (currentTab === "stdout") pre.textContent += (tail.stdout || "");
    if (currentTab === "stderr") pre.textContent += (tail.stderr || "");
    applyLogStyle();
    if (follow) pre.scrollTop = pre.scrollHeight;
  } catch (e) {
    document.getElementById("meta").textContent = "error: " + e.message;
  }
}

async function cancelJob() { if (!currentJob) return; await api(`cancel/${currentJob}`, {method: "POST"}); await refreshAll(); }
async function deleteJob() { if (!currentJob) return; await api(`job/${currentJob}`, {method: "DELETE"}); currentJob = null; document.getElementById("detail").style.display = "none"; await refreshAll(); }

function downloadZip() { if (!currentJob) return; window.open(`result/${currentJob}.zip`, "_blank"); }
function downloadText(which) { if (!currentJob) return; const p = (which === "stderr") ? `stderr/${currentJob}.txt` : `stdout/${currentJob}.txt`; window.open(p, "_blank"); }

function toggleAuto() { auto = !auto; document.getElementById("autostate").textContent = auto ? "on" : "off"; }

async function refreshAll(){
  await refreshStats();
  await refreshJobs();
  if (currentJob){
    await refreshMetaAndTail(false);
    await refreshOverview();
  }
}

async function tick() {
  if (auto) {
    await refreshAll();
  }
  setTimeout(tick, pollMs);
}

(async () => {
  const v = localStorage.getItem("pjr_view"); if (v) view = v;
  const p = localStorage.getItem("pjr_pollms"); if (p) { const pv = parseInt(p,10); if(!isNaN(pv)) pollMs = pv; }
  document.getElementById("pollms").value = String(pollMs);
  await refreshAll();
  const j = qs("job"); if (j) await selectJob(j);
  tick();
})();
</script>

</body>
</html>"""
    html_text = html_text.replace("__ADDON_VERSION__", addon_version)
    return html_text.encode("utf-8")

