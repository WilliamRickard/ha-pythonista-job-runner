/* VERSION: 0.6.11 */
/* eslint-disable no-alert */
(() => {
  "use strict";

  // Guard against double-injection (Ingress / hot reload / duplicate script tags).
  if (window.__pjr_webui_loaded__) return;
  window.__pjr_webui_loaded__ = true;

  const LOG_MAX_CHARS = 2000000;
  const MAX_MATCHES = 500;
  const TAIL_MAX_BYTES = 65536;

  let auto = true;
  let pollMs = 2000;

  let currentJob = null;
    initialTailForJob = null;
  let initialTailForJob = null;
  let currentTab = "stdout";
  let view = "all";

  let jobsCache = [];
  let follow = true;
  let wrap = true;
  let fontSize = 13;

  let paused = false;
  let hilite = false;
  let pane = "jobs"; // "jobs" or "detail" on narrow screens
  let refreshing = false;
  let toastActionHandler = null;

  let infoCache = null;

  let logSearch = "";
  let matchIdx = -1;
  let matches = [];
  let logSearchTimer = null;
  let tickTimer = null;

  const offsets = { stdout: 0, stderr: 0 };
  const buffers = { stdout: "", stderr: "" };

  const els = {};

  function qs(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function apiUrl(path) {
    return new URL(path, window.location.href).toString();
  }

  function baseUrl() {
    // Directory URL without trailing slash.
    return new URL(".", window.location.href).toString().replace(/\/$/, "");
  }

  function isNarrow() {
    return window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
  }

  function setPane(next) {
    pane = (next === "detail") ? "detail" : "jobs";
    localStorage.setItem("pjr_pane", pane);
    ensurePaneForViewport();
  }

  function ensurePaneForViewport() {
    const narrow = isNarrow();
    if (!els.pane_jobs || !els.pane_detail) return;

    if (!narrow) {
      els.pane_jobs.hidden = false;
      els.pane_detail.hidden = false;
      if (els.btn_back) els.btn_back.hidden = true;
      return;
    }

    els.pane_jobs.hidden = (pane !== "jobs");
    els.pane_detail.hidden = (pane !== "detail");
    if (els.btn_back) els.btn_back.hidden = (pane !== "detail");
  }

  async function api(path, opts) {
    const timeoutMs = 10000;
    const controller = (opts && opts.signal) ? null : new AbortController();
    const signal = controller ? controller.signal : (opts ? opts.signal : undefined);

    const finalOpts = Object.assign({}, (opts || {}));
    if (signal) finalOpts.signal = signal;

    let timer = null;
    if (controller) {
      timer = window.setTimeout(() => controller.abort(), timeoutMs);
    }

    try {
      const r = await fetch(apiUrl(path), finalOpts);
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`${r.status} ${t}`);
      }
      const ct = r.headers.get("content-type") || "";
      if (ct.includes("application/json")) return await r.json();
      return await r.text();
    } finally {
      if (timer) window.clearTimeout(timer);
    }
  }

  function clampInt(v, min, max, fallback) {
    const n = Number.parseInt(String(v), 10);
    if (Number.isNaN(n)) return fallback;
    return Math.max(min, Math.min(max, n));
  }

  function nowUtcSeconds() {
    return Math.floor(Date.now() / 1000);
  }

function parseUtcSeconds(v) {
    if (v === null || v === undefined) return 0;
    if (typeof v === "number") {
      if (!Number.isFinite(v)) return 0;
      return (v > 1e12) ? Math.floor(v / 1000) : Math.floor(v);
    }
    const s = String(v).trim();
    if (!s) return 0;
    const n = Number(s);
    if (Number.isFinite(n)) {
      return (n > 1e12) ? Math.floor(n / 1000) : Math.floor(n);
    }
    const ms = Date.parse(s);
    if (Number.isFinite(ms)) return Math.floor(ms / 1000);
    return 0;
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
    const t = parseUtcSeconds(createdUtc);
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

  async function copyTextToClipboard(text) {
    const t = String(text || "");
    if (!t) return;
    try {
      await navigator.clipboard.writeText(t);
      return;
    } catch (_e) {
      // Fallback for older webviews.
      const ta = document.createElement("textarea");
      ta.value = t;
      ta.setAttribute("readonly", "true");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } finally {
        document.body.removeChild(ta);
      }
    }
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
    pollMs = clampInt(els.pollms.value, 250, 10000, pollMs);
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

    const showLogs = (next !== "overview");
    els.overview.hidden = showLogs;
    els.logpanel.style.display = showLogs ? "block" : "none";
    if (els.logtools) els.logtools.style.display = showLogs ? "flex" : "none";
    if (els.findbar) els.findbar.style.display = showLogs ? "flex" : "none";

    if (next === "overview") {
      resetSearch();
      applyLogStyle();
      return;
    }

    renderLog(next);


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

  
  function clearFilters() {
    els.search.value = "";
    setView("all");
    localStorage.setItem("pjr_search", "");
    applyFilters();
  }

  function resetUi() {
    const keys = [
      "pjr_view","pjr_tab","pjr_pollms","pjr_search","pjr_auto","pjr_follow",
      "pjr_wrap","pjr_font","pjr_pause","pjr_hilite","pjr_pane"
    ];
    for (const k of keys) localStorage.removeItem(k);
    toast("ok", "Reset", "UI settings cleared");
    window.setTimeout(() => window.location.reload(), 500);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderLog(kind) {
    if (kind === "overview") return;
    const txt = buffers[kind] || "";
    if (!hilite) {
      els.logview.textContent = txt;
      applyLogStyle();
      return;
    }

    const MAX_RENDER = 200000;
    const truncated = (txt.length > MAX_RENDER);
    const slice = truncated ? txt.slice(-MAX_RENDER) : txt;
    const lines = slice.split("\n");
    const out = [];
    for (const line of lines) {
      const esc = escapeHtml(line);
      let cls = "logline";
      const u = line.toUpperCase();
      if (u.includes("TRACEBACK") || u.includes("ERROR") || u.includes("EXCEPTION")) cls += " err";
      else if (u.includes("WARN")) cls += " warn";
      out.push(`<span class="${cls}">${esc}</span>`);
    }
    els.logview.innerHTML = out.join("\n");
    applyLogStyle();

  }

  function jumpToNextError() {
    if (!currentJob) {
      toast("err", "No job selected", "Select a job first");
      return;
    }
    const kind = (currentTab === "stderr") ? "stderr" : "stdout";
    const txt = buffers[kind] || "";
    const re = /(Traceback|ERROR|Exception|FATAL|WARN(ING)?)/gi;
    const start = (matches && matchIdx >= 0 && matchIdx < matches.length) ? matches[matchIdx] : 0;
    re.lastIndex = start + 1;
    const m = re.exec(txt) || re.exec(txt);
    if (!m) {
      toast("ok", "No errors found", "No ERROR/WARN/Traceback lines found");
      return;
    }
    // Use search machinery to scroll approximately.
    logSearch = m[0];
    els.logsearch.value = logSearch;
    computeMatches();
    matchIdx = Math.min(matches.length - 1, Math.max(0, matches.findIndex((x) => x >= m.index)));
    scrollToMatch();
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
      const ta = parseUtcSeconds(a.created_utc);
      const tb = parseUtcSeconds(b.created_utc);
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

      const wrap = document.createElement("div");
      wrap.className = "jobcell";

      const line = document.createElement("div");
      line.className = "jobline";

      const btnJob = document.createElement("button");
      btnJob.type = "button";
      btnJob.className = "small jobbtn";
      btnJob.textContent = jobId;
      btnJob.title = jobId;
      btnJob.addEventListener("click", () => selectJob(jobId));

      const btnCopy = document.createElement("button");
      btnCopy.type = "button";
      btnCopy.className = "small copybtn";
      btnCopy.textContent = "Copy";
      btnCopy.addEventListener("click", async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        await copyTextToClipboard(jobId);
        toast("ok", "Copied", "Job id copied");
      });

      line.append(btnJob, btnCopy);

      const meta = document.createElement("div");
      meta.className = "jobmeta";

      const addMeta = (label, value) => {
        const v = String(value || "");
        if (!v) return;
        const span = document.createElement("span");
        span.className = "meta";
        span.textContent = `${label}: ${v}`;
        meta.appendChild(span);
      };

      addMeta("age", age);
      addMeta("dur", dur);
      addMeta("user", user);
      if (j.exit_code !== undefined && j.exit_code !== null && String(j.exit_code) !== "") {
        addMeta("exit", String(j.exit_code));
      }

      wrap.append(line, meta);
      tdJob.appendChild(wrap);

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
    if (els.jobs_loading) els.jobs_loading.hidden = false;
    try {
      const data = await api("jobs.json");
      jobsCache = (data && data.jobs) ? data.jobs : [];
      applyFilters();
    } finally {
      if (els.jobs_loading) els.jobs_loading.hidden = true;
    }
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

  function parseEndpointPath(v) {
    const s = String(v || "").trim();
    if (!s) return "";
    const parts = s.split(/\s+/, 2);
    if (parts.length === 2 && /^[A-Z]+$/.test(parts[0]) && parts[1].startsWith("/")) {
      return parts[1];
    }
    if (s.startsWith("/")) return s;
    return "";
  }

  function renderInfo(info) {
    const i = info || {};
    const service = i.service ? String(i.service) : "pythonista_job_runner";
    const version = i.version ? String(i.version) : "";
    els.about_sub.textContent = version ? `${service} v${version}` : service;

    const endpoints = i.endpoints || {};
    const keys = Object.keys(endpoints).sort();
    els.about_api.textContent = "";

    for (const k of keys) {
      const raw = endpoints[k];
      const row = document.createElement("div");
      row.className = "api-row";

      const left = document.createElement("div");
      left.className = "api-left";

      const name = document.createElement("div");
      name.className = "api-name";
      name.textContent = k;

      const path = document.createElement("div");
      path.className = "api-path";
      path.textContent = String(raw);

      left.append(name, path);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "small";
      btn.textContent = "Copy";
      btn.setAttribute("data-action", "copy-endpoint");
      btn.setAttribute("data-endpoint", k);

      const p = parseEndpointPath(raw);
      if (p) {
        btn.setAttribute("data-copy", apiUrl(p));
      } else {
        btn.disabled = true;
        btn.title = "No URL available";
      }

      row.append(left, btn);
      els.about_api.appendChild(row);
    }

    const base = baseUrl();
    const curl = [
      `# ${service} ${version ? `v${version}` : ""}`.trim(),
      "# Direct access requires X-Runner-Token unless you are using Ingress",
      `BASE=\"${base}\"`,
      "TOKEN=\"YOUR_TOKEN_HERE\"",
      "",
      "curl \"$BASE/health\"",
      "curl -H \"X-Runner-Token: $TOKEN\" \"$BASE/jobs.json\"",
      "curl -H \"X-Runner-Token: $TOKEN\" \"$BASE/stats.json\"",
      "curl -H \"X-Runner-Token: $TOKEN\" -X POST \"$BASE/purge\" -H \"content-type: application/json\" -d '{\"state\":\"done\"}'",
      "# Run requires a zip payload; see DOCS.md for the Pythonista client",
    ].join("\n");
    els.about_curl.value = curl;
  }

  async function loadInfo() {
    infoCache = await api("info.json");
    renderInfo(infoCache);
  }

  async function openAbout() {
    els.about_overlay.hidden = false;
    els.about_overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.height = "100%";
    document.body.style.height = "100%";
    try {
      await loadInfo();
    } catch (e) {
      els.about_sub.textContent = "Help";
      els.about_api.textContent = "";
      els.about_curl.value = "";
      toast("err", "Could not load info", e.message);
    }
  }

  
  function openAdvanced() {
    els.adv_overlay.hidden = false;
    els.adv_overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.height = "100%";
    document.body.style.height = "100%";

    if (els.auto) els.auto.checked = auto;
    if (els.pollms) els.pollms.value = String(pollMs);
  }

  function closeAdvanced() {
    els.adv_overlay.hidden = true;
    els.adv_overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    document.documentElement.style.height = "";
    document.body.style.height = "";
  }

function closeAbout() {
    els.about_overlay.hidden = true;
    els.about_overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    document.documentElement.style.height = "";
    document.body.style.height = "";
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
        const style = window.getComputedStyle(els.logview);
    const lh = Number.parseFloat(style.lineHeight) || 16;
    els.logview.scrollTop = Math.max(0, (line - 5) * lh);
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

  function updateDetailActions(state) {
    const st = String(state || "");
    const canCancel = (st === "running" || st === "queued");
    const canDelete = (st === "done" || st === "error");

    if (els.btn_cancel) els.btn_cancel.style.display = canCancel ? "inline-flex" : "none";
    if (els.btn_delete) els.btn_delete.style.display = canDelete ? "inline-flex" : "none";
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
    if (isNarrow()) setPane("detail");

    // Update URL (Ingress-safe: keep relative)
    const u = new URL(window.location.href);
    u.searchParams.set("job", jobId);
    window.history.replaceState({}, "", u.toString());

    resetBuffers();
    clearSearch();
    initialTailForJob = null;

    // Ensure row highlight is updated
    applyFilters();

    setTab(currentTab);
    await Promise.all([refreshMetaAndTail({ forceTail: true }), refreshOverview()]);
  }

  async function refreshOverview() {
    if (!currentJob) return;

    try {
      const j = await api(`job/${encodeURIComponent(currentJob)}.json`);
      const st = j || {};
      const durStr = (st.duration_seconds !== null && st.duration_seconds !== undefined) ? fmtDuration(st.duration_seconds) : "";
      const who = (st.submitted_by && (st.submitted_by.display_name || st.submitted_by.name)) || "";
      const ip = st.client_ip || "";

      els.overview_text.textContent = `Created: ${st.created_utc || ""}
Started: ${st.started_utc || ""}
Finished: ${st.finished_utc || ""}
Duration: ${durStr}
User: ${who || ""}
Client IP: ${ip || ""}`;

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

  async function refreshMetaAndTail(opts) {
    if (!currentJob) return;

    const forceTail = Boolean(opts && opts.forceTail);

    // When paused, do not consume new log bytes. We still refresh status/meta.
    if (paused && !forceTail && initialTailForJob === currentJob) {
      try {
        const st = await api(`job/${encodeURIComponent(currentJob)}.json`);
        renderMeta(st || {});
        updateDetailActions((st && st.state) || "");
      } catch (e) {
        els.meta.textContent = "";
        const dt = document.createElement("dt");
        dt.textContent = "Error";
        const dd = document.createElement("dd");
        dd.textContent = e.message;
        els.meta.append(dt, dd);
      }
      return;
    }

    try {
      const data = await api(
        `tail/${encodeURIComponent(currentJob)}.json?stdout_from=${offsets.stdout}&stderr_from=${offsets.stderr}&max_bytes=${TAIL_MAX_BYTES}`
      );

      const st = data.status || {};
      renderMeta(st);
      updateDetailActions(st.state);

      if (data.offsets) {
        offsets.stdout = data.offsets.stdout_next || offsets.stdout;
        offsets.stderr = data.offsets.stderr_next || offsets.stderr;
      }

      const tail = data.tail || {};
      appendBuffer("stdout", tail.stdout || "");
      appendBuffer("stderr", tail.stderr || "");

      initialTailForJob = currentJob;

      if (currentTab !== "overview") {
        renderLog(currentTab);
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
      await copyTextToClipboard(els.curl_snippet.value);
      toast("ok", "Copied", "curl snippet copied to clipboard");
    } else {
      toast("err", "Nothing to copy", "Select a job first");
    }
  }

  async function copyBase() {
    await copyTextToClipboard(baseUrl());
    toast("ok", "Copied", "Base URL copied to clipboard");
  }

  async function copyEndpoint(btn) {
    const val = btn.getAttribute("data-copy") || "";
    if (!val) return;
    await copyTextToClipboard(val);
    toast("ok", "Copied", val);
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
    if (refreshing) return;
    refreshing = true;
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
    finally {
      refreshing = false;
    }
  }

  async function tick() {
    if (auto) {
      await refreshAll();
    }
    tickTimer = window.setTimeout(tick, pollMs);
  }

  function toggleAuto() {
    auto = !auto;
    els.autostate.textContent = auto ? "on" : "off";
    toast(null, "Auto refresh", auto ? "Enabled" : "Disabled");
  }

  function bindEvents() {
    document.addEventListener("click", async (ev) => {
      const t = ev.target;
      const el = (t instanceof Element) ? t : (t && t.parentElement);
      if (!el) return;
      const btn = el.closest("button[data-action]");
      if (!btn) return;

      const action = btn.getAttribute("data-action");
      if (action === "refresh") await refreshAll();
      if (action === "open-advanced") openAdvanced();
      if (action === "close-advanced") closeAdvanced();
      if (action === "back-to-jobs") setPane("jobs");
      if (action === "clear-filters") clearFilters();
      if (action === "reset-ui") resetUi();
      if (action === "jump-error") jumpToNextError();
      if (action === "set-view") setView(btn.getAttribute("data-view") || "all");
      if (action === "purge") await purgeState(btn.getAttribute("data-state") || "");
      if (action === "set-tab") setTab(btn.getAttribute("data-tab") || "stdout");
      if (action === "find-next") findNext();
      if (action === "find-prev") findPrev();
      if (action === "clear-search") clearSearch();
      if (action === "copy-curl") await copyCurl();
      if (action === "open-about") await openAbout();
      if (action === "close-about") closeAbout();
      if (action === "copy-base") await copyBase();
      if (action === "open-info") window.open(apiUrl("info.json"), "_blank", "noopener,noreferrer");
      if (action === "copy-endpoint") await copyEndpoint(btn);
      if (action === "download-zip") downloadZip();
      if (action === "download-text") downloadText(btn.getAttribute("data-which") || "stdout");
      if (action === "cancel") await cancelJob();
      if (action === "delete") await deleteJob();
    });

    els.about_overlay.addEventListener("click", (ev) => {
      if (ev.target === els.about_overlay) closeAbout();
    });

    els.adv_overlay.addEventListener("click", (ev) => {
      if (ev.target === els.adv_overlay) closeAdvanced();
    });


    if (els.about_close) {
      const close = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        closeAbout();
      };
      els.about_close.addEventListener("click", close);
      els.about_close.addEventListener("touchend", close, { passive: false });
    }


    if (els.adv_close) {
      const close = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        closeAdvanced();
      };
      els.adv_close.addEventListener("click", close);
      els.adv_close.addEventListener("touchend", close, { passive: false });
    }

    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      if (!els.about_overlay.hidden) closeAbout();
      if (!els.adv_overlay.hidden) closeAdvanced();
    });

    els.pollms.addEventListener("change", () => {
      setPollMsFromInput();
      localStorage.setItem("pjr_pollms", String(pollMs));
    });
    els.search.addEventListener("input", () => {
      localStorage.setItem("pjr_search", String(els.search.value || ""));
      applyFilters();
    });
    if (els.auto) {
      els.auto.addEventListener("change", () => {
        auto = !!els.auto.checked;
        localStorage.setItem("pjr_auto", auto ? "1" : "0");
        els.autostate.textContent = auto ? "on" : "off";
      });
    }

    els.follow.addEventListener("change", () => {
      follow = !!els.follow.checked;
      localStorage.setItem("pjr_follow", follow ? "1" : "0");
    });

    els.wrap.addEventListener("change", () => {
      wrap = !!els.wrap.checked;
      localStorage.setItem("pjr_wrap", wrap ? "1" : "0");
      applyLogStyle();
      renderLog(currentTab);
    });

    els.font.addEventListener("input", () => {
      fontSize = clampInt(els.font.value, 11, 18, fontSize);
      localStorage.setItem("pjr_font", String(fontSize));
      applyLogStyle();
    });

    if (els.pause) {
      els.pause.addEventListener("change", () => {
        paused = !!els.pause.checked;
        localStorage.setItem("pjr_pause", paused ? "1" : "0");
      });
    }
    if (els.hilite) {
      els.hilite.addEventListener("change", () => {
        hilite = !!els.hilite.checked;
        localStorage.setItem("pjr_hilite", hilite ? "1" : "0");
        renderLog(currentTab);
      });
    }

    els.logsearch.addEventListener("input", onLogSearchDebounced);
    if (els.toast_action) {
      els.toast_action.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof toastActionHandler === "function") {
          const fn = toastActionHandler;
          toastActionHandler = null;
          fn();
          els.toast.classList.remove("show");
        }
      });
    }
    window.addEventListener("resize", ensurePaneForViewport);
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

    els.pane_jobs = document.getElementById("pane_jobs");
    els.pane_detail = document.getElementById("pane_detail");

    els.jobtable_tbody = document.querySelector("#jobtable tbody");
    els.empty = document.getElementById("empty");

    els.jobs_banner = document.getElementById("jobs_banner");
    els.jobs_loading = document.getElementById("jobs_loading");

    els.autostate = document.getElementById("autostate");
    els.pollms = document.getElementById("pollms");
    els.search = document.getElementById("search");

    els.detail = document.getElementById("detail");
    els.detail_empty = document.getElementById("detail_empty");
    els.jobid = document.getElementById("jobid");
    els.meta = document.getElementById("meta");

    els.follow = document.getElementById("follow");
    els.wrap = document.getElementById("wrap");
    els.pause = document.getElementById("pause");
    els.hilite = document.getElementById("hilite");
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
    els.toast_action = document.getElementById("toast_action");

    els.about_overlay = document.getElementById("about_overlay");
    els.about_close = document.getElementById("about_close");
    els.about_sub = document.getElementById("about_sub");
    els.about_api = document.getElementById("about_api");
    els.about_curl = document.getElementById("about_curl");

    els.adv_overlay = document.getElementById("adv_overlay");
    els.adv_close = document.getElementById("adv_close");
    els.auto = document.getElementById("auto");
    els.btn_back = document.getElementById("btn_back");
    els.btn_cancel = document.getElementById("btn_cancel");
    els.btn_delete = document.getElementById("btn_delete");
  }

  async function init() {
    cacheEls();
    bindEvents();

    const savedView = localStorage.getItem("pjr_view");
    if (savedView) view = savedView;

    const savedTab = localStorage.getItem("pjr_tab");
    if (savedTab) currentTab = savedTab;

    const savedPoll = localStorage.getItem("pjr_pollms");
    if (savedPoll) pollMs = clampInt(savedPoll, 250, 10000, pollMs);
    els.pollms.value = String(pollMs);

    const savedAuto = localStorage.getItem("pjr_auto");
    if (savedAuto !== null) auto = (savedAuto === "1");
    els.autostate.textContent = auto ? "on" : "off";
    if (els.auto) els.auto.checked = auto;

    const savedSearch = localStorage.getItem("pjr_search");
    if (savedSearch !== null) els.search.value = savedSearch;

    const savedFollow = localStorage.getItem("pjr_follow");
    if (savedFollow !== null) follow = (savedFollow === "1");
    els.follow.checked = follow;

    const savedWrap = localStorage.getItem("pjr_wrap");
    if (savedWrap !== null) wrap = (savedWrap === "1");
    els.wrap.checked = wrap;

    const savedFont = localStorage.getItem("pjr_font");
    if (savedFont) fontSize = clampInt(savedFont, 11, 18, fontSize);
    els.font.value = String(fontSize);

    const savedPause = localStorage.getItem("pjr_pause");
    if (savedPause !== null) paused = (savedPause === "1");
    if (els.pause) els.pause.checked = paused;

    const savedHilite = localStorage.getItem("pjr_hilite");
    if (savedHilite !== null) hilite = (savedHilite === "1");
    if (els.hilite) els.hilite.checked = hilite;

    const savedPane = localStorage.getItem("pjr_pane");
    if (savedPane) pane = (savedPane === "detail") ? "detail" : "jobs";
    setPane(pane);
    ensurePaneForViewport();

    applyLogStyle();

    setStatus("warn", "Connecting…");
    await refreshAll();

    const j = qs("job");
    if (j) await selectJob(j);

    setView(view);
    setTab(currentTab);
    window.addEventListener("beforeunload", () => {
      if (tickTimer) window.clearTimeout(tickTimer);
      tickTimer = null;
    }, { once: true });

    tick();
  }

  const start = () => {
    init().catch((e) => {
      // eslint-disable-next-line no-console
      console.error(e);
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
