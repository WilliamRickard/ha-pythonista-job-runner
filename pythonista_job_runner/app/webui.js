/* VERSION: 0.6.5 */
/* eslint-disable no-alert */
(() => {
  "use strict";

  const LOG_MAX_CHARS = 2_000_000;

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

  const offsets = { stdout: 0, stderr: 0 };
  const buffers = { stdout: "", stderr: "" };

  const els = {};

  function qs(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function apiUrl(path) {
    return new URL(path, window.location.href).toString();
  }

  async function api(path, opts) {
    const r = await fetch(apiUrl(path), opts || {});
    if (!r.ok) {
      const t = await r.text();
      throw new Error(`${r.status} ${t}`);
    }
    const ct = r.headers.get("content-type") || "";
    if (ct.includes("application/json")) return await r.json();
    return await r.text();
  }

  function clampInt(v, min, max, fallback) {
    const n = parseInt(String(v ?? ""), 10);
    if (Number.isNaN(n)) return fallback;
    return Math.max(min, Math.min(max, n));
  }

  function setPollMsFromInput() {
    pollMs = clampInt(els.pollms.value, 250, 10_000, pollMs);
    els.pollms.value = String(pollMs);
    localStorage.setItem("pjr_pollms", String(pollMs));
  }

  function setView(next) {
    view = next;
    localStorage.setItem("pjr_view", next);
    applyFilters();
  }

  function setTab(next) {
    currentTab = next;
    localStorage.setItem("pjr_tab", next);

    els.overview.hidden = (next !== "overview");
    els.logpanel.style.display = (next === "overview") ? "none" : "block";

    if (next === "overview") {
      resetSearch();
      return;
    }

    els.logview.textContent = buffers[next] || "";
    applyLogStyle();

    if (follow) {
      els.logview.scrollTop = els.logview.scrollHeight;
    }

    resetSearch();
    highlightMatches();
  }

  function toggleAuto() {
    auto = !auto;
    els.autostate.textContent = auto ? "on" : "off";
  }

  function applyFilters() {
    const q = (els.search.value || "").toLowerCase().trim();
    const filtered = jobsCache.filter((j) => {
      if (view !== "all" && (j.state || "") !== view) return false;
      if (!q) return true;
      const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name)) || "";
      return (j.job_id || "").toLowerCase().includes(q) || user.toLowerCase().includes(q);
    });
    renderJobs(filtered);
  }

  function badgeEl(state) {
    const cls = state || "queued";
    const span = document.createElement("span");
    span.className = `badge ${cls}`;
    span.textContent = cls;
    return span;
  }

  function renderJobs(jobs) {
    const tbody = els.jobtable_tbody;
    tbody.textContent = "";
    els.empty.hidden = (jobs.length !== 0);

    const frag = document.createDocumentFragment();

    for (const j of jobs) {
      const jobId = j.job_id || "";
      const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name)) || "";

      const tr = document.createElement("tr");

      const tdJob = document.createElement("td");
      const btnJob = document.createElement("button");
      btnJob.type = "button";
      btnJob.className = "rowbtn";
      btnJob.textContent = jobId;
      btnJob.addEventListener("click", () => selectJob(jobId));
      tdJob.appendChild(btnJob);

      const tdState = document.createElement("td");
      tdState.appendChild(badgeEl(j.state));

      const tdExit = document.createElement("td");
      tdExit.textContent = (j.exit_code === null || j.exit_code === undefined) ? "" : String(j.exit_code);

      const tdUser = document.createElement("td");
      tdUser.textContent = user;

      const tdActions = document.createElement("td");

      const btnView = document.createElement("button");
      btnView.type = "button";
      btnView.className = "rowbtn";
      btnView.textContent = "View";
      btnView.addEventListener("click", () => selectJob(jobId));

      const zip = document.createElement("a");
      zip.className = "rowbtn";
      zip.textContent = "Zip";
      zip.href = `result/${encodeURIComponent(jobId)}.zip`;
      zip.target = "_blank";
      zip.rel = "noopener noreferrer";

      tdActions.append(btnView, document.createTextNode(" "), zip);

      tr.append(tdJob, tdState, tdExit, tdUser, tdActions);
      frag.appendChild(tr);
    }

    tbody.appendChild(frag);
  }

  async function refreshStats() {
    const s = await api("stats.json");
    const kv = els.stats_kv;

    const items = [];
    if (s.version) items.push(`version: ${s.version}`);
    if (s.queue) items.push(`queue: ${s.queue.active}/${s.queue.max} active, ${s.queue.total} total`);
    if (s.disk) items.push(`disk: ${s.disk.free_mb}MB free (min ${s.disk.min_free_mb}MB)`);

    if (s.paths) {
      if (s.paths.jobs_dir) items.push(`jobs_dir: ${s.paths.jobs_dir}`);
      if (s.paths.result_dir) items.push(`result_dir: ${s.paths.result_dir}`);
    }

    kv.textContent = "";
    for (const t of items) {
      const div = document.createElement("div");
      div.className = "item";
      div.textContent = t;
      kv.appendChild(div);
    }

    els.stats.hidden = false;
  }

  async function refreshJobs() {
    const data = await api("jobs.json");
    jobsCache = (data && data.jobs) ? data.jobs : [];
    applyFilters();
  }

  async function purgeState(state) {
    try {
      const res = await api("purge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state }),
      });
      alert(`Deleted ${res.count} jobs`);
      await refreshAll();
    } catch (e) {
      alert(`Purge failed: ${e.message}`);
    }
  }

  function applyLogStyle() {
    els.logview.style.whiteSpace = wrap ? "pre-wrap" : "pre";
    els.logview.style.fontSize = `${fontSize}px`;
  }

  function resetSearch() {
    matches = [];
    matchIdx = -1;
  }

  function onLogSearch() {
    logSearch = (els.logsearch.value || "").trim();
    resetSearch();
    highlightMatches();
  }

  function highlightMatches() {
    const txt = els.logview.textContent || "";
    if (!logSearch) return;

    const haystack = txt.toLowerCase();
    const needle = logSearch.toLowerCase();

    let idx = 0;
    matches = [];
    while (true) {
      const found = haystack.indexOf(needle, idx);
      if (found === -1) break;
      matches.push(found);
      idx = found + needle.length;
      if (matches.length > 500) break;
    }

    matchIdx = matches.length ? 0 : -1;
    scrollToMatch();
  }

  function scrollToMatch() {
    if (matchIdx < 0 || matchIdx >= matches.length) return;
    const txt = els.logview.textContent || "";
    const before = txt.slice(0, matches[matchIdx]);
    const line = before.split("\n").length;
    const approxLineHeight = 16;
    els.logview.scrollTop = Math.max(0, (line - 5) * approxLineHeight);
  }

  function findNext() {
    if (!matches.length) return;
    matchIdx = (matchIdx + 1) % matches.length;
    scrollToMatch();
  }

  function findPrev() {
    if (!matches.length) return;
    matchIdx = (matchIdx - 1 + matches.length) % matches.length;
    scrollToMatch();
  }

  function clearSearch() {
    els.logsearch.value = "";
    logSearch = "";
    resetSearch();
  }

  function resetBuffers() {
    buffers.stdout = "";
    buffers.stderr = "";
    offsets.stdout = 0;
    offsets.stderr = 0;
    els.logview.textContent = "";
  }

  function appendBuffer(which, chunk) {
    if (!chunk) return;
    buffers[which] += chunk;
    if (buffers[which].length > LOG_MAX_CHARS) {
      buffers[which] = buffers[which].slice(-LOG_MAX_CHARS);
    }
  }

  async function selectJob(jobId) {
    currentJob = jobId;
    els.detail.hidden = false;
    els.jobid.textContent = jobId;

    resetBuffers();
    setTab(currentTab);

    await refreshOverview();
    await refreshMetaAndTail();
  }

  async function refreshOverview() {
    if (!currentJob) return;

    try {
      const j = await api(`job/${encodeURIComponent(currentJob)}.json`);
      const st = j || {};
      const dur = (st.duration_seconds !== null && st.duration_seconds !== undefined) ? st.duration_seconds : "";
      const who = (st.submitted_by && (st.submitted_by.display_name || st.submitted_by.name)) || "";
      const ip = st.client_ip || "";

      els.overview_text.textContent =
        `created=${st.created_utc} started=${st.started_utc} finished=${st.finished_utc} duration_s=${dur} ip=${ip} user=${who}`;

      const base = new URL(".", window.location.href).toString().replace(/\/$/, "");
      const curl = [
        "# Direct access requires X-Runner-Token unless you are using Ingress",
        `BASE="${base}"`,
        `JOB="${currentJob}"`,
        "TOKEN=\"YOUR_TOKEN_HERE\"",
        "",
        "curl -H \"X-Runner-Token: $TOKEN\" \"$BASE/job/$JOB.json\"",
        "curl -H \"X-Runner-Token: $TOKEN\" \"$BASE/tail/$JOB.json\"",
        "curl -H \"X-Runner-Token: $TOKEN\" -L \"$BASE/result/$JOB.zip\" -o result.zip",
        "curl -H \"X-Runner-Token: $TOKEN\" -X POST \"$BASE/cancel/$JOB\"",
        "curl -H \"X-Runner-Token: $TOKEN\" -X DELETE \"$BASE/job/$JOB\"",
      ].join("\n");

      els.curl_snippet.value = curl;
    } catch (e) {
      els.overview_text.textContent = `overview error: ${e.message}`;
    }
  }

  async function copyCurl() {
    try {
      await navigator.clipboard.writeText(els.curl_snippet.value);
      alert("Copied");
    } catch {
      els.curl_snippet.select();
      document.execCommand("copy");
      alert("Copied");
    }
  }

  async function refreshMetaAndTail() {
    if (!currentJob) return;

    try {
      const data = await api(
        `tail/${encodeURIComponent(currentJob)}.json?stdout_from=${offsets.stdout}&stderr_from=${offsets.stderr}&max_bytes=65536`
      );
      const st = data.status || {};
      const lim = st.limits || {};
      els.meta.textContent =
        `state=${st.state} exit=${st.exit_code} error=${st.error} cpu=${lim.cpu_percent} mode=${lim.cpu_limit_mode} eff=${lim.cpu_cpulimit_pct} mem_mb=${lim.mem_mb} thr=${lim.threads}`;

      if (data.offsets) {
        offsets.stdout = data.offsets.stdout_next || offsets.stdout;
        offsets.stderr = data.offsets.stderr_next || offsets.stderr;
      }

      const tail = data.tail || {};
      appendBuffer("stdout", tail.stdout || "");
      appendBuffer("stderr", tail.stderr || "");

      if (currentTab !== "overview") {
        els.logview.textContent = buffers[currentTab] || "";
        applyLogStyle();
        if (follow) {
          els.logview.scrollTop = els.logview.scrollHeight;
        }
      }

      if (logSearch) {
        // Recompute matches because content changed
        resetSearch();
        highlightMatches();
      }
    } catch (e) {
      els.meta.textContent = `error: ${e.message}`;
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
    els.detail.hidden = true;
    await refreshAll();
  }

  function openInNewTab(path) {
    window.open(apiUrl(path), "_blank", "noopener,noreferrer");
  }

  function downloadZip() {
    if (!currentJob) return;
    openInNewTab(`result/${encodeURIComponent(currentJob)}.zip`);
  }

  function downloadText(which) {
    if (!currentJob) return;
    const p = (which === "stderr")
      ? `stderr/${encodeURIComponent(currentJob)}.txt`
      : `stdout/${encodeURIComponent(currentJob)}.txt`;
    openInNewTab(p);
  }

  async function refreshAll() {
    await Promise.all([refreshStats(), refreshJobs()]);
    if (currentJob) {
      await Promise.all([refreshMetaAndTail(), refreshOverview()]);
    }
  }

  async function tick() {
    if (auto) {
      await refreshAll();
    }
    setTimeout(tick, pollMs);
  }

  function bindEvents() {
    document.addEventListener("click", async (ev) => {
      const btn = ev.target.closest("button[data-action]");
      if (!btn) return;

      const action = btn.getAttribute("data-action");
      if (action === "refresh") await refreshAll();
      if (action === "toggle-auto") toggleAuto();
      if (action === "set-view") setView(btn.getAttribute("data-view") || "all");
      if (action === "purge") await purgeState(btn.getAttribute("data-state") || "");
      if (action === "set-tab") setTab(btn.getAttribute("data-tab") || "stdout");
      if (action === "find-next") findNext();
      if (action === "find-prev") findPrev();
      if (action === "clear-search") clearSearch();
      if (action === "copy-curl") await copyCurl();
      if (action === "download-zip") downloadZip();
      if (action === "download-text") downloadText(btn.getAttribute("data-which") || "stdout");
      if (action === "cancel") await cancelJob();
      if (action === "delete") await deleteJob();
    });

    els.pollms.addEventListener("change", setPollMsFromInput);
    els.search.addEventListener("input", applyFilters);

    els.follow.addEventListener("change", () => {
      follow = !!els.follow.checked;
    });

    els.wrap.addEventListener("change", () => {
      wrap = !!els.wrap.checked;
      applyLogStyle();
    });

    els.font.addEventListener("input", () => {
      fontSize = clampInt(els.font.value, 11, 18, fontSize);
      applyLogStyle();
    });

    els.logsearch.addEventListener("input", onLogSearch);
  }

  function cacheEls() {
    els.statusline = document.getElementById("statusline");
    els.stats = document.getElementById("stats");
    els.stats_kv = document.getElementById("stats_kv");
    els.jobtable_tbody = document.querySelector("#jobtable tbody");
    els.empty = document.getElementById("empty");

    els.autostate = document.getElementById("autostate");
    els.pollms = document.getElementById("pollms");
    els.search = document.getElementById("search");

    els.detail = document.getElementById("detail");
    els.jobid = document.getElementById("jobid");
    els.meta = document.getElementById("meta");

    els.follow = document.getElementById("follow");
    els.wrap = document.getElementById("wrap");
    els.font = document.getElementById("font");

    els.logsearch = document.getElementById("logsearch");
    els.logpanel = document.getElementById("logpanel");
    els.logview = document.getElementById("logview");

    els.overview = document.getElementById("overview");
    els.overview_text = document.getElementById("overview_text");
    els.curl_snippet = document.getElementById("curl_snippet");
  }

  async function init() {
    cacheEls();
    bindEvents();

    const savedView = localStorage.getItem("pjr_view");
    if (savedView) view = savedView;

    const savedTab = localStorage.getItem("pjr_tab");
    if (savedTab) currentTab = savedTab;

    const savedPoll = localStorage.getItem("pjr_pollms");
    if (savedPoll) pollMs = clampInt(savedPoll, 250, 10_000, pollMs);
    els.pollms.value = String(pollMs);

    applyLogStyle();

    await refreshAll();

    const j = qs("job");
    if (j) await selectJob(j);

    setTab(currentTab);
    tick();
  }

  // Kick off after DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => { void init(); });
  } else {
    void init();
  }
})();
