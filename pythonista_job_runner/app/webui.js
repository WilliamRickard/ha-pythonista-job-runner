/* webui.js - extracted from webui.html to enable Home Assistant Ingress-safe asset loading */

(() => {
  "use strict";

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
  let offsets = { stdout: 0, stderr: 0 };

  const LOG_MAX_CHARS = 2_000_000;

  function qs(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function badge(state) {
    const cls = state || "queued";
    const span = document.createElement("span");
    span.className = `badge ${cls}`;
    span.textContent = cls;
    return span;
  }

  async function api(path, opts) {
    const url = new URL(path, window.location.href);
    const r = await fetch(url.toString(), opts || {});
    if (!r.ok) {
      const t = await r.text();
      throw new Error(`${r.status} ${t}`);
    }
    const ct = r.headers.get("content-type") || "";
    if (ct.includes("application/json")) return await r.json();
    return await r.text();
  }

  function $id(id) {
    return document.getElementById(id);
  }

  function setPollMs() {
    const el = $id("pollms");
    const v = parseInt((el && el.value) || "2000", 10);
    if (!Number.isNaN(v) && v >= 250 && v <= 10000) {
      pollMs = v;
      localStorage.setItem("pjr_pollms", String(v));
    }
  }

  function setView(v) {
    view = v;
    localStorage.setItem("pjr_view", v);
    applyFilters();
  }

  function applyFilters() {
    const q = (($id("search") && $id("search").value) || "").toLowerCase().trim();
    const filtered = jobsCache.filter((j) => {
      if (view !== "all" && (j.state || "") !== view) return false;
      if (!q) return true;
      const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name)) || "";
      return (j.job_id || "").toLowerCase().includes(q) || user.toLowerCase().includes(q);
    });
    renderJobs(filtered);
  }

  function renderJobs(jobs) {
    const tbody = document.querySelector("#jobtable tbody");
    if (!tbody) return;
    tbody.textContent = "";

    const empty = $id("empty");
    if (empty) empty.style.display = jobs.length === 0 ? "block" : "none";

    const frag = document.createDocumentFragment();

    for (const j of jobs) {
      const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name)) || "";
      const jobId = j.job_id || "";
      const jobIdEnc = encodeURIComponent(jobId);

      const tr = document.createElement("tr");

      const tdJob = document.createElement("td");
      const btnJob = document.createElement("button");
      btnJob.className = "rowbtn";
      btnJob.type = "button";
      btnJob.textContent = jobId;
      btnJob.addEventListener("click", () => selectJob(jobId));
      tdJob.appendChild(btnJob);

      const tdState = document.createElement("td");
      tdState.appendChild(badge(j.state));

      const tdExit = document.createElement("td");
      tdExit.textContent = (j.exit_code ?? "").toString();

      const tdUser = document.createElement("td");
      tdUser.textContent = user;

      const tdActions = document.createElement("td");
      const btnView = document.createElement("button");
      btnView.className = "rowbtn";
      btnView.type = "button";
      btnView.textContent = "View";
      btnView.addEventListener("click", () => selectJob(jobId));

      const aZip = document.createElement("a");
      aZip.className = "rowbtn";
      aZip.textContent = "Zip";
      aZip.href = `result/${jobIdEnc}.zip`;
      aZip.target = "_blank";
      aZip.rel = "noopener noreferrer";

      tdActions.append(btnView, document.createTextNode(" "), aZip);

      tr.append(tdJob, tdState, tdExit, tdUser, tdActions);
      frag.appendChild(tr);
    }

    tbody.appendChild(frag);
  }

  async function refreshStats() {
    try {
      const s = await api("stats.json");
      const kv = $id("stats_kv");
      const stats = $id("stats");
      if (!kv || !stats) return;

      const items = [];
      items.push(`jobs=${s.jobs_total}`);
      items.push(`running=${s.jobs_running}`);
      items.push(`errors=${s.jobs_error}`);
      items.push(`retention_h=${s.job_retention_hours}`);
      items.push(`disk_free_mb=${Math.floor(s.disk_free_bytes / 1024 / 1024)}`);
      items.push(`jobs_mb=${Math.floor(s.jobs_dir_bytes / 1024 / 1024)}`);

      kv.textContent = "";
      const frag = document.createDocumentFragment();
      for (const t of items) {
        const d = document.createElement("div");
        d.className = "item";
        d.textContent = t;
        frag.appendChild(d);
      }
      kv.appendChild(frag);
      stats.style.display = "block";
    } catch (e) {
      // ignore
    }
  }

  async function refreshJobs() {
    try {
      const data = await api("jobs.json");
      jobsCache = data.jobs || [];
      const status = $id("statusline");
      if (status) status.textContent = `ok (${jobsCache.length} jobs)`;
      applyFilters();
    } catch (e) {
      const status = $id("statusline");
      if (status) status.textContent = `error: ${e.message}`;
    }
  }

  async function purgeState(state) {
    const older = prompt(`Purge '${state}' jobs older than how many hours?`, "24");
    if (older === null) return;
    const hours = parseInt(older, 10);
    if (Number.isNaN(hours) || hours < 0) {
      alert("Please enter a non-negative whole number.");
      return;
    }
    try {
      const res = await api("purge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ states: [state], older_than_hours: hours }),
      });
      alert(`Deleted ${res.count} jobs`);
      await refreshAll();
    } catch (e) {
      alert(`Purge failed: ${e.message}`);
    }
  }

  function setTab(t) {
    currentTab = t;
    localStorage.setItem("pjr_tab", t);
    const overview = $id("overview");
    const logpanel = $id("logpanel");
    if (overview) overview.style.display = t === "overview" ? "block" : "none";
    if (logpanel) logpanel.style.display = t === "overview" ? "none" : "block";
    const pre = $id("logview");
    if (pre && t !== "overview") pre.textContent = "";
    resetSearch();
  }

  function onFollowChange() {
    const el = $id("follow");
    follow = !!(el && el.checked);
  }

  function onWrapChange() {
    const el = $id("wrap");
    wrap = !!(el && el.checked);
    applyLogStyle();
  }

  function onFontChange() {
    const el = $id("font");
    const v = parseInt((el && el.value) || "13", 10);
    fontSize = Number.isNaN(v) ? 13 : v;
    applyLogStyle();
  }

  function applyLogStyle() {
    const pre = $id("logview");
    if (!pre) return;
    pre.style.whiteSpace = wrap ? "pre-wrap" : "pre";
    pre.style.fontSize = `${fontSize}px`;
  }

  function resetSearch() {
    matches = [];
    matchIdx = -1;
  }

  function onLogSearch() {
    const el = $id("logsearch");
    logSearch = ((el && el.value) || "").trim();
    resetSearch();
    computeMatches();
  }

  function computeMatches() {
    const pre = $id("logview");
    if (!pre) return;
    const txt = pre.textContent || "";
    if (!logSearch) return;
    const needle = logSearch.toLowerCase();
    const hay = txt.toLowerCase();

    let idx = 0;
    matches = [];
    while (true) {
      const found = hay.indexOf(needle, idx);
      if (found === -1) break;
      matches.push(found);
      idx = found + needle.length;
      if (matches.length > 500) break;
    }
    matchIdx = matches.length ? 0 : -1;
    scrollToMatch();
  }

  function scrollToMatch() {
    const pre = $id("logview");
    if (!pre || matchIdx < 0 || matchIdx >= matches.length) return;
    const txt = pre.textContent || "";
    const before = txt.slice(0, matches[matchIdx]);
    const lines = before.split("\n").length;
    const approxLineHeight = fontSize * 1.35;
    pre.scrollTop = Math.max(0, (lines - 3) * approxLineHeight);
  }

  function findNext() {
    if (!matches.length) {
      computeMatches();
      return;
    }
    matchIdx = (matchIdx + 1) % matches.length;
    scrollToMatch();
  }

  function findPrev() {
    if (!matches.length) {
      computeMatches();
      return;
    }
    matchIdx = (matchIdx - 1 + matches.length) % matches.length;
    scrollToMatch();
  }

  function clearHighlights() {
    const el = $id("logsearch");
    if (el) el.value = "";
    logSearch = "";
    resetSearch();
  }

  async function selectJob(jobId) {
    currentJob = jobId;
    offsets = { stdout: 0, stderr: 0 };
    const detail = $id("detail");
    if (detail) detail.style.display = "block";
    const jobid = $id("jobid");
    if (jobid) jobid.textContent = jobId;
    setTab(localStorage.getItem("pjr_tab") || "stdout");
    await refreshMetaAndTail(true);
    await refreshOverview();
  }

  async function refreshOverview() {
    if (!currentJob) return;
    try {
      const st = (await api(`job/${encodeURIComponent(currentJob)}.json`)) || {};
      const dur = st.duration_seconds !== null && st.duration_seconds !== undefined ? st.duration_seconds : "";
      const who = (st.submitted_by && (st.submitted_by.display_name || st.submitted_by.name)) || "";
      const ip = st.client_ip || "";
      const ot = $id("overview_text");
      if (ot) {
        ot.textContent = `created=${st.created_utc} started=${st.started_utc} finished=${st.finished_utc} duration_s=${dur} ip=${ip} user=${who}`;
      }

      const base = window.location.origin + window.location.pathname;
      const curl = [
        "# Direct access requires X-Runner-Token unless you are using Ingress",
        `BASE=\"${base.replace(/\/$/, "")}\"`,
        `JOB=\"${currentJob}\"`,
        "TOKEN=\"YOUR_TOKEN_HERE\"",
        "",
        "curl -H \"X-Runner-Token: $TOKEN\" \"$BASE/job/$JOB.json\"",
        "curl -H \"X-Runner-Token: $TOKEN\" \"$BASE/tail/$JOB.json\"",
        "curl -H \"X-Runner-Token: $TOKEN\" -L \"$BASE/result/$JOB.zip\" -o result.zip",
        "curl -H \"X-Runner-Token: $TOKEN\" -X POST \"$BASE/cancel/$JOB\"",
        "curl -H \"X-Runner-Token: $TOKEN\" -X DELETE \"$BASE/job/$JOB\"",
      ].join("\n");
      const ta = $id("curl_snippet");
      if (ta) ta.value = curl;
    } catch (e) {
      const ot = $id("overview_text");
      if (ot) ot.textContent = `overview error: ${e.message}`;
    }
  }

  async function copyCurl() {
    const t = $id("curl_snippet");
    if (!t) return;
    try {
      await navigator.clipboard.writeText(t.value);
      alert("Copied");
    } catch (e) {
      t.select();
      document.execCommand("copy");
      alert("Copied");
    }
  }

  function appendLog(pre, chunk) {
    if (!pre || !chunk) return;
    pre.textContent += chunk;
    if (pre.textContent.length > LOG_MAX_CHARS) {
      pre.textContent = pre.textContent.slice(-LOG_MAX_CHARS);
    }
  }

  async function refreshMetaAndTail(full) {
    if (!currentJob) return;
    try {
      const data = await api(
        `tail/${encodeURIComponent(currentJob)}.json?stdout_from=${offsets.stdout}&stderr_from=${offsets.stderr}&max_bytes=65536`,
      );
      const st = data.status || {};
      const lim = st.limits || {};

      const cpu = lim.cpu_percent;
      const mode = lim.cpu_limit_mode;
      const eff = lim.cpu_cpulimit_pct;
      const mem = lim.mem_mb;
      const thr = lim.threads;

      const meta = $id("meta");
      if (meta) {
        meta.textContent = `state=${st.state} exit=${st.exit_code} error=${st.error} cpu=${cpu} mode=${mode} eff=${eff} mem_mb=${mem} thr=${thr}`;
      }

      if (data.offsets) {
        offsets.stdout = data.offsets.stdout_next || offsets.stdout;
        offsets.stderr = data.offsets.stderr_next || offsets.stderr;
      }

      const tail = data.tail || {};
      const pre = $id("logview");
      if (!pre || currentTab === "overview") return;

      if (full) pre.textContent = "";
      if (currentTab === "stdout") appendLog(pre, tail.stdout || "");
      if (currentTab === "stderr") appendLog(pre, tail.stderr || "");

      applyLogStyle();
      if (follow) pre.scrollTop = pre.scrollHeight;
    } catch (e) {
      const meta = $id("meta");
      if (meta) meta.textContent = `error: ${e.message}`;
    }
  }

  async function cancelJob() {
    if (!currentJob) return;
    await api(`cancel/${encodeURIComponent(currentJob)}`, { method: "POST" });
    await refreshAll();
  }

  async function deleteJob() {
    if (!currentJob) return;
    await api(`job/${encodeURIComponent(currentJob)}`, { method: "DELETE" });
    currentJob = null;
    const detail = $id("detail");
    if (detail) detail.style.display = "none";
    await refreshAll();
  }

  function openBlank(url) {
    const w = window.open(url, "_blank", "noopener");
    if (w) w.opener = null;
  }

  function downloadZip() {
    if (!currentJob) return;
    openBlank(`result/${encodeURIComponent(currentJob)}.zip`);
  }

  function downloadText(which) {
    if (!currentJob) return;
    const p = which === "stderr" ? `stderr/${encodeURIComponent(currentJob)}.txt` : `stdout/${encodeURIComponent(currentJob)}.txt`;
    openBlank(p);
  }

  function toggleAuto() {
    auto = !auto;
    const el = $id("autostate");
    if (el) el.textContent = auto ? "on" : "off";
  }

  async function refreshAll() {
    await refreshStats();
    await refreshJobs();
    if (currentJob) {
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

  function bindEvents() {
    const refreshBtn = $id("refreshBtn");
    if (refreshBtn) refreshBtn.addEventListener("click", () => refreshAll());

    const autoBtn = $id("autoBtn");
    if (autoBtn) autoBtn.addEventListener("click", () => toggleAuto());

    const poll = $id("pollms");
    if (poll) poll.addEventListener("change", () => setPollMs());

    const search = $id("search");
    if (search) search.addEventListener("input", () => applyFilters());

    document.querySelectorAll("[data-view]").forEach((btn) => {
      btn.addEventListener("click", () => setView(btn.getAttribute("data-view")));
    });

    document.querySelectorAll("[data-purge-state]").forEach((btn) => {
      btn.addEventListener("click", () => purgeState(btn.getAttribute("data-purge-state")));
    });

    const dlZip = $id("dlZip");
    if (dlZip) dlZip.addEventListener("click", () => downloadZip());
    const dlStdout = $id("dlStdout");
    if (dlStdout) dlStdout.addEventListener("click", () => downloadText("stdout"));
    const dlStderr = $id("dlStderr");
    if (dlStderr) dlStderr.addEventListener("click", () => downloadText("stderr"));
    const cancel = $id("cancelBtn");
    if (cancel) cancel.addEventListener("click", () => cancelJob());
    const del = $id("deleteBtn");
    if (del) del.addEventListener("click", () => deleteJob());

    document.querySelectorAll("[data-tab]").forEach((btn) => {
      btn.addEventListener("click", () => setTab(btn.getAttribute("data-tab")));
    });

    const followEl = $id("follow");
    if (followEl) followEl.addEventListener("change", () => onFollowChange());
    const wrapEl = $id("wrap");
    if (wrapEl) wrapEl.addEventListener("change", () => onWrapChange());
    const fontEl = $id("font");
    if (fontEl) fontEl.addEventListener("input", () => onFontChange());

    const logSearchEl = $id("logsearch");
    if (logSearchEl) logSearchEl.addEventListener("input", () => onLogSearch());
    const next = $id("findNext");
    if (next) next.addEventListener("click", () => findNext());
    const prev = $id("findPrev");
    if (prev) prev.addEventListener("click", () => findPrev());
    const clear = $id("clearSearch");
    if (clear) clear.addEventListener("click", () => clearHighlights());

    const copy = $id("copyCurl");
    if (copy) copy.addEventListener("click", () => copyCurl());
  }

  async function init() {
    const v = localStorage.getItem("pjr_view");
    if (v) view = v;

    const p = localStorage.getItem("pjr_pollms");
    if (p) {
      const pv = parseInt(p, 10);
      if (!Number.isNaN(pv)) pollMs = pv;
    }

    const poll = $id("pollms");
    if (poll) poll.value = String(pollMs);

    bindEvents();
    applyLogStyle();

    await refreshAll();

    const j = qs("job");
    if (j) await selectJob(j);

    tick();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => void init());
  } else {
    void init();
  }
})();
