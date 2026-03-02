/* VERSION: 0.6.7 */
/* eslint-disable no-alert */
(() => {
  "use strict";

  const LOG_MAX_CHARS = 2_000_000;
  const MAX_MATCHES = 500;
  const TAIL_MAX_BYTES = 65_536;

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
  let logSearchTimer = null;

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
    const n = Number.parseInt(String(v), 10);
    if (Number.isNaN(n)) return fallback;
    return Math.max(min, Math.min(max, n));
  }

  function nowUtcSeconds() {
    return Math.floor(Date.now() / 1000);
  }

  function fmtDuration(seconds) {
    const s = Number(seconds);
    if (!Number.isFinite(s) || s < 0) return "";
    if (s < 60) return `${Math.round(s)}s`;
    const m = Math.floor(s / 60);
    const rs = Math.floor(s % 60);
    if (m < 60) return `${m}m ${rs}s`;
    const h = Math.floor(m / 60);
    const rm = m % 60;
    if (h < 24) return `${h}h ${rm}m`;
    const d = Math.floor(h / 24);
    const rh = h % 24;
    return `${d}d ${rh}h`;
  }

  function fmtAge(createdUtc) {
    const t = Number(createdUtc);
    if (!Number.isFinite(t) || t <= 0) return "";
    const age = Math.max(0, nowUtcSeconds() - t);
    return fmtDuration(age);
  }

  function fmtBytes(n) {
    const b = Number(n);
    if (!Number.isFinite(b) || b <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let v = b;
    let i = 0;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i += 1;
    }
    const rounded = (v >= 100) ? Math.round(v) : Math.round(v * 10) / 10;
    return `${rounded} ${units[i]}`;
  }

  function setStatus(kind, text) {
    els.statusline.textContent = text;
    els.statuspill.classList.remove("ok", "err", "warn");
    if (kind) els.statuspill.classList.add(kind);
  }

  function setLastUpdated(ts) {
    els.lastupdated.textContent = ts;
  }

  let toastTimer = null;
  function toast(kind, title, msg) {
    if (!els.toast) return;

    els.toast.classList.remove("ok", "err");
    if (kind) els.toast.classList.add(kind);

    els.toast_title.textContent = title || "";
    els.toast_msg.textContent = msg || "";
    els.toast.classList.add("show");

    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      els.toast.classList.remove("show");
    }, 3500);
  }

  function setPollMsFromInput() {
    pollMs = clampInt(els.pollms.value, 250, 10_000, pollMs);
    els.pollms.value = String(pollMs);
    localStorage.setItem("pjr_pollms", String(pollMs));
  }

  function setActiveButton(prefixId, activeId) {
    const ids = ["all", "running", "queued", "error", "done"];
    for (const k of ids) {
      const el = document.getElementById(`${prefixId}${k}`);
      if (!el) continue;
      el.classList.toggle("active", `${prefixId}${k}` === activeId);
    }
  }

  function setView(next) {
    view = next;
    localStorage.setItem("pjr_view", next);
    applyFilters();
    setActiveButton("view_", `view_${next}`);
  }

  function setTab(next) {
    currentTab = next;
    localStorage.setItem("pjr_tab", next);

    const tStdout = document.getElementById("tab_stdout");
    const tStderr = document.getElementById("tab_stderr");
    const tOverview = document.getElementById("tab_overview");
    if (tStdout) tStdout.classList.toggle("active", next === "stdout");
    if (tStderr) tStderr.classList.toggle("active", next === "stderr");
    if (tOverview) tOverview.classList.toggle("active", next === "overview");

    els.overview.hidden = (next !== "overview");
    els.logpanel.style.display = (next === "overview") ? "none" : "block";

    if (next === "overview") {
      resetSearch();
      applyLogStyle();
      return;
    }

    els.logview.textContent = buffers[next] || "";
    applyLogStyle();

    if (follow) {
      els.logview.scrollTop = els.logview.scrollHeight;
    }

    resetSearch();
    computeMatches();
    scrollToMatch();
  }

  function badgeEl(state) {
    const cls = state || "queued";
    const span = document.createElement("span");
    span.className = `badge ${cls}`;
    span.textContent = cls;
    return span;
  }

  function applyFilters() {
    const q = (els.search.value || "").trim().toLowerCase();
    let jobs = jobsCache.slice(0);

    // Sort: running, queued, error, done, other; within each: newest first.
    const order = { running: 0, queued: 1, error: 2, done: 3 };
    jobs.sort((a, b) => {
      const sa = order[a.state] ?? 9;
      const sb = order[b.state] ?? 9;
      if (sa !== sb) return sa - sb;
      const ta = Number(a.created_utc) || 0;
      const tb = Number(b.created_utc) || 0;
      return tb - ta;
    });

    if (view !== "all") {
      jobs = jobs.filter((j) => (j.state || "queued") === view);
    }

    if (q) {
      jobs = jobs.filter((j) => {
        const id = (j.job_id || "").toLowerCase();
        const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name) || "").toLowerCase();
        const st = (j.state || "queued").toLowerCase();
        return id.includes(q) || user.includes(q) || st.includes(q);
      });
    }

    renderJobs(jobs);
  }

  function renderJobs(jobs) {
    const tbody = els.jobtable_tbody;
    tbody.textContent = "";
    els.empty.hidden = (jobs.length !== 0);

    const frag = document.createDocumentFragment();

    for (const j of jobs) {
      const jobId = j.job_id || "";
      const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name)) || "";
      const state = j.state || "queued";
      const age = fmtAge(j.created_utc);
      const dur = fmtDuration(j.duration_seconds);

      const tr = document.createElement("tr");
      if (currentJob && jobId === currentJob) tr.classList.add("selected");

      const tdJob = document.createElement("td");
      tdJob.setAttribute("data-label", "Job");
      const btnJob = document.createElement("button");
      btnJob.type = "button";
      btnJob.className = "small";
      btnJob.textContent = jobId;
      btnJob.addEventListener("click", () => selectJob(jobId));
      tdJob.appendChild(btnJob);

      const tdState = document.createElement("td");
      tdState.setAttribute("data-label", "State");
      tdState.appendChild(badgeEl(state));

      const tdAge = document.createElement("td");
      tdAge.setAttribute("data-label", "Age");
      tdAge.textContent = age;

      const tdDur = document.createElement("td");
      tdDur.setAttribute("data-label", "Duration");
      tdDur.textContent = dur;

      const tdUser = document.createElement("td");
      tdUser.setAttribute("data-label", "User");
      tdUser.textContent = user;

      const tdActions = document.createElement("td");
      tdActions.className = "actions";
      tdActions.setAttribute("data-label", "Actions");

      const btnView = document.createElement("button");
      btnView.type = "button";
      btnView.className = "small";
      btnView.textContent = "View";
      btnView.addEventListener("click", () => selectJob(jobId));

      const zip = document.createElement("a");
      zip.className = "linkbtn";
      zip.textContent = "Zip";
      zip.href = `result/${encodeURIComponent(jobId)}.zip`;
      zip.target = "_blank";
      zip.rel = "noopener noreferrer";

      tdActions.append(btnView, document.createTextNode(" "), zip);

      tr.append(tdJob, tdState, tdAge, tdDur, tdUser, tdActions);
      frag.appendChild(tr);
    }

    tbody.appendChild(frag);
  }

  function renderStats(stats) {
    const s = stats || {};
    const running = Number(s.jobs_running) || 0;
    const queued = Number(s.jobs_queued) || 0;
    const done = Number(s.jobs_done) || 0;
    const error = Number(s.jobs_error) || 0;
    const total = Number(s.jobs_total) || 0;

    els.kpi_running.textContent = String(running);
    els.kpi_queued.textContent = String(queued);
    els.kpi_done.textContent = String(done);
    els.kpi_error.textContent = String(error);
    els.kpi_total.textContent = String(total);

    // Meta pills
    els.stats_kv.textContent = "";
    const pills = [];

    if (s.runner_version) pills.push(`runner: ${s.runner_version}`);
    if (Number.isFinite(Number(s.job_retention_hours))) pills.push(`retention: ${s.job_retention_hours}h`);

    if (Number.isFinite(Number(s.disk_free_bytes)) && Number.isFinite(Number(s.disk_total_bytes)) && Number(s.disk_total_bytes) > 0) {
      pills.push(`disk free: ${fmtBytes(s.disk_free_bytes)} of ${fmtBytes(s.disk_total_bytes)}`);
    }
    if (Number.isFinite(Number(s.jobs_dir_bytes))) pills.push(`jobs dir: ${fmtBytes(s.jobs_dir_bytes)}`);

    for (const t of pills) {
      const span = document.createElement("span");
      span.className = "pill";
      span.textContent = t;
      els.stats_kv.appendChild(span);
    }

    els.stats.hidden = false;
  }

  async function refreshStats() {
    const s = await api("stats.json");
    renderStats(s);
  }

  async function refreshJobs() {
    const data = await api("jobs.json");
    jobsCache = (data && data.jobs) ? data.jobs : [];
    applyFilters();
  }

  async function purgeState(state) {
    if (!state) return;
    if (!window.confirm(`Purge ${state} jobs? This deletes job files.`)) return;
    await api("purge", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ state }),
    });
    toast("ok", "Purge complete", `Purged ${state} jobs`);
    await refreshAll();
  }

  function applyLogStyle() {
    els.logview.classList.toggle("nowrap", !wrap);
    els.logview.style.fontSize = `${fontSize}px`;
  }

  function resetSearch() {
    matches = [];
    matchIdx = -1;
    els.matchcount.textContent = "";
  }

  function updateMatchCount() {
    if (!logSearch) {
      els.matchcount.textContent = "";
      return;
    }
    if (!matches.length) {
      els.matchcount.textContent = "0 matches";
      return;
    }
    els.matchcount.textContent = `${matchIdx + 1} of ${matches.length}`;
  }

  function computeMatches() {
    const txt = els.logview.textContent || "";
    const needleRaw = logSearch;
    if (!needleRaw) {
      resetSearch();
      return;
    }

    const haystack = txt.toLowerCase();
    const needle = needleRaw.toLowerCase();

    let idx = 0;
    matches = [];
    while (true) {
      const found = haystack.indexOf(needle, idx);
      if (found === -1) break;
      matches.push(found);
      idx = found + needle.length;
      if (matches.length >= MAX_MATCHES) break;
    }

    matchIdx = matches.length ? 0 : -1;
    updateMatchCount();
  }

  function scrollToMatch() {
    if (matchIdx < 0 || matchIdx >= matches.length) {
      updateMatchCount();
      return;
    }
    const txt = els.logview.textContent || "";
    const needle = logSearch;
    if (!needle) return;

    const start = matches[matchIdx];
    const before = txt.slice(0, start);
    const line = before.split("\n").length;
    const approxLineHeight = 16;
    els.logview.scrollTop = Math.max(0, (line - 5) * approxLineHeight);
    updateMatchCount();
  }

  function onLogSearchDebounced() {
    if (logSearchTimer) window.clearTimeout(logSearchTimer);
    logSearchTimer = window.setTimeout(() => {
      logSearch = (els.logsearch.value || "").trim();
      computeMatches();
      scrollToMatch();
    }, 180);
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
    offsets.stdout = 0;
    offsets.stderr = 0;
    buffers.stdout = "";
    buffers.stderr = "";
  }

  function appendBuffer(which, chunk) {
    if (!chunk) return;
    buffers[which] = (buffers[which] || "") + chunk;
    if (buffers[which].length > LOG_MAX_CHARS) {
      buffers[which] = buffers[which].slice(-LOG_MAX_CHARS);
    }
  }

  function renderMeta(st) {
    const s = st || {};
    const lim = s.limits || {};
    const by = (s.submitted_by && (s.submitted_by.display_name || s.submitted_by.name)) || "";

    const items = [
      ["State", s.state || "queued"],
      ["Phase", s.phase || ""],
      ["Exit code", (s.exit_code === null || s.exit_code === undefined) ? "" : String(s.exit_code)],
      ["Error", s.error || ""],
      ["Created", s.created_utc ? String(s.created_utc) : ""],
      ["Started", s.started_utc ? String(s.started_utc) : ""],
      ["Finished", s.finished_utc ? String(s.finished_utc) : ""],
      ["Duration", fmtDuration(s.duration_seconds)],
      ["User", by],
      ["Client IP", s.client_ip || ""],
      ["CPU %", (lim.cpu_percent === null || lim.cpu_percent === undefined) ? "" : String(lim.cpu_percent)],
      ["CPU mode", lim.cpu_limit_mode || ""],
      ["CPU effective %", (lim.cpu_cpulimit_pct === null || lim.cpu_cpulimit_pct === undefined) ? "" : String(lim.cpu_cpulimit_pct)],
      ["Memory (MB)", (lim.mem_mb === null || lim.mem_mb === undefined) ? "" : String(lim.mem_mb)],
      ["Threads", (lim.threads === null || lim.threads === undefined) ? "" : String(lim.threads)],
      ["Timeout (s)", (lim.timeout_seconds === null || lim.timeout_seconds === undefined) ? "" : String(lim.timeout_seconds)],
    ];

    els.meta.textContent = "";
    for (const [k, v] of items) {
      if (v === "") continue;
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      els.meta.append(dt, dd);
    }
  }

  async function selectJob(jobId) {
    if (!jobId) return;
    currentJob = jobId;

    els.detail_empty.hidden = true;
    els.detail.hidden = false;
    els.jobid.textContent = jobId;

    // Update URL (Ingress-safe: keep relative)
    const u = new URL(window.location.href);
    u.searchParams.set("job", jobId);
    window.history.replaceState({}, "", u.toString());

    resetBuffers();
    clearSearch();

    // Ensure row highlight is updated
    applyFilters();

    await Promise.all([refreshMetaAndTail(), refreshOverview()]);
    setTab(currentTab);
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

  async function refreshMetaAndTail() {
    if (!currentJob) return;

    try {
      const data = await api(
        `tail/${encodeURIComponent(currentJob)}.json?stdout_from=${offsets.stdout}&stderr_from=${offsets.stderr}&max_bytes=${TAIL_MAX_BYTES}`
      );

      const st = data.status || {};
      renderMeta(st);

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
        computeMatches();
        scrollToMatch();
      }
    } catch (e) {
      els.meta.textContent = "";
      const dt = document.createElement("dt");
      dt.textContent = "Error";
      const dd = document.createElement("dd");
      dd.textContent = e.message;
      els.meta.append(dt, dd);
    }
  }

  async function copyCurl() {
    if (els.curl_snippet && els.curl_snippet.value) {
      await navigator.clipboard.writeText(els.curl_snippet.value);
      toast("ok", "Copied", "curl snippet copied to clipboard");
    } else {
      toast("err", "Nothing to copy", "Select a job first");
    }
  }

  async function cancelJob() {
    if (!currentJob) return;
    if (!window.confirm(`Cancel job ${currentJob}?`)) return;
    await api(`cancel/${encodeURIComponent(currentJob)}`, { method: "POST" });
    toast("ok", "Cancelled", `Job ${currentJob} cancelled`);
    await refreshAll();
  }

  async function deleteJob() {
    if (!currentJob) return;
    if (!window.confirm(`Delete job ${currentJob}? This removes job files.`)) return;
    await api(`job/${encodeURIComponent(currentJob)}`, { method: "DELETE" });
    toast("ok", "Deleted", `Job ${currentJob} deleted`);
    currentJob = null;
    els.detail.hidden = true;
    els.detail_empty.hidden = false;
    applyFilters();
    await refreshAll();
  }

  function downloadZip() {
    if (!currentJob) return;
    window.open(apiUrl(`result/${encodeURIComponent(currentJob)}.zip`), "_blank", "noopener,noreferrer");
  }

  function downloadText(which) {
    if (!currentJob) return;
    const w = which || "stdout";
    const url = apiUrl(`${w}/${encodeURIComponent(currentJob)}.txt`);
    window.open(url, "_blank", "noopener,noreferrer");
  }

  async function refreshAll() {
    try {
      await Promise.all([refreshStats(), refreshJobs()]);
      if (currentJob) {
        await Promise.all([refreshMetaAndTail(), refreshOverview()]);
      }
      setStatus("ok", "Connected");
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (e) {
      setStatus("err", "Disconnected");
      toast("err", "Request failed", e.message);
    }
  }

  async function tick() {
    if (auto) {
      await refreshAll();
    }
    window.setTimeout(tick, pollMs);
  }

  function toggleAuto() {
    auto = !auto;
    els.autostate.textContent = auto ? "on" : "off";
    toast(null, "Auto refresh", auto ? "Enabled" : "Disabled");
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

    els.logsearch.addEventListener("input", onLogSearchDebounced);
  }

  function cacheEls() {
    els.statuspill = document.getElementById("statuspill");
    els.statusline = document.getElementById("statusline");
    els.lastupdated = document.getElementById("lastupdated");

    els.stats = document.getElementById("stats");
    els.stats_kv = document.getElementById("stats_kv");

    els.kpi_running = document.getElementById("kpi_running");
    els.kpi_queued = document.getElementById("kpi_queued");
    els.kpi_error = document.getElementById("kpi_error");
    els.kpi_done = document.getElementById("kpi_done");
    els.kpi_total = document.getElementById("kpi_total");

    els.jobtable_tbody = document.querySelector("#jobtable tbody");
    els.empty = document.getElementById("empty");

    els.autostate = document.getElementById("autostate");
    els.pollms = document.getElementById("pollms");
    els.search = document.getElementById("search");

    els.detail = document.getElementById("detail");
    els.detail_empty = document.getElementById("detail_empty");
    els.jobid = document.getElementById("jobid");
    els.meta = document.getElementById("meta");

    els.follow = document.getElementById("follow");
    els.wrap = document.getElementById("wrap");
    els.font = document.getElementById("font");

    els.logsearch = document.getElementById("logsearch");
    els.matchcount = document.getElementById("matchcount");
    els.logpanel = document.getElementById("logpanel");
    els.logview = document.getElementById("logview");

    els.overview = document.getElementById("overview");
    els.overview_text = document.getElementById("overview_text");
    els.curl_snippet = document.getElementById("curl_snippet");

    els.toast = document.getElementById("toast");
    els.toast_title = document.getElementById("toast_title");
    els.toast_msg = document.getElementById("toast_msg");
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

    els.autostate.textContent = auto ? "on" : "off";

    applyLogStyle();

    setStatus("warn", "Connecting…");
    await refreshAll();

    const j = qs("job");
    if (j) await selectJob(j);

    setView(view);
    setTab(currentTab);
    tick();
  }

  init();
})();
