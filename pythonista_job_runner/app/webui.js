/* VERSION: 0.6.17-webui.1 */
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
  let initialTailForJob = null;
  let currentTab = "overview";
  let view = "all";
  let sortMode = "newest";
  let filterHasResult = false;
  let filterUser = "";
  let filterSince = "";
  let currentPage = 1;
  const PAGE_SIZE = 12;
  let keepSecondaryFilters = true;
  let uiDensity = "comfortable";
  let uiDirection = "auto";
  let firstJobsLoad = true;
  let jobsViewState = "initial";
  let jobsPaneWidth = 460;

  let jobsCache = [];
  let follow = true;
  let wrap = true;
  let fontSize = 13;

  let paused = false;
  let hilite = false;
  let highlightTerms = [];
  let autoPauseReason = "";

  const lastAppend = { stdout: { at: 0, from: 0 }, stderr: { at: 0, from: 0 } };
  let newFlashTimer = null;
  let programmaticScrollAt = 0;
  let pane = "jobs"; // "jobs" or "detail" on narrow screens
  let refreshing = false;
  let toastActionHandler = null;

  let infoCache = null;
  let setupStatusCache = null;
  let rowPopoverMode = "manual";
  let hoverPopoverTimer = null;
  let hoverPopoverCloseTimer = null;

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


  function currentHomeAssistantHost() {
    try {
      const host = String(window.location.hostname || "").trim();
      if (host) return host;
    } catch (_err) {
      // fall through
    }
    try {
      return String(window.location.host || "").trim();
    } catch (_err) {
      return "";
    }
  }

  function safeDownloadName(name, fallback) {
    const raw = String(name || "").trim();
    if (!raw) return fallback;
    return raw.replace(/[^A-Za-z0-9._-]+/g, "_");
  }

  function isNarrow() {
    return window.matchMedia && window.matchMedia("(max-width: 720px)").matches;
  }

  function hasFinePointer() {
    return !!(window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches);
  }


  function storageGet(key) {
    try {
      const ls = window["localStorage"];
      return ls ? ls.getItem(key) : null;
    } catch (_err) {
      return null;
    }
  }

  function storageSet(key, value) {
    try {
      const ls = window["localStorage"];
      if (ls) ls.setItem(key, value);
    } catch (_err) {
      // ignore storage write failures in restricted environments
    }
  }

  function storageRemove(key) {
    try {
      const ls = window["localStorage"];
      if (ls) ls.removeItem(key);
    } catch (_err) {
      // ignore storage remove failures in restricted environments
    }
  }

  function setPane(next) {
    pane = (next === "detail") ? "detail" : "jobs";
    storageSet("pjr_pane", pane);
    ensurePaneForViewport();
  }

  function updateSplitUi() {
    if (!document || !document.documentElement) return;
    const maxWidth = Math.max(360, window.innerWidth - 420);
    jobsPaneWidth = Math.max(360, Math.min(maxWidth, jobsPaneWidth));
    document.documentElement.style.setProperty("--jobs-pane-width", `${jobsPaneWidth}px`);
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


  /**
   * Update live/paused UI controls to reflect the current follow and paused state.
   *
   * Updates button active states and `aria-pressed` attributes, sets the pause/resume
   * button label, toggles visibility of the "jump to latest" control, and adjusts
   * the live status pill's styling and text based on whether logs are live, paused,
   * or in a scrollable state.
   */
  function updateLiveUi() {
    if (!els.btn_live || !els.btn_pause_resume || !els.livepill || !els.livestate) return;

    const isLive = (follow && !paused);
    els.btn_live.classList.toggle("active", isLive);
    els.btn_live.setAttribute("aria-pressed", isLive ? "true" : "false");

    const isPaused = !!paused;
    els.btn_pause_resume.classList.toggle("active", isPaused);
    els.btn_pause_resume.setAttribute("aria-pressed", isPaused ? "true" : "false");
    els.btn_pause_resume.textContent = isPaused ? "Resume" : "Pause";

    if (els.btn_jump_latest) {
      els.btn_jump_latest.hidden = !isPaused;
    }

    els.livepill.classList.remove("ok", "warn", "err");
    if (isPaused) {
      els.livepill.classList.add("warn");
      els.livestate.textContent = "Paused";
    } else if (isLive) {
      els.livepill.classList.add("ok");
      els.livestate.textContent = "Live";
    } else {
      els.livestate.textContent = "Scroll";
    }
  }

  function setFollow(next) {
    follow = !!next;
    if (els.follow) els.follow.checked = follow;
    storageSet("pjr_follow", follow ? "1" : "0");
    updateLiveUi();
  }

  function setPaused(next, reason) {
    paused = !!next;
    autoPauseReason = paused ? String(reason || "") : "";
    if (els.pause) els.pause.checked = paused;
    storageSet("pjr_pause", paused ? "1" : "0");
    updateLiveUi();
  }

  function flashNewLines() {
    if (!els.logpanel) return;
    els.logpanel.classList.add("newflash");
    if (newFlashTimer) window.clearTimeout(newFlashTimer);
    newFlashTimer = window.setTimeout(() => {
      if (els.logpanel) els.logpanel.classList.remove("newflash");
    }, 950);
  }

  function _normTerm(t) {
    const s = String(t || "").trim();
    if (!s) return "";
    if (s.length > 64) return s.slice(0, 64);
    return s;
  }

  function _saveHighlightTerms() {
    try {
      storageSet("pjr_hterms", JSON.stringify(highlightTerms));
    } catch (_e) {}
  }

  function _loadHighlightTerms() {
    try {
      const raw = storageGet("pjr_hterms");
      if (!raw) return;
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) {
        highlightTerms = arr.map(_normTerm).filter(Boolean);
      }
    } catch (_e) {}
  }

  function hasHighlightTerms() {
    return Array.isArray(highlightTerms) && highlightTerms.length > 0;
  }

  function toggleHighlightTerm(term) {
    const t = _normTerm(term);
    if (!t) return;
    const idx = highlightTerms.findIndex((x) => x.toLowerCase() === t.toLowerCase());
    if (idx >= 0) highlightTerms.splice(idx, 1);
    else highlightTerms.push(t);
    _saveHighlightTerms();
    updateHighlightUi();
    renderLog(currentTab);
  }

  function clearHighlightTerms() {
    highlightTerms = [];
    _saveHighlightTerms();
    updateHighlightUi();
    renderLog(currentTab);
  }

  function addHighlightTermFromInput() {
    if (!els.hterm_input) return;
    const t = _normTerm(els.hterm_input.value);
    if (!t) return;
    els.hterm_input.value = "";
    const exists = highlightTerms.some((x) => x.toLowerCase() === t.toLowerCase());
    if (!exists) highlightTerms.push(t);
    _saveHighlightTerms();
    updateHighlightUi();
    renderLog(currentTab);
  }

  function updateHighlightUi() {
    const setPressed = (id, term) => {
      const b = document.getElementById(id);
      if (!b) return;
      const on = highlightTerms.some((x) => x.toLowerCase() === String(term).toLowerCase());
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    };

    setPressed("hterm_error", "ERROR");
    setPressed("hterm_warn", "WARN");
    setPressed("hterm_traceback", "Traceback");

    if (!els.hterms_custom) return;
    els.hterms_custom.textContent = "";

    const builtins = ["ERROR", "WARN", "Traceback"];
    const custom = highlightTerms.filter((t) => !builtins.some((b) => b.toLowerCase() === t.toLowerCase()));

    for (const t of custom) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip small active";
      btn.textContent = t;
      btn.setAttribute("data-action", "toggle-hterm");
      btn.setAttribute("data-term", t);
      btn.setAttribute("aria-pressed", "true");
      els.hterms_custom.appendChild(btn);
    }
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
    storageSet("pjr_pollms", String(pollMs));
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
    currentPage = 1;
    storageSet("pjr_view", next);
    applyFilters();
    setActiveButton("view_", `view_${next}`);
  }

  function setTab(next) {
    currentTab = next;
    storageSet("pjr_tab", next);

    const tStdout = document.getElementById("tab_stdout");
    const tStderr = document.getElementById("tab_stderr");
    const tOverview = document.getElementById("tab_overview");
    if (tStdout) tStdout.classList.toggle("active", next === "stdout");
    if (tStderr) tStderr.classList.toggle("active", next === "stderr");
    if (tOverview) tOverview.classList.toggle("active", next === "overview");

    // Accessibility: keep ARIA tab state in sync with the active tab.
    const tabs = [
      { el: tStdout, selected: next === "stdout" },
      { el: tStderr, selected: next === "stderr" },
      { el: tOverview, selected: next === "overview" },
    ];
    for (const t of tabs) {
      if (!t.el) continue;
      t.el.setAttribute("aria-selected", t.selected ? "true" : "false");
      t.el.tabIndex = t.selected ? 0 : -1;
    }

    const showLogs = (next !== "overview");
    els.overview.hidden = showLogs;
    els.logpanel.style.display = showLogs ? "block" : "none";
    if (els.logtools) els.logtools.style.display = showLogs ? "flex" : "none";
    if (els.hilitebar) els.hilitebar.style.display = showLogs ? "flex" : "none";
    if (els.findbar) els.findbar.style.display = showLogs ? "flex" : "none";

    // Keep tabpanel ARIA state aligned with what is shown.
    if (els.overview) els.overview.setAttribute("aria-hidden", showLogs ? "true" : "false");
    if (els.logpanel) {
      els.logpanel.setAttribute("aria-hidden", showLogs ? "false" : "true");
      const activeTabId = (next === "stderr") ? "tab_stderr" : (next === "overview" ? "tab_overview" : "tab_stdout");
      els.logpanel.setAttribute("aria-labelledby", activeTabId);
    }

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

    const icon = document.createElement("span");
    icon.className = "badge-icon";
    icon.setAttribute("aria-hidden", "true");
    const iconByState = {
      running: "↻",
      queued: "…",
      done: "✓",
      error: "!",
    };
    icon.textContent = iconByState[cls] || "•";

    const label = document.createElement("span");
    label.className = "badge-label";
    label.textContent = cls;

    span.append(icon, label);
    return span;
  }

  

  function updateDensityUi() {
    if (document && document.body) document.body.dataset.density = uiDensity;
  }

  function updateDirectionUi() {
    if (!document || !document.documentElement) return;
    const rootEl = document.documentElement;
    const body = document.body;
    if (uiDirection === "rtl" || uiDirection === "ltr") {
      rootEl.setAttribute("dir", uiDirection);
      if (body) body.setAttribute("dir", uiDirection);
    } else {
      rootEl.removeAttribute("dir");
      if (body) body.removeAttribute("dir");
    }
  }

  function updateClearButtonVisibility() {
    if (!els.clear_filters || !els.search) return;
    const hasSearch = !!String(els.search.value || "").trim();
    const hasSecondary = !!filterHasResult;
    const hasNonDefaultSort = sortMode !== "newest";
    const hasStateFilter = view !== "all";
    const hasUserFilter = !!String(filterUser || "").trim();
    const hasDateFilter = !!String(filterSince || "").trim();
    els.clear_filters.hidden = !(hasSearch || hasSecondary || hasNonDefaultSort || hasStateFilter || hasUserFilter || hasDateFilter);
    if (els.clear_user_filter) els.clear_user_filter.hidden = !hasUserFilter;
  }

  function clearFilters() {
    els.search.value = "";
    setView("all");
    sortMode = "newest";
    filterHasResult = false;
    filterUser = "";
    filterSince = "";
    currentPage = 1;
    if (els.filter_user) els.filter_user.value = "";
    if (els.filter_since) els.filter_since.value = "";
    if (els.job_sort) els.job_sort.value = sortMode;
    if (els.filter_has_result) els.filter_has_result.checked = filterHasResult;
    storageSet("pjr_search", "");
    storageSet("pjr_sort", sortMode);
    storageSet("pjr_has_result", "0");
    storageSet("pjr_filter_user", "");
    storageSet("pjr_filter_since", "");
    applyFilters();
    updateClearButtonVisibility();
    if (typeof updateFiltersSummaryUi === "function") updateFiltersSummaryUi();
  }

  function resetUi() {
    const keys = [
      "pjr_view","pjr_tab","pjr_pollms","pjr_search","pjr_auto","pjr_follow",
      "pjr_wrap","pjr_font","pjr_pause","pjr_hilite","pjr_hterms","pjr_pane","pjr_sort","pjr_has_result","pjr_density","pjr_keep_secondary","pjr_dir","pjr_filter_user","pjr_filter_since","pjr_jobs_pane_width"
    ];
    for (const k of keys) storageRemove(k);
    toast("ok", "Reset", "UI settings cleared");
    window.setTimeout(() => window.location.reload(), 500);
  }

  function _isVisible(el) {
    if (!(el instanceof HTMLElement)) return false;
    const rects = el.getClientRects();
    return !!(rects && rects.length);
  }

  function _focusablesWithin(root) {
    if (!root) return [];
    const sel = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])"
    ].join(",");
    const nodes = Array.from(root.querySelectorAll(sel));
    return nodes.filter((n) => (n instanceof HTMLElement) && _isVisible(n) && n.getAttribute("aria-hidden") !== "true");
  }

  function trapTabKey(ev, root) {
    if (!root) return;
    const focusables = _focusablesWithin(root);
    if (!focusables.length) return;

    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;

    if (!(active instanceof HTMLElement) || !root.contains(active)) {
      (ev.shiftKey ? last : first).focus();
      ev.preventDefault();
      return;
    }

    if (ev.shiftKey) {
      if (active === first) {
        last.focus();
        ev.preventDefault();
      }
      return;
    }

    if (active === last) {
      first.focus();
      ev.preventDefault();
    }
  }



  async function goLive() {
    setPaused(false);
    setFollow(true);
    updateLiveUi();
    if (currentJob) {
      try {
        await refreshMetaAndTail({ forceTail: true });
      } catch (_e) {}
    }
    if (els.logview) {
      programmaticScrollAt = Date.now();
      els.logview.scrollTop = els.logview.scrollHeight;
    }
  }

  async function togglePauseResume() {
    if (paused) {
      await goLive();
      return;
    }
    // Pause means stop consuming new bytes and stop auto-follow.
    setFollow(false);
    setPaused(true, "manual");
  }

  async function jumpLatest() {
    await goLive();
  }

  function clearCurrentLog() {
    const kind = (currentTab === "stderr") ? "stderr" : (currentTab === "stdout" ? "stdout" : "");
    if (!kind) return;

    buffers[kind] = "";
    lastAppend[kind].at = 0;
    lastAppend[kind].from = 0;

    // Keep offsets as-is so we continue from the current tail position.
    els.logview.textContent = "";

    logSearch = "";
    if (els.logsearch) els.logsearch.value = "";
    resetSearch();

    renderLog(kind);
  }

  function isNearBottom(el) {
    const gap = el.scrollHeight - (el.scrollTop + el.clientHeight);
    return gap <= 30;
  }

  function onLogScrollAutoPause() {
    if (!els.logview) return;
    if (paused) return;
    if (!follow) return;
    if (currentTab === "overview") return;

    // Ignore programmatic scrolls.
    if (Date.now() - programmaticScrollAt < 250) return;

    if (!isNearBottom(els.logview)) {
      setFollow(false);
      setPaused(true, "scroll");
    }
  }
function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }


  const SORT_LABELS = {
    newest: "Newest first",
    oldest: "Oldest first",
    active: "Active first",
    errors: "Errors first",
  };

  function updateSortUi() {
    const summary = document.getElementById("sort_summary");
    if (summary) summary.textContent = SORT_LABELS[sortMode] || "Newest first";
    document.querySelectorAll('[data-action="set-sort"]').forEach((btn) => {
      const selected = (btn.getAttribute("data-sort") || "") === sortMode;
      btn.classList.toggle("active", selected);
      btn.setAttribute("aria-checked", selected ? "true" : "false");
    });
  }

  function updateUserFilterOptions(sourceJobs) {
    if (!els.filter_user_list) return;
    const jobs = Array.isArray(sourceJobs) ? sourceJobs : jobsCache;
    const seen = new Set();
    const frag = document.createDocumentFragment();
    for (const j of jobs) {
      const user = String((j && j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name)) || "").trim();
      if (!user) continue;
      const key = user.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      const opt = document.createElement("option");
      opt.value = user;
      frag.appendChild(opt);
    }
    els.filter_user_list.textContent = "";
    els.filter_user_list.appendChild(frag);
  }

  function updatePaginationUi(totalJobs, pageCount) {
    if (!els.jobs_pagination || !els.page_prev || !els.page_next || !els.page_summary) return;
    const pages = Math.max(1, pageCount || 1);
    const total = Math.max(0, totalJobs || 0);
    els.jobs_pagination.hidden = !(total > PAGE_SIZE);
    els.page_prev.disabled = currentPage <= 1;
    els.page_next.disabled = currentPage >= pages;
    els.page_summary.textContent = `Page ${currentPage} of ${pages} · ${total} jobs`;
  }

  function _stateSpecificRowSummary(job) {
    const state = String((job && job.state) || "queued");
    const age = fmtAge(job && job.created_utc) || "Just now";
    const dur = fmtDuration(job && job.duration_seconds) || "Not yet";
    const user = String((job && job.submitted_by && (job.submitted_by.display_name || job.submitted_by.name)) || "").trim();
    const exitText = (job && job.exit_code !== undefined && job.exit_code !== null && String(job.exit_code) !== "") ? `Exit ${job.exit_code}` : "";
    const errorText = String((job && job.error) || "").trim();
    const resultReady = !!(job && job.result_ready);

    if (state === "running") {
      return {
        lead: "Running now",
        pieces: [
          { text: `Duration ${dur}`, cls: "meta-state" },
          user ? { text: user } : null,
          { text: "Live logs available" },
        ].filter(Boolean),
      };
    }
    if (state === "done") {
      return {
        lead: resultReady ? "Archive ready" : "Completed",
        pieces: [
          { text: `Duration ${dur}`, cls: "meta-state" },
          user ? { text: user } : null,
          exitText ? { text: exitText } : { text: "Ready to download" },
        ].filter(Boolean),
      };
    }
    if (state === "error") {
      return {
        lead: errorText ? errorText : "Failed",
        pieces: [
          exitText ? { text: exitText, cls: "meta-state" } : { text: `Duration ${dur}`, cls: "meta-state" },
          user ? { text: user } : null,
          { text: "Open details for stderr" },
        ].filter(Boolean),
      };
    }
    return {
      lead: "Waiting to start",
      pieces: [
        { text: `Queued ${age}`, cls: "meta-state" },
        user ? { text: user } : null,
        { text: "Will run when a worker is free" },
      ].filter(Boolean),
    };
  }

  function _popoverSummaryForJob(job) {
    const state = String((job && job.state) || "queued");
    const user = String((job && job.submitted_by && (job.submitted_by.display_name || job.submitted_by.name)) || "").trim();
    const dur = fmtDuration(job && job.duration_seconds) || "Not yet";
    const exitText = (job && job.exit_code !== undefined && job.exit_code !== null && String(job.exit_code) !== "") ? `Exit ${job.exit_code}` : "";
    const errorText = String((job && job.error) || "").trim();
    const resultReady = !!(job && job.result_ready);

    if (state === "running") {
      return {
        title: "Running",
        body: user ? `${user} started this job. Live output is available now.` : "This job is running and live output is available now.",
        extra: [["Duration", dur], ["Focus", "Watch stdout for progress"]],
      };
    }
    if (state === "done") {
      return {
        title: resultReady ? "Archive ready" : "Completed",
        body: resultReady ? "The result archive is ready to download." : "The job has finished. Open details to inspect outputs and status.",
        extra: [["Duration", dur], ["Outcome", exitText || "Finished"]],
      };
    }
    if (state === "error") {
      return {
        title: "Needs attention",
        body: errorText || "The job failed. Open details to inspect stderr and status.",
        extra: [["Duration", dur], ["Outcome", exitText || "Failed"]],
      };
    }
    return {
      title: "Queued",
      body: user ? `${user} submitted this job. It will start when a worker slot is free.` : "This job is queued and waiting for a worker slot.",
      extra: [["Age", fmtAge(job && job.created_utc) || "Just now"], ["Next step", "Wait for worker availability"]],
    };
  }

  function setDatePreset(preset) {
    const today = new Date();
    const format = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    if (preset === "today") filterSince = format(today);
    else if (preset === "7d") {
      const d = new Date(today);
      d.setDate(d.getDate() - 6);
      filterSince = format(d);
    } else filterSince = "";
    if (els.filter_since) els.filter_since.value = filterSince;
    storageSet("pjr_filter_since", filterSince);
    currentPage = 1;
    applyFilters();
    updateClearButtonVisibility();
    if (typeof updateFiltersSummaryUi === "function") updateFiltersSummaryUi();
  }

  function renderLog(kind) {
    if (kind === "overview") return;
    const txt = buffers[kind] || "";

    const needHtml = !!hilite || hasHighlightTerms();
    if (!needHtml) {
      els.logview.textContent = txt;
      applyLogStyle();
      return;
    }

    const MAX_RENDER = 200000;
    const truncated = (txt.length > MAX_RENDER);
    const sliceStart = truncated ? (txt.length - MAX_RENDER) : 0;
    const slice = truncated ? txt.slice(-MAX_RENDER) : txt;

    const lines = slice.split("\n");
    const out = [];

    // New line window: mark recently appended lines for a short period.
    const meta = (lastAppend && lastAppend[kind]) ? lastAppend[kind] : null;
    const showNew = !!(meta && meta.at && (Date.now() - meta.at) < 2500);
    const newFrom = showNew ? Math.max(0, (meta.from || 0) - sliceStart) : 1e12;

    const terms = Array.isArray(highlightTerms) ? highlightTerms.slice(0) : [];
    const termsUpper = terms.map((t) => String(t || "").toUpperCase()).filter(Boolean);

    let pos = 0;
    for (const line of lines) {
      const lineStart = pos;
      pos += line.length + 1;

      const esc = escapeHtml(line);
      let cls = "logline";

      const u = line.toUpperCase();

      if (hilite) {
        if (u.includes("TRACEBACK") || u.includes("ERROR") || u.includes("EXCEPTION")) cls += " err";
        else if (u.includes("WARN")) cls += " warn";
      }

      if (termsUpper.length) {
        for (const t of termsUpper) {
          if (t && u.includes(t)) {
            cls += " hit";
            break;
          }
        }
      }

      if (showNew && lineStart >= newFrom) {
        cls += " new";
      }

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
    const visibleTxt = (els.logview && typeof els.logview.textContent === "string") ? els.logview.textContent : "";
    const re = /(Traceback|ERROR|Exception|FATAL|WARN(ING)?)/gi;

    // Prefer searching the rendered log text (what computeMatches() uses) so indices align.
    const start = (visibleTxt && matches && matchIdx >= 0 && matchIdx < matches.length) ? matches[matchIdx] : 0;
    re.lastIndex = start + 1;
    let m = visibleTxt ? (re.exec(visibleTxt) || re.exec(visibleTxt)) : null;

    // Fallback: if nothing is rendered (or no match), search the raw buffer.
    if (!m) {
      const rawTxt = buffers[kind] || "";
      re.lastIndex = 0;
      m = re.exec(rawTxt);
      if (!m) {
        toast("ok", "No errors found", "No ERROR/WARN/Traceback lines found");
        return;
      }
      // We cannot reliably translate raw indices to rendered indices, so jump to the first visible match.
      logSearch = m[0];
      els.logsearch.value = logSearch;
      computeMatches();
      matchIdx = 0;
      scrollToMatch();
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
    const userQ = String(filterUser || "").trim().toLowerCase();
    const sinceTs = filterSince ? Math.floor(Date.parse(`${filterSince}T00:00:00`) / 1000) : 0;
    let jobs = jobsCache.slice(0);

    if (view !== "all") {
      jobs = jobs.filter((j) => (j.state || "queued") === view);
    }

    if (filterHasResult) {
      jobs = jobs.filter((j) => !!j.result_ready);
    }

    if (userQ) {
      jobs = jobs.filter((j) => {
        const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name) || "").toLowerCase();
        return user.includes(userQ);
      });
    }

    if (sinceTs) {
      jobs = jobs.filter((j) => parseUtcSeconds(j.created_utc) >= sinceTs);
    }

    if (q) {
      jobs = jobs.filter((j) => {
        const id = (j.job_id || "").toLowerCase();
        const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name) || "").toLowerCase();
        const st = (j.state || "queued").toLowerCase();
        return id.includes(q) || user.includes(q) || st.includes(q);
      });
    }

    const statePriority = {
      active: { running: 0, queued: 1, error: 2, done: 3 },
      errors: { error: 0, running: 1, queued: 2, done: 3 },
    };

    jobs.sort((a, b) => {
      const ta = parseUtcSeconds(a.created_utc);
      const tb = parseUtcSeconds(b.created_utc);
      if (sortMode === "oldest") return ta - tb;
      if (sortMode === "active" || sortMode === "errors") {
        const order = statePriority[sortMode];
        const sa = order[a.state] ?? 9;
        const sb = order[b.state] ?? 9;
        if (sa !== sb) return sa - sb;
      }
      return tb - ta;
    });

    const totalJobs = jobs.length;
    const pageCount = Math.max(1, Math.ceil(totalJobs / PAGE_SIZE));
    if (currentPage > pageCount) currentPage = pageCount;
    if (currentPage < 1) currentPage = 1;
    const startIdx = (currentPage - 1) * PAGE_SIZE;
    const pagedJobs = jobs.slice(startIdx, startIdx + PAGE_SIZE);

    renderJobs(pagedJobs, q, totalJobs, pageCount);
    updateSortUi();
    updatePaginationUi(totalJobs, pageCount);
    updateClearButtonVisibility();
  }

  /**
   * Ensure a table row exists for the given job id, creating and initialising one with controls if necessary.
   * The created row contains job metadata cells, action controls (View, Zip, Copy id) and attaches the appropriate event handlers.
   * @param {string} jobId - The job identifier.
   * @returns {HTMLTableRowElement|null} The existing or newly created table row element for the job, or `null` if `jobId` is falsy.
   */
  function _ensureRow(jobId) {
    if (!jobId) return null;
    let tr = els.jobtable_tbody.querySelector(`tr[data-job-id="${CSS.escape(jobId)}"]`);
    if (tr) return tr;

    tr = document.createElement("tr");
    tr.dataset.jobId = jobId;
    tr.tabIndex = 0;
    tr.className = "job-row";
    tr.addEventListener("click", (ev) => {
      const target = ev.target;
      if (target instanceof Element && target.closest("button,a,summary,details,input,select,textarea,label")) return;
      selectJob(tr.dataset.jobId || "");
    });
    tr.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        selectJob(tr.dataset.jobId || "");
      }
      if (ev.key === "ContextMenu" || (ev.shiftKey && ev.key === "F10")) {
        ev.preventDefault();
        const rect = tr.getBoundingClientRect();
        openRowMenu(tr.dataset.jobId || "", rect.left + 20, rect.top + 16);
      }
    });
    tr.addEventListener("contextmenu", (ev) => {
      ev.preventDefault();
      openRowMenu(tr.dataset.jobId || "", ev.clientX, ev.clientY);
    });

    const scheduleHoverOpen = (anchor) => {
      if (!hasFinePointer()) return;
      window.clearTimeout(hoverPopoverCloseTimer);
      window.clearTimeout(hoverPopoverTimer);
      hoverPopoverTimer = window.setTimeout(() => {
        openRowPopover(tr.dataset.jobId || "", anchor, undefined, "hover");
      }, 320);
    };
    const scheduleHoverClose = () => {
      if (!hasFinePointer()) return;
      window.clearTimeout(hoverPopoverTimer);
      hoverPopoverCloseTimer = window.setTimeout(() => {
        if (rowPopoverMode === "hover") closeRowPopover(true);
      }, 160);
    };

    tr.addEventListener("touchstart", (ev) => {
      const target = ev.target;
      if (target instanceof Element && target.closest("button,a,summary,details,input,select,textarea,label")) return;
      const touch = ev.touches && ev.touches[0];
      if (!touch) return;
      window.clearTimeout(_rowMenuTouchTimer);
      _rowMenuTouchTimer = window.setTimeout(() => {
        openRowMenu(tr.dataset.jobId || "", touch.clientX, touch.clientY);
      }, 450);
    }, { passive: true });
    const clearTouchMenu = () => {
      if (_rowMenuTouchTimer) {
        window.clearTimeout(_rowMenuTouchTimer);
        _rowMenuTouchTimer = null;
      }
    };
    tr.addEventListener("touchend", clearTouchMenu, { passive: true });
    tr.addEventListener("touchcancel", clearTouchMenu, { passive: true });
    tr.addEventListener("touchmove", clearTouchMenu, { passive: true });

    const tdJob = document.createElement("td");
    tdJob.setAttribute("data-label", "Job");
    const wrap = document.createElement("div");
    wrap.className = "jobcell";
    const line = document.createElement("div");
    line.className = "jobline";

    const btnJob = document.createElement("button");
    btnJob.type = "button";
    btnJob.className = "small jobbtn tooltip-target hover-preview-trigger";
    btnJob.setAttribute("data-tooltip", "Open details");
    btnJob.addEventListener("click", () => selectJob(tr.dataset.jobId || ""));
    btnJob.addEventListener("mouseenter", () => scheduleHoverOpen(btnJob));
    btnJob.addEventListener("mouseleave", scheduleHoverClose);

    const inlineState = document.createElement("button");
    inlineState.type = "button";
    inlineState.className = "state-badge-inline state-badge-trigger tooltip-target hover-preview-trigger";
    inlineState.setAttribute("aria-label", "Quick peek");
    inlineState.setAttribute("data-tooltip", "Quick peek");
    inlineState.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      openRowPopover(tr.dataset.jobId || "", inlineState, undefined, "manual");
    });
    inlineState.addEventListener("mouseenter", () => scheduleHoverOpen(inlineState));
    inlineState.addEventListener("mouseleave", scheduleHoverClose);

    line.append(btnJob, inlineState);

    const meta = document.createElement("div");
    meta.className = "jobmeta";

    const progressShell = document.createElement("div");
    progressShell.className = "row-progress-shell";
    progressShell.hidden = true;
    const progress = document.createElement("div");
    progress.className = "progress row-progress";
    progress.setAttribute("role", "progressbar");
    progress.setAttribute("aria-label", "Job progress");
    const progressBar = document.createElement("div");
    progressBar.className = "progress-bar";
    progress.appendChild(progressBar);
    const progressCopy = document.createElement("div");
    progressCopy.className = "row-progress-copy";
    progressShell.append(progress, progressCopy);

    wrap.append(line, meta, progressShell);
    tdJob.appendChild(wrap);

    const tdState = document.createElement("td");
    tdState.setAttribute("data-label", "State");
    const stateBtn = document.createElement("button");
    stateBtn.type = "button";
    stateBtn.className = "state-badge-trigger tooltip-target hover-preview-trigger";
    stateBtn.setAttribute("aria-label", "Quick peek");
    stateBtn.setAttribute("data-tooltip", "Quick peek");
    stateBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      openRowPopover(tr.dataset.jobId || "", stateBtn, undefined, "manual");
    });
    stateBtn.addEventListener("mouseenter", () => scheduleHoverOpen(stateBtn));
    stateBtn.addEventListener("mouseleave", scheduleHoverClose);
    tdState.appendChild(stateBtn);

    const tdAge = document.createElement("td");
    tdAge.setAttribute("data-label", "Age");
    const tdDur = document.createElement("td");
    tdDur.setAttribute("data-label", "Duration");
    const tdUser = document.createElement("td");
    tdUser.setAttribute("data-label", "User");
    const tdActions = document.createElement("td");
    tdActions.className = "actions";
    tdActions.setAttribute("data-label", "Actions");

    const btnView = document.createElement("button");
    btnView.type = "button";
    btnView.className = "small primary row-view";
    btnView.textContent = "View";
    btnView.addEventListener("click", () => selectJob(tr.dataset.jobId || ""));

    const overflow = document.createElement("button");
    overflow.type = "button";
    overflow.className = "small tertiary row-overflow tooltip-target";
    overflow.setAttribute("aria-label", "More row actions");
    overflow.setAttribute("data-tooltip", "More actions");
    overflow.textContent = "⋯";
    overflow.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      openRowMenu(tr.dataset.jobId || "", overflow);
    });

    tdActions.append(btnView, overflow);
    tr.append(tdJob, tdState, tdAge, tdDur, tdUser, tdActions);
    return tr;
  }

  function _patchRow(tr, j) {
    const jobId = j.job_id || "";
    const user = (j.submitted_by && (j.submitted_by.display_name || j.submitted_by.name)) || "";
    const state = j.state || "queued";
    const age = fmtAge(j.created_utc);
    const dur = fmtDuration(j.duration_seconds);

    tr.dataset.jobId = jobId;
    tr.dataset.state = state;
    const isSelected = !!(currentJob && jobId === currentJob);
    tr.classList.toggle("selected", isSelected);
    tr.setAttribute("aria-selected", isSelected ? "true" : "false");

    const tdJob = tr.children[0];
    const btnJob = tdJob.querySelector(".jobbtn");
    if (btnJob) {
      btnJob.textContent = jobId;
      btnJob.title = jobId;
    }
    tr.setAttribute("aria-label", `Job ${jobId}, ${state}`);

    const meta = tdJob.querySelector(".jobmeta");
    if (meta) {
      meta.textContent = "";
      const summary = _stateSpecificRowSummary(j);
      const addMeta = (value, extraCls) => {
        const v = String(value || "").trim();
        if (!v) return;
        const span = document.createElement("span");
        span.className = `meta${extraCls ? ` ${extraCls}` : ""}`;
        span.textContent = v;
        meta.appendChild(span);
      };

      addMeta(summary.lead, "meta-primary");
      for (const piece of summary.pieces) addMeta(piece.text, piece.cls || "");
    }

    const inlineState = tdJob.querySelector(".state-badge-inline");
    if (inlineState) {
      inlineState.textContent = "";
      inlineState.appendChild(badgeEl(state));
    }

    const progressShell = tdJob.querySelector(".row-progress-shell");
    if (progressShell) {
      const showProgress = state === "running" || state === "queued" || state === "error" || state === "done";
      progressShell.hidden = !showProgress;
      if (showProgress) {
        _applyProgressUi(progressShell.querySelector(".row-progress"), progressShell.querySelector(".progress-bar"), progressShell.querySelector(".row-progress-copy"), state);
      }
    }

    const tdState = tr.children[1];
    if (!tdState) return;
    const stateBtn = tdState.querySelector(".state-badge-trigger");
    if (stateBtn) {
      stateBtn.textContent = "";
      stateBtn.appendChild(badgeEl(state));
    }

    tr.children[2].textContent = age;
    tr.children[3].textContent = dur;
    tr.children[4].textContent = user;

    const zip = tr.children[5].querySelector("a");
    if (zip) zip.href = `result/${encodeURIComponent(jobId)}.zip`;
  }

  /**
   * Render a list of job objects into the jobs table and update the empty-state UI.
   *
   * Updates the jobs table body to reflect the provided jobs: ensures rows exist, updates each row's content, removes stale rows, and appends the current set. When no jobs are supplied, updates the empty-state visibility and adjusts the empty title, body and action text based on the current view, query and connection/loading state.
   *
   * @param {Array<Object>} jobs - Array of job objects to display; each should include a `job_id` property.
   * @param {string} [query] - Current search/filter query used to choose appropriate empty-state messaging.
   */
  function renderJobs(jobs, query, totalJobs, pageCount) {
    const tbody = els.jobtable_tbody;
    const hasJobs = jobs.length !== 0;
    els.empty.hidden = hasJobs;
    const tableWrap = document.querySelector(".tablewrap");
    const tableRegion = document.querySelector(".table-region");
    if (tableWrap) tableWrap.hidden = !hasJobs;
    if (tableRegion) tableRegion.classList.toggle("has-jobs", hasJobs);
    if (els.jobs_count) els.jobs_count.textContent = String(totalJobs || jobs.length);
    if (els.jobs_pagination) els.jobs_pagination.hidden = !(hasJobs && (totalJobs || 0) > PAGE_SIZE);

    if (!hasJobs) {
      const emptyTitle = document.getElementById("empty_title");
      const emptyBody = document.getElementById("empty_body");
      if (emptyTitle && emptyBody) {
        if (jobsViewState === "initial") {
          emptyTitle.textContent = "Loading jobs";
          emptyBody.textContent = "Connecting and fetching jobs now. The jobs list will appear automatically.";
        } else if (jobsViewState === "disconnected") {
          emptyTitle.textContent = "Cannot connect";
          emptyBody.textContent = "The runner is unreachable right now. Check connection details and retry refresh.";
        } else if (view !== "all" || (query && String(query).trim()) || String(filterUser || "").trim() || String(filterSince || "").trim()) {
          emptyTitle.textContent = "No matching jobs";
          emptyBody.textContent = "No jobs match the current search/filter. Clear search or switch state filters.";
        } else {
          emptyTitle.textContent = "No jobs yet";
          emptyBody.textContent = "Copy the sample task, run it from Pythonista, then return here to open the first job.";
        }

        const emptyAction = document.getElementById("empty_action");
        if (emptyAction) {
          if (jobsViewState === "disconnected") {
            emptyAction.textContent = "Use header Refresh. If it persists, open Help for troubleshooting steps.";
          } else if (view !== "all" || (query && String(query).trim()) || String(filterUser || "").trim() || String(filterSince || "").trim()) {
            emptyAction.textContent = "Use Clear to reset search and filters quickly.";
          } else {
            emptyAction.textContent = "Quick start has the step-by-step path if you want a guided first run.";
          }
        }
      }
    }

    const seen = new Set();
    const frag = document.createDocumentFragment();

    for (const j of jobs) {
      const jobId = j.job_id || "";
      if (!jobId) continue;
      const tr = _ensureRow(jobId);
      if (!tr) continue;
      _patchRow(tr, j);
      seen.add(jobId);
      frag.appendChild(tr);
    }

    for (const row of Array.from(tbody.querySelectorAll("tr[data-job-id]"))) {
      if (!seen.has(row.dataset.jobId || "")) row.remove();
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

    const queueSummary = document.getElementById("queue_summary_text");
    if (queueSummary) {
      const bits = [`${total} total`];
      if (running) bits.push(`${running} running`);
      if (queued) bits.push(`${queued} queued`);
      if (error) bits.push(`${error} errors`);
      queueSummary.textContent = bits.join(" · ");
    }

    const haHost = currentHomeAssistantHost();
    if (els.ha_host_pill) {
      els.ha_host_pill.hidden = !haHost;
    }
    if (els.ha_host_label && haHost) {
      els.ha_host_label.textContent = `Home Assistant ${haHost}`;
    }
    if (els.meta_ha_host) {
      els.meta_ha_host.hidden = !haHost;
      const strong = els.meta_ha_host.querySelector("strong");
      if (strong) strong.textContent = haHost;
    }

    const ingressStrict = !!s.ingress_strict;
    const cidrs = Array.isArray(s.api_allow_cidrs) ? s.api_allow_cidrs : [];
    const accessMode = ingressStrict ? "Ingress only" : "Ingress or direct API";
    const allowedCidrsText = ingressStrict
      ? "Not used while Ingress-only mode is on"
      : (cidrs.length ? cidrs.join(", ") : "Any direct IP address");

    if (els.meta_access_mode) {
      els.meta_access_mode.hidden = false;
      const strong = els.meta_access_mode.querySelector("strong");
      if (strong) strong.textContent = accessMode;
    }
    if (els.meta_allowed_cidrs) {
      els.meta_allowed_cidrs.hidden = false;
      const strong = els.meta_allowed_cidrs.querySelector("strong");
      if (strong) strong.textContent = allowedCidrsText;
    }

    els.stats.hidden = false;
  }

  async function refreshStats() {
    const s = await api("stats.json");
    renderStats(s);
  }

  async function refreshJobs(opts) {
    const silent = !!(opts && opts.silent);
    if (els.jobs_loading && !silent) {
      if (firstJobsLoad) els.jobs_loading.hidden = false;
    }
    try {
      const data = await api("jobs.json");
      jobsCache = (data && Array.isArray(data.jobs)) ? data.jobs : [];
      updateUserFilterOptions(jobsCache);
      applyFilters();
    } finally {
      if (els.jobs_loading && !silent) {
        if (firstJobsLoad) els.jobs_loading.hidden = true;
      }
      firstJobsLoad = false;
    }
  }

  async function performPurgeState(state) {
    if (!state) return;
    await api("purge", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ state }),
    });
    toast("ok", "Purge complete", `Purged ${state} jobs`);
    await refreshAll();
  }

  async function purgeState(state) {
    if (!state) return;
    openConfirm({
      title: `Purge ${state} jobs?`,
      body: "This removes job files for the selected job state.",
      confirmLabel: `Purge ${state}`,
      onConfirm: async () => performPurgeState(state),
    });
  }

  function parseEndpointPath(v) {
    const s = String(v || "").trim();
    if (!s) return "";
    const parts = s.split(/\s+/, 2);
    if (parts.length === 2 && /^[A-Z]+$/.test(parts[0]) && parts[1].startsWith("/") && !parts[1].startsWith("//")) {
      return parts[1];
    }
    if (s.startsWith("/") && !s.startsWith("//")) return s;
    return "";
  }

  function renderInfo(info) {
    const i = info || {};
    const service = i.service ? String(i.service) : "pythonista_job_runner";
    const version = i.version ? String(i.version) : "";
    els.about_sub.textContent = version ? `${service} v${version}` : service;

    const endpoints = i.endpoints || {};
    const keys = Object.keys(endpoints).sort();
    const core = ["health", "run", "jobs", "stats", "info", "tail", "job", "result", "cancel", "purge"];
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
      btn.className = "small secondary";
      btn.textContent = "Copy";
      btn.setAttribute("data-action", "copy-endpoint");
      btn.setAttribute("data-endpoint", k);

      const p = parseEndpointPath(raw);
      const canCopy = core.some((n) => k.toLowerCase().includes(n));
      if (p && canCopy) {
        btn.setAttribute("data-copy", apiUrl(p));
      } else {
        btn.hidden = true;
      }

      row.append(left, btn);
      els.about_api.appendChild(row);
    }

    const base = baseUrl();
    const pythonSample = [
      "import io",
      "import json",
      "import zipfile",
      "import requests",
      "",
      `BASE = "${base}"`,
      'TOKEN = "YOUR_TOKEN_HERE"  # Needed for direct access',
      "",
      "task_code = 'print(\"hello from Pythonista\")'",
      "zip_buf = io.BytesIO()",
      'with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:',
      '    zf.writestr("main.py", task_code)',
      "zip_buf.seek(0)",
      "",
      'headers = {"X-Runner-Token": TOKEN}',
      'files = {"file": ("task.zip", zip_buf.getvalue(), "application/zip")}',
      'res = requests.post(f"{BASE}/run", headers=headers, files=files, timeout=30)',
      "res.raise_for_status()",
      "payload = res.json()",
      "print(json.dumps(payload, indent=2))",
      "",
      "# Success: a job_id is returned; open it in the Jobs list and watch for done + result zip.",
    ].join("\n");
    const curl = [
      `# ${service} ${version ? `v${version}` : ""}`.trim(),
      "# Direct access requires X-Runner-Token unless you are using Ingress",
      `BASE="${base}"`,
      'TOKEN="YOUR_TOKEN_HERE"',
      "",
      'curl -H "X-Runner-Token: $TOKEN" "$BASE/health"',
      'curl -H "X-Runner-Token: $TOKEN" "$BASE/jobs.json"',
      'curl -H "X-Runner-Token: $TOKEN" "$BASE/stats.json"',
      "# /run needs a zip payload from Pythonista (see sample above)",
    ].join("\n");
    if (els.about_python) els.about_python.value = pythonSample;
    els.about_curl.value = curl;
  }

  async function loadInfo() {
    infoCache = await api("info.json");
    renderInfo(infoCache);
  }


  async function copySampleTask() {
    const txt = (els.about_python && els.about_python.value) ? els.about_python.value : "";
    if (!txt) {
      await loadInfo();
    }
    const code = (els.about_python && els.about_python.value) ? els.about_python.value : "";
    if (!code) {
      toast("err", "No sample available", "Could not prepare sample Python task");
      return;
    }
    await copyTextToClipboard(code);
    toast("ok", "Copied", "Sample Python task copied");
  }


  async function copyAboutCurl() {
    const txt = (els.about_curl && els.about_curl.value) ? els.about_curl.value : "";
    if (!txt) {
      await loadInfo();
    }
    const code = (els.about_curl && els.about_curl.value) ? els.about_curl.value : "";
    if (!code) {
      toast("err", "No sample available", "Could not prepare curl sample");
      return;
    }
    await copyTextToClipboard(code);
    toast("ok", "Copied", "curl sample copied");
  }

  let _aboutReturnFocus = null;
  let _advReturnFocus = null;
  let _setupReturnFocus = null;
  let _settingsReturnFocus = null;
  let _commandReturnFocus = null;
  let _confirmReturnFocus = null;
  let confirmActionHandler = null;
  let _rowMenuJobId = null;
  let _rowMenuReturnFocus = null;
  let _rowMenuTouchTimer = null;
  let _rowPopoverJobId = null;
  let _rowPopoverReturnFocus = null;



  function _jobById(jobId) {
    return jobsCache.find((j) => (j.job_id || "") === String(jobId || "")) || null;
  }

  function _progressModelForState(state) {
    const st = String(state || "queued");
    if (st === "running") return { cls: "running", label: "Running now", detail: "Work is in progress." };
    if (st === "queued") return { cls: "queued", label: "Queued", detail: "Waiting for an execution slot." };
    if (st === "done") return { cls: "done", label: "Completed", detail: "Finished successfully." };
    if (st === "error") return { cls: "error", label: "Failed", detail: "Finished with an error." };
    return { cls: "queued", label: st || "Queued", detail: "Lifecycle information." };
  }

  function _applyProgressUi(progressEl, barEl, copyEl, state) {
    if (!(progressEl instanceof HTMLElement) || !(barEl instanceof HTMLElement)) return;
    const model = _progressModelForState(state);
    progressEl.className = `progress ${model.cls}`;
    if (copyEl instanceof HTMLElement) copyEl.textContent = model.detail;
    progressEl.setAttribute("aria-valuetext", model.label);
    if (model.cls === "done") {
      progressEl.setAttribute("aria-valuenow", "100");
    } else if (model.cls === "error") {
      progressEl.setAttribute("aria-valuenow", "100");
    } else {
      progressEl.removeAttribute("aria-valuenow");
    }
  }

  function _renderPopoverMeta(container, label, value) {
    const v = String(value || "").trim();
    if (!v || !(container instanceof HTMLElement)) return;
    const row = document.createElement("div");
    row.className = "item-slab";
    const copy = document.createElement("div");
    copy.className = "item-copy";
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = label;
    copy.appendChild(title);
    const meta = document.createElement("div");
    meta.className = "item-meta";
    meta.textContent = v;
    row.append(copy, meta);
    container.appendChild(row);
  }

  function commandItems() {
    return [
      { key: "refresh", title: "Refresh now", description: "Reload queue stats, jobs, and the selected detail view.", hint: "Action", action: async () => refreshAll() },
      { key: "search", title: "Focus search", description: "Jump straight to the Jobs search field.", hint: "/", action: async () => { if (els.search) els.search.focus(); } },
      { key: "settings", title: "Open settings", description: "Change runtime and UI preferences.", hint: "Panel", action: async () => openSettings() },
      { key: "help", title: "Open help", description: "See quick start, samples, and troubleshooting.", hint: "Panel", action: async () => openAbout() },
      { key: "setup", title: "Open setup", description: "Check package setup readiness for example 5.", hint: "Panel", action: async () => openSetup() },
      { key: "maintenance", title: "Open maintenance tools", description: "Open advanced cleanup and reset actions.", hint: "Panel", action: async () => openAdvanced() },
      { key: "sample", title: "Copy sample Python task", description: "Copy the quick-start Python task to the clipboard.", hint: "Copy", action: async () => copySampleTask() },
    ];
  }

  function updateCommandList(filterText) {
    if (!els.command_list) return;
    const q = String(filterText || "").trim().toLowerCase();
    els.command_list.textContent = "";
    for (const item of commandItems()) {
      const hay = `${item.title} ${item.description}`.toLowerCase();
      if (q && !hay.includes(q)) continue;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "small tertiary command-item";
      btn.setAttribute("data-action", "command-run");
      btn.setAttribute("data-command", item.key);

      const copy = document.createElement("span");
      copy.className = "item-copy";
      const title = document.createElement("span");
      title.className = "item-title";
      title.textContent = item.title;
      const desc = document.createElement("span");
      desc.className = "item-description";
      desc.textContent = item.description;
      copy.append(title, desc);

      const hint = document.createElement("span");
      hint.className = "command-hint";
      hint.textContent = item.hint;

      btn.append(copy, hint);
      els.command_list.appendChild(btn);
    }
    if (!els.command_list.children.length) {
      const empty = document.createElement("div");
      empty.className = "hint compact-hint";
      empty.textContent = "No commands match that search.";
      els.command_list.appendChild(empty);
    }
  }

  async function runCommand(key) {
    const found = commandItems().find((item) => item.key === key);
    if (!found) return;
    closeCommand();
    await found.action();
  }

  function openCommand() {
    _commandReturnFocus = (document.activeElement instanceof HTMLElement) ? document.activeElement : null;
    els.command_overlay.hidden = false;
    els.command_overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.height = "100%";
    document.body.style.height = "100%";
    if (els.command_input) {
      els.command_input.value = "";
      updateCommandList("");
      els.command_input.focus();
    } else if (els.command_modal) {
      els.command_modal.focus();
    }
  }

  function closeCommand() {
    if (!els.command_overlay) return;
    els.command_overlay.hidden = true;
    els.command_overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    document.documentElement.style.height = "";
    document.body.style.height = "";
    if (_commandReturnFocus && document.contains(_commandReturnFocus)) {
      try { _commandReturnFocus.focus(); } catch (_e) {}
    }
    _commandReturnFocus = null;
  }

  function positionFloatingMenu(el, x, y) {
    if (!(el instanceof HTMLElement)) return;
    const pad = 10;
    const maxLeft = Math.max(pad, window.innerWidth - el.offsetWidth - pad);
    const maxTop = Math.max(pad, window.innerHeight - el.offsetHeight - pad);
    el.style.left = `${Math.min(maxLeft, Math.max(pad, x))}px`;
    el.style.top = `${Math.min(maxTop, Math.max(pad, y))}px`;
  }

  function openRowMenu(jobId, anchorOrX, maybeY) {
    if (!jobId || !els.row_menu) return;
    _rowMenuJobId = jobId;
    _rowMenuReturnFocus = (document.activeElement instanceof HTMLElement) ? document.activeElement : null;
    if (els.row_menu_label) els.row_menu_label.textContent = `Job ${jobId}`;
    if (els.row_menu_zip) els.row_menu_zip.href = apiUrl(`result/${encodeURIComponent(jobId)}.zip`);
    els.row_menu.hidden = false;
    let x = 16;
    let y = 16;
    if (anchorOrX instanceof HTMLElement) {
      const rect = anchorOrX.getBoundingClientRect();
      x = rect.right - 180;
      y = rect.bottom + 6;
    } else {
      x = Number(anchorOrX) || x;
      y = Number(maybeY) || y;
    }
    positionFloatingMenu(els.row_menu, x, y);
  }

  function closeRowMenu() {
    if (!els.row_menu) return;
    els.row_menu.hidden = true;
    _rowMenuJobId = null;
    if (_rowMenuReturnFocus && document.contains(_rowMenuReturnFocus)) {
      try { _rowMenuReturnFocus.focus(); } catch (_e) {}
    }
    _rowMenuReturnFocus = null;
  }

  async function runRowMenuAction(action) {
    const jobId = _rowMenuJobId;
    closeRowMenu();
    if (!jobId) return;
    if (action === "view") {
      await selectJob(jobId);
      return;
    }
    if (action === "copy-id") {
      await copyTextToClipboard(jobId);
      toast("ok", "Copied", "Job id copied");
      return;
    }
    if (action === "stdout" || action === "stderr" || action === "curl") {
      if (currentJob !== jobId) await selectJob(jobId);
      if (action === "stdout") downloadText("stdout");
      else if (action === "stderr") downloadText("stderr");
      else await copyCurl();
      return;
    }
  }


  function openRowPopover(jobId, anchorOrX, maybeY, mode) {
    if (!jobId || !els.row_popover) return;
    const job = _jobById(jobId);
    if (!job) return;
    rowPopoverMode = mode || "manual";
    _rowPopoverJobId = jobId;
    _rowPopoverReturnFocus = rowPopoverMode === "manual" && (document.activeElement instanceof HTMLElement) ? document.activeElement : null;
    if (els.row_popover_label) els.row_popover_label.textContent = rowPopoverMode === "hover" ? `Preview ${jobId}` : `Job ${jobId}`;
    els.row_popover.dataset.mode = rowPopoverMode;
    const summary = _popoverSummaryForJob(job);
    if (els.row_popover_summary && els.row_popover_summary_title && els.row_popover_summary_body) {
      els.row_popover_summary.hidden = false;
      els.row_popover_summary_title.textContent = summary.title;
      els.row_popover_summary_body.textContent = summary.body;
    }
    if (els.row_popover_list) {
      els.row_popover_list.textContent = "";
      _renderPopoverMeta(els.row_popover_list, "State", String(job.state || "queued"));
      _renderPopoverMeta(els.row_popover_list, "Age", fmtAge(job.created_utc) || "Just now");
      const user = (job.submitted_by && (job.submitted_by.display_name || job.submitted_by.name)) || "";
      _renderPopoverMeta(els.row_popover_list, "User", user || "Unknown");
      for (const [label, value] of summary.extra || []) _renderPopoverMeta(els.row_popover_list, label, value);
      if (job.exit_code !== undefined && job.exit_code !== null && String(job.exit_code) !== "") _renderPopoverMeta(els.row_popover_list, "Exit", String(job.exit_code));
    }
    if (els.row_popover_progress_shell) {
      const showProgress = ["running", "queued", "done", "error"].includes(String(job.state || "queued"));
      els.row_popover_progress_shell.hidden = !showProgress;
      if (showProgress) _applyProgressUi(els.row_popover_progress, els.row_popover_progress_bar, els.row_popover_progress_copy, job.state);
    }
    els.row_popover.hidden = false;
    let x = 16;
    let y = 16;
    if (anchorOrX instanceof HTMLElement) {
      const rect = anchorOrX.getBoundingClientRect();
      x = rect.left;
      y = rect.bottom + 8;
    } else {
      x = Number(anchorOrX) || x;
      y = Number(maybeY) || y;
    }
    positionFloatingMenu(els.row_popover, x, y);
  }

  function closeRowPopover(silent) {
    if (!els.row_popover) return;
    els.row_popover.hidden = true;
    _rowPopoverJobId = null;
    if (!silent && _rowPopoverReturnFocus && document.contains(_rowPopoverReturnFocus)) {
      try { _rowPopoverReturnFocus.focus(); } catch (_e) {}
    }
    _rowPopoverReturnFocus = null;
  }

  async function runRowPopoverAction(action) {
    const jobId = _rowPopoverJobId;
    closeRowPopover();
    if (!jobId) return;
    if (action === "view") await selectJob(jobId);
  }

  function goToNextPage(step) {
    currentPage = Math.max(1, currentPage + step);
    applyFilters();
  }

  function openConfirm(opts) {
    confirmActionHandler = (opts && typeof opts.onConfirm === "function") ? opts.onConfirm : null;
    _confirmReturnFocus = (document.activeElement instanceof HTMLElement) ? document.activeElement : null;
    if (els.confirm_title) els.confirm_title.textContent = (opts && opts.title) ? String(opts.title) : "Confirm action";
    if (els.confirm_body) els.confirm_body.textContent = (opts && opts.body) ? String(opts.body) : "Are you sure?";
    if (els.confirm_accept) els.confirm_accept.textContent = (opts && opts.confirmLabel) ? String(opts.confirmLabel) : "Confirm";
    els.confirm_overlay.hidden = false;
    els.confirm_overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.height = "100%";
    document.body.style.height = "100%";
    if (els.confirm_accept) els.confirm_accept.focus();
    else if (els.confirm_modal) els.confirm_modal.focus();
  }

  function closeConfirm() {
    if (!els.confirm_overlay) return;
    els.confirm_overlay.hidden = true;
    els.confirm_overlay.setAttribute("aria-hidden", "true");
    confirmActionHandler = null;
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    document.documentElement.style.height = "";
    document.body.style.height = "";
    if (_confirmReturnFocus && document.contains(_confirmReturnFocus)) {
      try { _confirmReturnFocus.focus(); } catch (_e) {}
    }
    _confirmReturnFocus = null;
  }

  async function acceptConfirm() {
    if (typeof confirmActionHandler !== "function") {
      closeConfirm();
      return;
    }
    const fn = confirmActionHandler;
    closeConfirm();
    await fn();
  }

  async function openAbout() {
    _aboutReturnFocus = (document.activeElement instanceof HTMLElement) ? document.activeElement : null;
    els.about_overlay.hidden = false;
    els.about_overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.height = "100%";
    document.body.style.height = "100%";
    if (els.about_close) els.about_close.focus();
    else if (els.about_modal) els.about_modal.focus();
    try {
      await loadInfo();
    } catch (e) {
      els.about_sub.textContent = "Help";
      els.about_api.textContent = "";
      if (els.about_python) els.about_python.value = "";
      els.about_curl.value = "";
      const msg = String(e && e.message ? e.message : e);
      toast("err", "Could not load info", msg);
    }
  }

  
  function openAdvanced() {
    _advReturnFocus = (document.activeElement instanceof HTMLElement) ? document.activeElement : null;
    els.adv_overlay.hidden = false;
    els.adv_overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.height = "100%";
    document.body.style.height = "100%";
    if (els.adv_close) els.adv_close.focus();
    else if (els.adv_modal) els.adv_modal.focus();

    if (els.auto) els.auto.checked = auto;
    if (els.pollms) els.pollms.value = String(pollMs);
    refreshPackageCache().catch((_err) => {});
    refreshPackageProfiles().catch((_err) => {});
  }

  function closeAdvanced() {
    els.adv_overlay.hidden = true;
    els.adv_overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    document.documentElement.style.height = "";
    document.body.style.height = "";
    if (_advReturnFocus && (document.contains(_advReturnFocus))) {
      try { _advReturnFocus.focus(); } catch (e) {}
    }
    _advReturnFocus = null;
  }

  function openSetup() {
    _setupReturnFocus = (document.activeElement instanceof HTMLElement) ? document.activeElement : null;
    els.setup_overlay.hidden = false;
    els.setup_overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.height = "100%";
    document.body.style.height = "100%";
    if (els.setup_close) els.setup_close.focus();
    else if (els.setup_modal) els.setup_modal.focus();
    refreshSetupStatus().catch((_err) => {});
  }

  function closeSetup() {
    if (!els.setup_overlay) return;
    els.setup_overlay.hidden = true;
    els.setup_overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    document.documentElement.style.height = "";
    document.body.style.height = "";
    if (_setupReturnFocus && (document.contains(_setupReturnFocus))) {
      try { _setupReturnFocus.focus(); } catch (e) {}
    }
    _setupReturnFocus = null;
  }

  function openSettings() {
    _settingsReturnFocus = (document.activeElement instanceof HTMLElement) ? document.activeElement : null;
    els.settings_overlay.hidden = false;
    els.settings_overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.height = "100%";
    document.body.style.height = "100%";
    if (els.settings_close) els.settings_close.focus();
    else if (els.settings_modal) els.settings_modal.focus();
    if (els.auto) els.auto.checked = auto;
    if (els.pollms) els.pollms.value = String(pollMs);
    if (els.settings_default_sort) els.settings_default_sort.value = sortMode;
    if (els.settings_keep_secondary) els.settings_keep_secondary.checked = keepSecondaryFilters;
    if (els.settings_density) els.settings_density.value = uiDensity;
    if (els.settings_direction) els.settings_direction.value = uiDirection;
  }

  function closeSettings() {
    els.settings_overlay.hidden = true;
    els.settings_overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    document.documentElement.style.height = "";
    document.body.style.height = "";
    if (_settingsReturnFocus && (document.contains(_settingsReturnFocus))) {
      try { _settingsReturnFocus.focus(); } catch (e) {}
    }
    _settingsReturnFocus = null;
  }

function closeAbout() {
    els.about_overlay.hidden = true;
    els.about_overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    document.documentElement.style.overflow = "";
    document.documentElement.style.height = "";
    document.body.style.height = "";
    if (_aboutReturnFocus && (document.contains(_aboutReturnFocus))) {
      try { _aboutReturnFocus.focus(); } catch (e) {}
    }
    _aboutReturnFocus = null;
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

    const before = buffers[which] || "";
    const combined = before + chunk;

    let dropped = 0;
    let final = combined;
    if (combined.length > LOG_MAX_CHARS) {
      dropped = combined.length - LOG_MAX_CHARS;
      final = combined.slice(-LOG_MAX_CHARS);
    }

    buffers[which] = final;

    // Track where new content starts in the current buffer so renderLog() can mark new lines.
    const from = Math.max(0, before.length - dropped);
    if (lastAppend && lastAppend[which]) {
      lastAppend[which].at = Date.now();
      lastAppend[which].from = from;
    }
  }

  function updateDetailActions(state) {
    const st = String(state || "");
    const canCancel = (st === "running" || st === "queued");
    const canDelete = (st === "done" || st === "error");

    if (els.btn_cancel) els.btn_cancel.style.display = canCancel ? "inline-flex" : "none";
    if (els.btn_delete) els.btn_delete.style.display = canDelete ? "inline-flex" : "none";
  }

  function _fmtWhen(value) {
    const ts = parseUtcSeconds(value);
    if (!ts) return "Not yet";
    try {
      return new Date(ts * 1000).toLocaleString();
    } catch (_e) {
      return String(value || "");
    }
  }

  function _setStateBanner(st) {
    if (!els.detail_state_banner) return;

    const state = String((st && st.state) || "queued");
    const phase = String((st && st.phase) || state);
    const titleMap = {
      queued: "Queued for execution",
      running: "Running",
      done: "Completed",
      error: "Failed",
    };

    els.detail_state_banner.hidden = false;
    els.detail_state_banner.classList.remove("queued", "running", "done", "error");
    els.detail_state_banner.classList.add(state);

    if (els.state_badge) {
      els.state_badge.className = `badge ${state}`;
      els.state_badge.textContent = state;
    }
    if (els.detail_inline_state) {
      els.detail_inline_state.hidden = false;
      els.detail_inline_state.className = `badge ${state} detail-inline-state`;
      els.detail_inline_state.textContent = state;
    }
    if (els.state_title) els.state_title.textContent = titleMap[state] || "Unknown state";

    let desc = `Phase: ${phase}`;
    if (state === "queued") {
      desc += ". Waiting for an execution slot.";
    } else if (state === "running") {
      desc += ". Logs update live below.";
    } else if (state === "done") {
      desc += ". Result archive should be available.";
    } else if (state === "error") {
      const err = st && st.error ? String(st.error) : "Unknown failure";
      desc += `. ${err}`;
    }

    if (els.state_description) els.state_description.textContent = desc;
  }



  function _renderDetailProgress(st) {
    if (!els.detail_progress_shell || !els.detail_progress || !els.detail_progress_bar) return;
    const state = String((st && st.state) || "queued");
    const show = ["running", "queued", "done", "error"].includes(state);
    els.detail_progress_shell.hidden = !show;
    if (!show) return;
    _applyProgressUi(els.detail_progress, els.detail_progress_bar, els.detail_progress_copy, state);
  }

  function _renderTimeline(st) {
    if (!els.detail_timeline) return;

    const timeline = [
      { key: "created", label: "Created", value: _fmtWhen(st && st.created_utc), done: !!(st && st.created_utc) },
      { key: "started", label: "Started", value: _fmtWhen(st && st.started_utc), done: !!(st && st.started_utc) },
      { key: "finished", label: "Finished", value: _fmtWhen(st && st.finished_utc), done: !!(st && st.finished_utc) },
      { key: "duration", label: "Duration", value: fmtDuration(st && st.duration_seconds) || "Not yet", done: !!(st && st.duration_seconds !== null && st.duration_seconds !== undefined) },
    ];

    els.detail_timeline.textContent = "";
    for (const step of timeline) {
      const li = document.createElement("li");
      li.className = step.done ? "done" : "pending";

      const title = document.createElement("span");
      title.className = "step-title";
      title.textContent = step.label;

      const value = document.createElement("span");
      value.className = "step-value";
      value.textContent = step.value;

      li.append(title, value);
      els.detail_timeline.appendChild(li);
    }
  }

  function _renderInsights(st) {
    if (!st) return;
    const limits = st.limits || {};
    const state = String(st.state || "queued");
    const cpu = (limits.cpu_percent === null || limits.cpu_percent === undefined) ? "?" : String(limits.cpu_percent);
    const mem = (limits.mem_mb === null || limits.mem_mb === undefined) ? "?" : String(limits.mem_mb);
    const threads = (limits.threads === null || limits.threads === undefined) ? "?" : String(limits.threads);
    const filename = st.result_filename ? String(st.result_filename) : "result archive";
    const exit = (st.exit_code === null || st.exit_code === undefined) ? "" : `Exit ${st.exit_code}`;
    const err = st.error ? String(st.error) : "Unknown error";

    if (els.detail_subtitle) {
      if (state === "running") els.detail_subtitle.textContent = "Follow progress, outputs, and the latest status in one place.";
      else if (state === "queued") els.detail_subtitle.textContent = "Queued work, expected limits, and the next useful checks.";
      else if (state === "done") els.detail_subtitle.textContent = "Result, completion details, and downloads in one place.";
      else if (state === "error") els.detail_subtitle.textContent = "Failure summary, next checks, and recovery actions in one place.";
      else els.detail_subtitle.textContent = "Lifecycle, outputs, and logs in one place.";
    }

    if (els.detail_limits_summary) {
      els.detail_limits_summary.textContent = `CPU ${cpu}% · Memory ${mem} MB · Threads ${threads}`;
    }

    if (els.detail_result_label) els.detail_result_label.textContent = (state === "queued") ? "Next step" : (state === "running" ? "Progress" : (state === "error" ? "Failure" : "Result"));
    if (els.detail_failure_label) els.detail_failure_label.textContent = (state === "queued") ? "What to expect" : (state === "running" ? "Watch for" : (state === "error" ? "Next step" : "Completion"));
    if (els.detail_limits_label) els.detail_limits_label.textContent = (state === "done" || state === "error") ? "Execution profile" : "Execution limits";

    if (els.detail_result_summary) {
      if (state === "queued") {
        els.detail_result_summary.textContent = "Waiting for a worker slot. Refresh or leave this open to see when execution begins.";
      } else if (state === "running") {
        els.detail_result_summary.textContent = "Execution is in progress. Open stdout for live output and check the state banner for changes.";
      } else if (state === "done") {
        els.detail_result_summary.textContent = `${filename} is ready or expected to be ready. Use Download zip to inspect outputs and status.json.`;
      } else if (state === "error") {
        els.detail_result_summary.textContent = `${err}. Open stderr and the request details to diagnose the failure.`;
      } else {
        els.detail_result_summary.textContent = `Current state: ${state}.`;
      }
    }

    if (els.detail_failure_summary) {
      if (state === "queued") {
        els.detail_failure_summary.textContent = "Logs, duration, and result details appear after the worker starts this job.";
      } else if (state === "running") {
        els.detail_failure_summary.textContent = "If execution stalls or fails, stderr and the state banner will show the clearest signal first.";
      } else if (state === "error") {
        els.detail_failure_summary.textContent = exit ? `${exit}. Check stderr first, then request and metadata for context.` : "Check stderr first, then request and metadata for context.";
      } else if (state === "done") {
        els.detail_failure_summary.textContent = exit ? `${exit}. Inspect stdout and stderr if you need extra confirmation.` : "No failure detected. Inspect stdout and stderr only if you need extra confirmation.";
      } else {
        els.detail_failure_summary.textContent = "Failure diagnosis becomes available when the job finishes.";
      }
    }

    const priorityState = state || "queued";
    [els.detail_result_summary, els.detail_failure_summary, els.detail_limits_summary].forEach((node) => {
      const shell = node && node.closest ? node.closest(".detail-priority-item") : null;
      if (shell) {
        shell.dataset.state = priorityState;
        shell.dataset.emphasis = (node === els.detail_result_summary || (state === "error" && node === els.detail_failure_summary)) ? "strong" : "normal";
      }
    });

    if (els.detail_timeline_title) {
      els.detail_timeline_title.textContent = (state === "queued") ? "Queue and timing" : (state === "running" ? "Live timing" : "Lifecycle");
    }
    if (els.detail_overview_title) {
      els.detail_overview_title.textContent = (state === "error") ? "Failure focus" : (state === "running" ? "Live summary" : "Quick facts");
    }
    if (els.overview_text) {
      if (state === "queued") {
        els.overview_text.textContent = "This job is waiting for a worker slot. The Summary tab shows the next useful state checks first.";
      } else if (state === "running") {
        els.overview_text.textContent = "This job is actively running. The most useful next steps are live stdout and the state banner above.";
      } else if (state === "error") {
        els.overview_text.textContent = `Failure details are prioritised above. ${exit ? `${exit}. ` : ""}Use stderr first, then request details if you need deeper context.`;
      } else if (state === "done") {
        els.overview_text.textContent = "This job finished. Download the result archive first, then inspect stdout or stderr only if you need more detail.";
      }
    }
  }

  function renderMeta(st) {
    const s = st || {};
    const lim = s.limits || {};
    const by = (s.submitted_by && (s.submitted_by.display_name || s.submitted_by.name)) || "";

    const pkg = s.package || {};
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
      ["Result file", s.result_filename || ""],
      ["Input SHA256", s.input_sha256 || ""],
      ["Package mode", pkg.mode || ""],
      ["Package status", pkg.status || ""],
      ["Package profile", pkg.profile_name || ""],
      ["Package profile display", pkg.profile_display_name || ""],
      ["Package profile status", pkg.profile_status || ""],
      ["Package profile attached", pkg.profile_attached ? "yes" : ""],
      ["Package profile requirements", pkg.profile_effective_requirements_path || pkg.profile_requirements_path || ""],
      ["Package profile bundle", pkg.profile_diagnostics_bundle_path || ""],
      ["Package cache", pkg.cache_enabled ? "enabled" : (pkg.enabled ? "disabled" : "")],
      ["Package cache hit", (pkg.cache_hit === true) ? "yes" : ((pkg.cache_hit === false && pkg.enabled) ? "no" : "")],
      ["Package wheelhouse hit", (pkg.wheelhouse_hit === true) ? "yes" : ((pkg.wheelhouse_hit === false && pkg.enabled) ? "no" : "")],
      ["Package install source", pkg.install_source || ""],
      ["Package local only", pkg.local_only_attempted ? (pkg.local_only_status || "attempted") : ""],
      ["Package find-links", (pkg.find_links_dirs && pkg.find_links_dirs.length) ? pkg.find_links_dirs.join("\n") : ""],
      ["Wheelhouse files", (pkg.wheelhouse_total_files === null || pkg.wheelhouse_total_files === undefined) ? "" : String(pkg.wheelhouse_total_files)],
      ["Wheelhouse imported", (pkg.wheelhouse_imported_files === null || pkg.wheelhouse_imported_files === undefined) ? "" : String(pkg.wheelhouse_imported_files)],
      ["Public wheels sync", pkg.public_wheel_sync_status || ""],
      ["Package install (s)", (pkg.install_duration_seconds === null || pkg.install_duration_seconds === undefined) ? "" : String(pkg.install_duration_seconds)],
      ["Package inspect (s)", (pkg.inspect_duration_seconds === null || pkg.inspect_duration_seconds === undefined) ? "" : String(pkg.inspect_duration_seconds)],
      ["Package inspect status", pkg.inspect_status || ""],
      ["Package env key", pkg.environment_key || ""],
      ["Reusable venv", pkg.venv_enabled ? ((pkg.venv_reused === true) ? "reused" : (pkg.venv_action || "enabled")) : ""],
      ["Reusable venv status", pkg.venv_status || ""],
      ["Reusable venv path", pkg.venv_path || ""],
      ["Reusable venv pruned", (pkg.venv_pruned_count === null || pkg.venv_pruned_count === undefined) ? "" : String(pkg.venv_pruned_count)],
      ["Wheelhouse download prep", pkg.prepare_download_status || ""],
      ["Wheelhouse wheel prep", pkg.prepare_wheel_status || ""],
      ["Package report dir", pkg.report_dir || ""],
      ["Package install report", pkg.install_report || ""],
      ["Package inspect report", pkg.inspect_report || ""],
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
      const row = document.createElement("div");
      row.className = "item-slab";
      const copy = document.createElement("div");
      copy.className = "item-copy";
      const title = document.createElement("div");
      title.className = "item-title";
      title.textContent = k;
      const desc = document.createElement("div");
      desc.className = "item-description";
      desc.textContent = "Job metadata";
      copy.append(title, desc);
      const meta = document.createElement("div");
      meta.className = "item-meta";
      meta.textContent = v;
      row.append(copy, meta);
      els.meta.append(row);
    }

    _setStateBanner(s);
    _renderDetailProgress(s);
    _renderTimeline(s);
    _renderInsights(s);
  }

  async function selectJob(jobId) {
    if (!jobId) return;
    currentJob = jobId;

    els.detail_empty.hidden = true;
    els.detail.hidden = false;
    els.jobid.textContent = jobId;
    if (els.detail_breadcrumb_current) els.detail_breadcrumb_current.textContent = jobId;
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
      els.overview_text.textContent = `overview error: ${String(e && e.message ? e.message : e)}`;
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
        dd.textContent = String(e && e.message ? e.message : e);
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
        offsets.stdout = data.offsets.stdout_next ?? offsets.stdout;
        offsets.stderr = data.offsets.stderr_next ?? offsets.stderr;
      }

      const tail = data.tail || {};
      appendBuffer("stdout", tail.stdout || "");
      appendBuffer("stderr", tail.stderr || "");

      initialTailForJob = currentJob;

      const hadNew = (currentTab === "stdout" && (tail.stdout || "")) || (currentTab === "stderr" && (tail.stderr || ""));

      if (currentTab !== "overview") {
        renderLog(currentTab);
        if (hadNew) {
          flashNewLines();
        }
        if (follow) {
          programmaticScrollAt = Date.now();
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
      dd.textContent = String(e && e.message ? e.message : e);
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

  function renderPackageCache(payload) {
    if (!els.package_cache_summary || !els.package_cache_list) return;

    const data = payload || {};
    const privateBytes = Number(data.private_bytes || 0);
    const maxBytes = Number(data.package_cache_max_bytes || 0);
    const overLimit = !!data.over_limit;
    const activeKeys = Array.isArray(data.active_environment_keys) ? data.active_environment_keys : [];
    let summary = `${fmtBytes(privateBytes)} used`;
    if (maxBytes > 0) summary += ` of ${fmtBytes(maxBytes)}`;
    if (overLimit) summary += `, over limit`;
    if (data.last_action_kind) summary += `, last ${data.last_action_kind} ${data.last_action_reason || ""}`.trimEnd();
    if (activeKeys.length) summary += `, ${activeKeys.length} active envs protected`;
    els.package_cache_summary.textContent = summary;

    els.package_cache_list.textContent = "";
    const entries = [];
    const breakdown = data.breakdown || {};
    entries.push(["pip cache", fmtBytes(Number(breakdown.cache_pip_bytes || 0))]);
    entries.push(["HTTP cache", fmtBytes(Number(breakdown.cache_http_bytes || 0))]);
    entries.push(["Wheelhouse downloaded", fmtBytes(Number(breakdown.wheelhouse_downloaded_bytes || 0))]);
    entries.push(["Wheelhouse built", fmtBytes(Number(breakdown.wheelhouse_built_bytes || 0))]);
    entries.push(["Wheelhouse imported", fmtBytes(Number(breakdown.wheelhouse_imported_bytes || 0))]);
    entries.push(["Reusable venvs", fmtBytes(Number(breakdown.venv_bytes || 0))]);
    entries.push(["Package reports", fmtBytes(Number(breakdown.jobs_package_reports_bytes || 0))]);
    entries.push(["Last prune", `${data.last_prune_status || ""}${data.last_prune_removed !== undefined && data.last_prune_removed !== null ? ` (${String(data.last_prune_removed)} removed)` : ""}`.trim()]);

    for (const [label, value] of entries) {
      const row = document.createElement("div");
      row.className = "item-row";
      const copy = document.createElement("div");
      copy.className = "item-copy";
      const title = document.createElement("div");
      title.className = "item-title";
      title.textContent = String(label || "");
      const desc = document.createElement("div");
      desc.className = "item-description";
      desc.textContent = String(value || "");
      copy.append(title, desc);
      row.append(copy);
      els.package_cache_list.appendChild(row);
    }
  }

  async function refreshPackageCache() {
    const payload = await api("packages/cache.json");
    renderPackageCache(payload || {});
  }

  async function prunePackageCache() {
    const payload = await api("packages/cache/prune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "manual" }),
    });
    toast("ok", "Package cache pruned", `${String(payload.removed || 0)} items removed`);
    await refreshPackageCache();
    await refreshAll({ silent: true });
  }

  async function purgePackageCache() {
    const payload = await api("packages/cache/purge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "manual", include_venvs: false, include_imported_wheels: false }),
    });
    toast("ok", "Package caches purged", `${String(payload.removed || 0)} items removed`);
    await refreshPackageCache();
    await refreshAll({ silent: true });
  }

  function renderPackageProfiles(payload) {
    if (!els.package_profiles_summary || !els.package_profiles_list) return;

    const data = payload || {};
    const profiles = Array.isArray(data.profiles) ? data.profiles : [];
    const defaultProfile = String(data.default_profile || "");
    const readyCount = Number(data.ready_count || 0);
    const enabled = !!data.enabled;

    let summary = `${profiles.length} profiles`;
    if (enabled) summary += `, ${readyCount} ready`;
    if (defaultProfile) summary += `, default ${defaultProfile}`;
    if (!enabled) summary += ", disabled in add-on config";
    els.package_profiles_summary.textContent = summary;

    els.package_profiles_list.textContent = "";
    if (!profiles.length) {
      const empty = document.createElement("div");
      empty.className = "field-hint";
      empty.textContent = "Create folders under /config/package_profiles with requirements.lock or requirements.txt to define reusable profiles.";
      els.package_profiles_list.appendChild(empty);
      return;
    }

    for (const profile of profiles) {
      const row = document.createElement("div");
      row.className = "item-row";

      const copy = document.createElement("div");
      copy.className = "item-copy";

      const title = document.createElement("div");
      title.className = "item-title";
      const name = String(profile.display_name || profile.name || "profile");
      const state = String(profile.status || (profile.ready ? "ready" : "not_built"));
      title.textContent = `${name} (${state})`;

      const desc = document.createElement("div");
      desc.className = "item-description";
      const parts = [];
      if (profile.name) parts.push(`Name: ${profile.name}`);
      if (profile.requirements_kind) parts.push(`Source: ${profile.requirements_kind}`);
      if (profile.environment_key) parts.push(`Env key: ${profile.environment_key}`);
      if (profile.last_build_utc) parts.push(`Last build: ${profile.last_build_utc}`);
      if (profile.last_error) parts.push(`Last error: ${profile.last_error}`);
      desc.textContent = parts.join(" • ");

      copy.append(title, desc);

      const actions = document.createElement("div");
      actions.className = "item-actions";

      const buildBtn = document.createElement("button");
      buildBtn.type = "button";
      buildBtn.className = "small tertiary";
      buildBtn.setAttribute("data-action", "build-package-profile");
      buildBtn.setAttribute("data-profile", String(profile.name || ""));
      buildBtn.textContent = profile.ready ? "Refresh build" : "Build";

      const rebuildBtn = document.createElement("button");
      rebuildBtn.type = "button";
      rebuildBtn.className = "small tertiary";
      rebuildBtn.setAttribute("data-action", "rebuild-package-profile");
      rebuildBtn.setAttribute("data-profile", String(profile.name || ""));
      rebuildBtn.textContent = "Rebuild";

      actions.append(buildBtn, rebuildBtn);
      row.append(copy, actions);
      els.package_profiles_list.appendChild(row);
    }
  }

  async function refreshPackageProfiles() {
    const payload = await api("package_profiles.json");
    renderPackageProfiles(payload || {});
  }

  async function buildPackageProfile(profileName, rebuild) {
    const name = String(profileName || "").trim();
    if (!name) {
      toast("err", "No profile selected", "Choose a package profile first.");
      return;
    }
    const payload = await api("package_profiles/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: name, rebuild: !!rebuild }),
    });
    const actionText = rebuild ? "Rebuilt" : "Built";
    const status = String((payload && payload.status) || "unknown");
    toast(status === "ready" ? "ok" : "err", actionText, `${name}: ${status}`);
    await refreshPackageProfiles();
    await refreshAll({ silent: true });
  }

  function setupBadgeText(enabled) {
    return enabled ? "Enabled" : "Disabled";
  }

  function createSetupRow(titleText, descriptionText, metaText) {
    const row = document.createElement("div");
    row.className = "item-row";
    const copy = document.createElement("div");
    copy.className = "item-copy";
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = titleText;
    const desc = document.createElement("div");
    desc.className = "item-description";
    desc.textContent = descriptionText;
    copy.append(title, desc);
    row.appendChild(copy);
    if (metaText) {
      const meta = document.createElement("div");
      meta.className = "item-meta";
      meta.textContent = metaText;
      row.appendChild(meta);
    }
    return row;
  }

  function createSetupActionButton(label, action, dataName, dataValue) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "small tertiary";
    btn.textContent = label;
    btn.setAttribute("data-action", action);
    if (dataName) btn.setAttribute(dataName, String(dataValue || ""));
    return btn;
  }

  function createSetupManagedRow(titleText, descriptionText, metaText, buttons) {
    const row = createSetupRow(titleText, descriptionText, metaText);
    if (Array.isArray(buttons) && buttons.length) {
      const actions = document.createElement("div");
      actions.className = "item-actions";
      for (const btn of buttons) {
        if (btn instanceof HTMLElement) actions.appendChild(btn);
      }
      if (actions.childElementCount) row.appendChild(actions);
    }
    return row;
  }

  function renderSetupSectionList(container, rows, emptyText) {
    if (!(container instanceof HTMLElement)) return;
    container.textContent = "";
    if (!Array.isArray(rows) || !rows.length) {
      const empty = document.createElement("div");
      empty.className = "field-hint";
      empty.textContent = emptyText;
      container.appendChild(empty);
      return;
    }
    for (const row of rows) {
      container.appendChild(row);
    }
  }

  function renderSetupTextList(container, heading, items, emptyText) {
    if (!(container instanceof HTMLElement)) return;
    container.textContent = "";
    const values = Array.isArray(items) ? items.filter((item) => String(item || "").trim()) : [];
    if (!values.length) {
      const empty = document.createElement("div");
      empty.className = "field-hint";
      empty.textContent = emptyText;
      container.appendChild(empty);
      return;
    }
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = heading;
    container.appendChild(title);
    for (const item of values) {
      const row = document.createElement("div");
      row.className = "item-row";
      const copy = document.createElement("div");
      copy.className = "item-copy";
      const desc = document.createElement("div");
      desc.className = "item-description";
      desc.textContent = String(item);
      copy.appendChild(desc);
      row.appendChild(copy);
      container.appendChild(row);
    }
  }

  function selectedSetupFile(kind) {
    const input = kind === "profile" ? els.setup_profile_zip_file : els.setup_wheel_file;
    if (!(input instanceof HTMLInputElement) || !input.files || !input.files.length) return null;
    return input.files[0] || null;
  }

  function updateSetupPickerSummary(kind) {
    const file = selectedSetupFile(kind);
    if (kind === "profile") {
      if (els.setup_profile_picker_summary) {
        els.setup_profile_picker_summary.textContent = file
          ? `Selected profile archive: ${file.name}`
          : "Choose one profile archive to upload into /config/package_profiles.";
      }
      if (els.setup_upload_profile_zip) els.setup_upload_profile_zip.disabled = !file;
      if (els.setup_clear_profile_zip_file) els.setup_clear_profile_zip_file.disabled = !file;
      return;
    }
    if (els.setup_wheel_picker_summary) {
      els.setup_wheel_picker_summary.textContent = file
        ? `Selected wheel file: ${file.name}`
        : "Choose one .whl file to upload into /config/wheel_uploads.";
    }
    if (els.setup_upload_wheel) els.setup_upload_wheel.disabled = !file;
    if (els.setup_clear_wheel_file) els.setup_clear_wheel_file.disabled = !file;
  }

  function clearSetupSelectedFile(kind) {
    const input = kind === "profile" ? els.setup_profile_zip_file : els.setup_wheel_file;
    if (input instanceof HTMLInputElement) input.value = "";
    updateSetupPickerSummary(kind);
  }

  async function setupRequest(path, opts) {
    const response = await fetch(apiUrl(path), Object.assign({ credentials: "same-origin" }, opts || {}));
    const ct = response.headers.get("content-type") || "";
    const payload = ct.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const message = (payload && typeof payload === "object" && payload.error)
        ? String(payload.error)
        : `${response.status}`;
      const err = new Error(message);
      err.status = response.status;
      err.payload = payload;
      throw err;
    }
    return payload;
  }

  function setSetupBusy(isBusy, bannerText) {
    const busy = !!isBusy;
    const cached = setupStatusCache && typeof setupStatusCache === "object" ? setupStatusCache : {};
    if (els.setup_refresh) els.setup_refresh.disabled = busy;
    if (els.setup_upload_wheel) els.setup_upload_wheel.disabled = busy || !selectedSetupFile("wheel");
    if (els.setup_clear_wheel_file) els.setup_clear_wheel_file.disabled = busy || !selectedSetupFile("wheel");
    if (els.setup_upload_profile_zip) els.setup_upload_profile_zip.disabled = busy || !selectedSetupFile("profile");
    if (els.setup_clear_profile_zip_file) els.setup_clear_profile_zip_file.disabled = busy || !selectedSetupFile("profile");
    if (els.setup_build_target_profile) els.setup_build_target_profile.disabled = busy || !cached.build_available;
    if (els.setup_rebuild_target_profile) els.setup_rebuild_target_profile.disabled = busy || !cached.rebuild_available;
    if (els.setup_apply_persistent_mode) els.setup_apply_persistent_mode.disabled = busy || !cached.persistent_packages_apply_available;
    if (els.setup_copy_config_snippet) els.setup_copy_config_snippet.disabled = busy || !String(cached.config_snippet || "").trim();
    if (busy && els.setup_status_banner && bannerText) {
      els.setup_status_banner.classList.remove("ok", "warn", "err");
      els.setup_status_banner.textContent = bannerText;
    }
  }

  function applySetupStatusPayload(payload) {
    const nextPayload = (payload && typeof payload === "object" && payload.setup_status && typeof payload.setup_status === "object")
      ? payload.setup_status
      : payload;
    if (nextPayload && typeof nextPayload === "object") {
      renderSetupStatus(nextPayload);
      return;
    }
    refreshSetupStatus().catch((_err) => {});
  }

  async function applySetupPersistentMode() {
    const target = String((setupStatusCache && setupStatusCache.target_profile) || "demo_formatsize_profile").trim() || "demo_formatsize_profile";
    setSetupBusy(true, "Saving the recommended persistent-package settings…");
    try {
      const payload = await setupRequest("setup/apply-persistent-mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_profile: target }),
      });
      applySetupStatusPayload(payload || {});
      const restartRequired = !!(payload && payload.setup_status && payload.setup_status.restart_required);
      toast("ok", "Persistent packages saved", restartRequired ? "Restart the add-on, then refresh Setup." : "Recommended package settings saved.");
    } catch (err) {
      const payload = err && err.payload && typeof err.payload === "object" ? err.payload : null;
      if (payload) applySetupStatusPayload(payload);
      const msg = payload && payload.error ? String(payload.error) : String(err && err.message ? err.message : err);
      toast("err", "Could not save persistent-package settings", msg);
    } finally {
      setSetupBusy(false);
    }
  }

  async function buildSetupTargetProfile(rebuild) {
    const target = String((setupStatusCache && setupStatusCache.target_profile) || "").trim();
    if (!target) {
      toast("err", "No target profile", "Refresh Setup and try again.");
      return;
    }
    const actionText = rebuild ? "Rebuilding" : "Building";
    setSetupBusy(true, `${actionText} ${target}…`);
    try {
      const payload = await setupRequest("package_profiles/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: target, rebuild: !!rebuild }),
      });
      applySetupStatusPayload(payload || {});
      await refreshPackageProfiles().catch((_err) => {});
      await refreshAll({ silent: true });
      const status = String((payload && payload.status) || "unknown");
      toast(status === "ready" ? "ok" : "err", rebuild ? "Profile rebuilt" : "Profile built", `${target}: ${status}`);
    } catch (err) {
      const payload = err && err.payload && typeof err.payload === "object" ? err.payload : null;
      if (payload) applySetupStatusPayload(payload);
      const msg = payload && payload.error ? String(payload.error) : String(err && err.message ? err.message : err);
      toast("err", rebuild ? "Rebuild failed" : "Build failed", `${target}: ${msg}`);
    } finally {
      setSetupBusy(false);
    }
  }

  async function copySetupConfigSnippet() {
    const snippet = String((setupStatusCache && setupStatusCache.config_snippet) || (els.setup_config_snippet && els.setup_config_snippet.value) || "").trim();
    if (!snippet) {
      toast("err", "No config snippet", "Refresh Setup and try again.");
      return;
    }
    await copyTextToClipboard(snippet);
    toast("ok", "Copied", "Suggested add-on config copied to clipboard");
  }

  async function uploadSetupBinary(kind, overwrite) {
    const file = selectedSetupFile(kind);
    if (!file) {
      toast("err", "No file selected", kind === "profile" ? "Choose a profile archive first." : "Choose a wheel file first.");
      return;
    }
    const path = kind === "profile" ? "setup/upload-profile-zip" : "setup/upload-wheel";
    const noun = kind === "profile" ? "profile archive" : "wheel";
    const query = `${path}?filename=${encodeURIComponent(file.name)}${overwrite ? "&overwrite=1" : ""}`;
    setSetupBusy(true, `Uploading ${file.name}…`);
    try {
      const payload = await setupRequest(query, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
      });
      clearSetupSelectedFile(kind);
      applySetupStatusPayload(payload || {});
      toast("ok", overwrite ? "Replaced" : "Uploaded", `${file.name} ${overwrite ? "replaced" : `${noun} uploaded`}.`);
    } catch (err) {
      const status = Number(err && err.status ? err.status : 0);
      const payload = err && err.payload && typeof err.payload === "object" ? err.payload : null;
      if (!overwrite && status === 409 && payload && String(payload.error || "") === "already_exists") {
        openConfirm({
          title: `Replace ${file.name}?`,
          body: `A file with that name already exists. Replace it with the selected ${noun}?`,
          confirmLabel: "Replace",
          onConfirm: async () => uploadSetupBinary(kind, true),
        });
      } else {
        const msg = payload && payload.error ? String(payload.error) : String(err && err.message ? err.message : err);
        toast("err", `Upload failed`, `${file.name}: ${msg}`);
      }
    } finally {
      setSetupBusy(false);
    }
  }

  async function performDeleteSetupWheel(filename) {
    const safeName = String(filename || "").trim();
    if (!safeName) return;
    setSetupBusy(true, `Deleting ${safeName}…`);
    try {
      const payload = await setupRequest("setup/delete-wheel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: safeName }),
      });
      applySetupStatusPayload(payload || {});
      toast("ok", "Wheel deleted", safeName);
    } catch (err) {
      const payload = err && err.payload && typeof err.payload === "object" ? err.payload : null;
      const msg = payload && payload.error ? String(payload.error) : String(err && err.message ? err.message : err);
      toast("err", "Delete failed", `${safeName}: ${msg}`);
    } finally {
      setSetupBusy(false);
    }
  }

  function deleteSetupWheel(filename) {
    const safeName = String(filename || "").trim();
    if (!safeName) return;
    openConfirm({
      title: `Delete wheel ${safeName}?`,
      body: "This removes the uploaded wheel and its imported copy from the internal wheelhouse.",
      confirmLabel: "Delete wheel",
      onConfirm: async () => performDeleteSetupWheel(safeName),
    });
  }

  async function performDeleteSetupProfile(profileName) {
    const safeName = String(profileName || "").trim();
    if (!safeName) return;
    setSetupBusy(true, `Deleting ${safeName}…`);
    try {
      const payload = await setupRequest("setup/delete-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: safeName }),
      });
      applySetupStatusPayload(payload || {});
      toast("ok", "Profile deleted", safeName);
    } catch (err) {
      const payload = err && err.payload && typeof err.payload === "object" ? err.payload : null;
      const msg = payload && payload.error ? String(payload.error) : String(err && err.message ? err.message : err);
      toast("err", "Delete failed", `${safeName}: ${msg}`);
    } finally {
      setSetupBusy(false);
    }
  }

  function deleteSetupProfile(profileName) {
    const safeName = String(profileName || "").trim();
    if (!safeName) return;
    openConfirm({
      title: `Delete profile ${safeName}?`,
      body: "This removes the uploaded package profile and any cached build artefacts linked to it.",
      confirmLabel: "Delete profile",
      onConfirm: async () => performDeleteSetupProfile(safeName),
    });
  }

  function renderSetupStatus(payload) {
    const data = payload || {};
    setupStatusCache = data;
    const blockers = Array.isArray(data.blockers) ? data.blockers : [];
    const warnings = Array.isArray(data.warnings) ? data.warnings : [];
    const nextSteps = Array.isArray(data.next_steps) ? data.next_steps : [];
    const wheelFiles = Array.isArray(data.wheel_files) ? data.wheel_files : [];
    const profileNames = Array.isArray(data.profile_names) ? data.profile_names : [];
    const ready = !!data.ready_for_example_5;
    const targetProfile = String(data.target_profile || "demo_formatsize_profile");
    const targetWheel = String(data.target_wheel || "pjr_demo_formatsize-0.1.0-py3-none-any.whl");
    const targetSummary = data.target_profile_summary || {};
    const readyState = String(data.ready_state || "not_ready");
    const buildAvailable = !!data.build_available;
    const rebuildAvailable = !!data.rebuild_available;
    const buildRecommended = !!data.build_recommended;
    const targetProfileStatus = String(data.target_profile_status || (data.profile_present ? (data.profile_built ? "ready" : "not_built") : "missing"));
    const targetProfileLastError = String(data.target_profile_last_error || "");
    const restartRequired = !!data.restart_required;
    const restartGuidance = String(data.restart_guidance || "");
    const configSnippet = String(data.config_snippet || "");
    const persistentRunning = !!data.persistent_packages_running;
    const persistentSaved = !!data.persistent_packages_saved;
    const persistentApplyAvailable = !!data.persistent_packages_apply_available;
    const persistentModeSummary = String(data.persistent_mode_summary || "");
    const settingsSummary = [
      `Mode: ${String(data.dependency_mode || "per_job")}`,
      `Requirements: ${setupBadgeText(!!data.install_requirements_enabled)}`,
      `Profiles: ${setupBadgeText(!!data.package_profiles_enabled)}`,
    ].join(" • ");
    const wheelsDir = String(((data.paths || {}).wheel_uploads_dir) || "/config/wheel_uploads");
    const profilesDir = String(((data.paths || {}).profiles_dir) || "/config/package_profiles");

    if (els.setup_status_banner) {
      els.setup_status_banner.classList.remove("ok", "warn", "err");
      if (readyState === "ready") {
        els.setup_status_banner.classList.add("ok");
        els.setup_status_banner.textContent = "Persistent packages are ready. The target wheel, profile, and running add-on settings are aligned.";
      } else if (readyState === "build_recommended") {
        els.setup_status_banner.classList.add("warn");
        els.setup_status_banner.textContent = `The persistent-package settings are in place. Build ${targetProfile} now for a cleaner first run, or let the first run build it on demand.`;
      } else if (readyState === "build_failed") {
        els.setup_status_banner.classList.add("err");
        els.setup_status_banner.textContent = targetProfileLastError
          ? `The last ${targetProfile} build failed: ${targetProfileLastError}`
          : `The last ${targetProfile} build failed. Rebuild it and inspect the diagnostics bundle if needed.`;
      } else if (readyState === "restart_required") {
        els.setup_status_banner.classList.add("warn");
        els.setup_status_banner.textContent = restartGuidance || "Persistent package defaults are saved. Restart the add-on, then refresh Setup.";
      } else if (blockers.length) {
        els.setup_status_banner.classList.add("warn");
        els.setup_status_banner.textContent = blockers[0];
      } else {
        els.setup_status_banner.textContent = "Setup information loaded.";
      }
    }
    if (els.setup_target_summary) {
      els.setup_target_summary.textContent = `Target profile: ${targetProfile} • Target wheel: ${targetWheel}`;
    }
    if (els.setup_persistent_mode_summary) {
      els.setup_persistent_mode_summary.textContent = persistentModeSummary || "Refresh Setup to check the persistent-package toggle state.";
    }
    if (els.setup_settings_summary) {
      els.setup_settings_summary.textContent = settingsSummary;
    }
    if (els.setup_wheels_summary) {
      const wheelStatus = wheelFiles.length ? `${wheelFiles.length} wheel uploads found` : "No wheel uploads found yet";
      els.setup_wheels_summary.textContent = `${wheelStatus} • Upload location: ${wheelsDir}`;
    }
    if (els.setup_profiles_summary) {
      const readyCount = Number(((data.inventory || {}).ready_count) || 0);
      const profileStatus = profileNames.length ? `${profileNames.length} profiles found, ${readyCount} ready` : "No package profiles found yet";
      els.setup_profiles_summary.textContent = `${profileStatus} • Profile location: ${profilesDir}`;
    }
    if (els.setup_readiness_summary) {
      if (readyState === "ready") {
        els.setup_readiness_summary.textContent = "Ready to run with persistent packages.";
      } else if (readyState === "build_recommended") {
        els.setup_readiness_summary.textContent = `Build ${targetProfile} now for a cleaner first run.`;
      } else if (readyState === "build_failed") {
        els.setup_readiness_summary.textContent = `${targetProfile} needs a rebuild before you rely on it.`;
      } else if (readyState === "restart_required") {
        els.setup_readiness_summary.textContent = "Restart required before the running add-on can use the saved persistent-package settings.";
      } else if (blockers.length) {
        els.setup_readiness_summary.textContent = `${blockers.length} blocker${blockers.length === 1 ? "" : "s"} found.`;
      } else if (warnings.length) {
        els.setup_readiness_summary.textContent = `${warnings.length} warning${warnings.length === 1 ? "" : "s"} found.`;
      } else {
        els.setup_readiness_summary.textContent = "No blockers found.";
      }
    }
    if (els.setup_build_summary) {
      if (!data.profile_present) {
        els.setup_build_summary.textContent = `Upload ${targetProfile} before trying to build it.`;
      } else if (readyState === "build_failed") {
        els.setup_build_summary.textContent = targetProfileLastError
          ? `Last build failed: ${targetProfileLastError}`
          : `Last build failed. Try Rebuild for ${targetProfile}.`;
      } else if (data.profile_built) {
        els.setup_build_summary.textContent = `${targetProfile} is already built and ready to attach.`;
      } else if (buildRecommended) {
        els.setup_build_summary.textContent = `${targetProfile} exists but has not been built yet.`;
      } else {
        els.setup_build_summary.textContent = `${targetProfile} status: ${targetProfileStatus}.`;
      }
    }
    if (els.setup_config_snippet) {
      els.setup_config_snippet.value = configSnippet;
    }
    if (els.setup_restart_guidance) {
      els.setup_restart_guidance.textContent = restartGuidance || "Refresh Setup after the next change to confirm the current state.";
    }
    if (els.setup_build_target_profile) {
      els.setup_build_target_profile.disabled = !buildAvailable;
      els.setup_build_target_profile.textContent = data.profile_built ? "Refresh build" : "Build target profile";
    }
    if (els.setup_rebuild_target_profile) {
      els.setup_rebuild_target_profile.disabled = !rebuildAvailable;
    }
    if (els.setup_apply_persistent_mode) {
      els.setup_apply_persistent_mode.disabled = !persistentApplyAvailable;
      els.setup_apply_persistent_mode.textContent = persistentRunning
        ? "Persistent packages enabled"
        : (persistentSaved ? "Defaults saved" : "Enable persistent packages");
    }
    if (els.setup_copy_config_snippet) {
      els.setup_copy_config_snippet.disabled = !configSnippet;
    }

    renderSetupSectionList(els.setup_settings_list, [
      createSetupRow("Install requirements.txt automatically", setupBadgeText(!!data.install_requirements_enabled), null),
      createSetupRow("Dependency handling mode", String(data.dependency_mode || "per_job"), null),
      createSetupRow("Package profiles", setupBadgeText(!!data.package_profiles_enabled), null),
      createSetupRow("Default package profile", String(data.default_profile || "Not set"), !!data.default_profile_exists ? "Found" : "Missing"),
      createSetupRow("Persistent packages preset", persistentRunning ? "Running" : (persistentSaved ? "Saved, restart required" : "Not saved"), null),
      createSetupRow("Public wheelhouse", setupBadgeText(!!data.package_allow_public_wheelhouse), null),
      createSetupRow("Offline prefer local", setupBadgeText(!!data.package_offline_prefer_local), null),
      createSetupRow("Reusable virtual environments", setupBadgeText(!!data.venv_reuse_enabled), null),
    ], "No setup settings available.");

    const wheelRows = [
      createSetupRow(
        "Target wheel",
        targetWheel,
        !!data.wheel_present ? "Present" : "Missing"
      ),
      ...wheelFiles.map((name) => createSetupManagedRow(
        "Uploaded wheel",
        String(name),
        name === targetWheel ? "Target match" : null,
        [createSetupActionButton("Delete", "setup-delete-wheel", "data-filename", name)]
      )),
    ];
    renderSetupSectionList(els.setup_wheels_list, wheelRows, "No uploaded wheel files were found.");

    const targetProfileButtons = [];
    if (buildAvailable) targetProfileButtons.push(createSetupActionButton(data.profile_built ? "Refresh build" : "Build", "setup-build-target-profile"));
    if (rebuildAvailable) targetProfileButtons.push(createSetupActionButton("Rebuild", "setup-rebuild-target-profile"));
    const profileRows = [
      createSetupManagedRow(
        "Target profile",
        targetProfile,
        !!data.profile_present ? (data.profile_built ? "Ready" : "Needs build") : "Missing",
        targetProfileButtons
      ),
      ...profileNames.map((name) => {
        let meta = null;
        if (name === targetProfile) meta = !!data.profile_built ? "Target ready" : `Target (${targetProfileStatus})`;
        return createSetupManagedRow(
          "Discovered profile",
          String(name),
          meta,
          [createSetupActionButton("Delete", "setup-delete-profile", "data-profile", name)]
        );
      }),
    ];
    if (targetSummary && typeof targetSummary === "object" && Object.keys(targetSummary).length) {
      profileRows.splice(1, 0, createSetupRow(
        "Target profile source",
        String(targetSummary.requirements_kind || targetSummary.requirements_path || "requirements.txt"),
        String(targetSummary.status || "unknown")
      ));
    }
    renderSetupSectionList(els.setup_profiles_list, profileRows, "No package profiles were found.");

    renderSetupTextList(els.setup_blockers_list, "Blockers", blockers, "No blockers found.");
    renderSetupTextList(els.setup_warnings_list, "Warnings", warnings, "No warnings.");
    renderSetupTextList(els.setup_next_steps_list, "Next steps", nextSteps, "No next steps available.");
    updateSetupPickerSummary("wheel");
    updateSetupPickerSummary("profile");
  }

  async function refreshSetupStatus() {
    const payload = await api("setup/status.json");
    renderSetupStatus(payload || {});
  }

  async function copyEndpoint(btn) {
    const val = btn.getAttribute("data-copy") || "";
    if (!val) return;
    await copyTextToClipboard(val);
    toast("ok", "Copied", val);
  }

  async function performCancelJob() {
    if (!currentJob) return;
    await api(`cancel/${encodeURIComponent(currentJob)}`, { method: "POST" });
    toast("ok", "Cancelled", `Job ${currentJob} cancelled`);
    await refreshAll();
  }

  async function cancelJob() {
    if (!currentJob) return;
    openConfirm({
      title: `Cancel job ${currentJob}?`,
      body: "The current run will stop and can still be inspected afterward.",
      confirmLabel: "Cancel job",
      onConfirm: async () => performCancelJob(),
    });
  }

  async function performDeleteJob() {
    if (!currentJob) return;
    await api(`job/${encodeURIComponent(currentJob)}`, { method: "DELETE" });
    toast("ok", "Deleted", `Job ${currentJob} deleted`);
    currentJob = null;
    els.detail.hidden = true;
    els.detail_empty.hidden = false;
    applyFilters();
    await refreshAll();
  }

  async function deleteJob() {
    if (!currentJob) return;
    openConfirm({
      title: `Delete job ${currentJob}?`,
      body: "This removes the job record and any downloaded outputs linked to it.",
      confirmLabel: "Delete job",
      onConfirm: async () => performDeleteJob(),
    });
  }

  async function _downloadViaFetch(path, filename) {
    const response = await fetch(apiUrl(path), { credentials: "same-origin" });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`${response.status} ${body}`);
    }

    const blob = await response.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => window.URL.revokeObjectURL(objectUrl), 1000);
  }

  async function downloadZip() {
    if (!currentJob) return;
    const filename = safeDownloadName(`pythonista_job_runner_${currentJob}.zip`, "result.zip");
    await _downloadViaFetch(`result/${encodeURIComponent(currentJob)}.zip`, filename);
  }

  async function downloadText(which) {
    if (!currentJob) return;
    const w = which || "stdout";
    const filename = safeDownloadName(`${currentJob}_${w}.txt`, `${w}.txt`);
    await _downloadViaFetch(`${w}/${encodeURIComponent(currentJob)}.txt`, filename);
  }

  /**
   * Refreshes application state: stats, job list and, if a job is selected, its meta/tail and overview.
   *
   * Runs concurrently where possible, prevents concurrent refreshes, and updates UI state on success or error.
   * The function sets an internal `refreshing` flag while the operation runs and clears it on completion.
   *
   * @param {{silent?: boolean}=} opts - Optional settings. If `silent` is true, suppresses the error toast on failure.
   */
  async function refreshAll(opts) {
    if (refreshing) return;
    refreshing = true;
    const silent = !!(opts && opts.silent);
    try {
      await Promise.all([refreshStats(), refreshJobs({ silent })]);
      if (currentJob) {
        await Promise.all([refreshMetaAndTail(), refreshOverview()]);
      }
      setStatus("ok", "Connected");
      jobsViewState = "connected";
      setLastUpdated(new Date().toLocaleTimeString());
      if (els.jobs_banner) els.jobs_banner.hidden = true;
    } catch (e) {
      const msg = String(e && e.message ? e.message : e);
      setStatus("err", "Disconnected");
      jobsViewState = "disconnected";
      if (els.jobs_banner) {
        els.jobs_banner.hidden = false;
        els.jobs_banner.textContent = `Connection problem: ${msg}`;
      }
      if (!silent) toast("err", "Request failed", msg);
    }
    finally {
      refreshing = false;
    }
  }

  async function tick() {
    if (auto) {
      await refreshAll({ silent: true });
    }
    tickTimer = window.setTimeout(tick, pollMs);
  }
function toggleAuto() {
    auto = !auto;
    if (els.auto) els.auto.checked = auto;
    toast(null, "Auto refresh", auto ? "Enabled" : "Disabled");
  }

  function setSort(next, sourceBtn) {
    sortMode = next || "newest";
    storageSet("pjr_sort", sortMode);
    const menu = document.getElementById("sort_menu");
    if (menu) menu.open = false;
    applyFilters();
    updateClearButtonVisibility();
    if (sourceBtn && typeof sourceBtn.focus === "function") sourceBtn.focus();
  }



  function updateFiltersSummaryUi() {
    const summary = document.getElementById("filters_summary");
    if (!summary) return;
    const parts = [];
    if (String(filterUser || "").trim()) parts.push(`User: ${String(filterUser).trim()}`);
    if (String(filterSince || "").trim()) parts.push(`From: ${filterSince}`);
    if (filterHasResult) parts.push("Has result zip");
    summary.textContent = parts.length ? parts.join(" · ") : "User, date, and artifacts";
  }

  function closeJobsFiltersPanel(options) {
    const returnFocus = !!(options && options.returnFocus);
    const panel = document.getElementById("filters_menu");
    if (!panel) return;
    panel.open = false;
    if (!returnFocus) return;
    const summary = panel.querySelector("summary");
    if (summary && typeof summary.focus === "function") summary.focus();
  }

  function isHeaderMoreElement(el) {
    return !!(el && el.closest && el.closest("#header_more_toggle, #header_more_panel button[data-action], #header_more_panel"));
  }

  function closeHeaderMoreMenu(options) {
    const returnFocus = !!(options && options.returnFocus);
    if (!els.header_more_panel || !els.header_more_toggle) return;
    els.header_more_panel.hidden = true;
    els.header_more_toggle.setAttribute("aria-expanded", "false");
    if (returnFocus && typeof els.header_more_toggle.focus === "function") {
      els.header_more_toggle.focus();
    }
  }

  function openHeaderMoreMenu() {
    if (!els.header_more_panel || !els.header_more_toggle) return;
    els.header_more_panel.hidden = false;
    els.header_more_toggle.setAttribute("aria-expanded", "true");
  }

  function toggleHeaderMoreMenu() {
    if (!els.header_more_panel || !els.header_more_toggle) return;
    if (els.header_more_panel.hidden) {
      openHeaderMoreMenu();
    } else {
      closeHeaderMoreMenu({ returnFocus: true });
    }
  }

  function bindEvents() {
    document.addEventListener("click", async (ev) => {
      const t = ev.target;
      const el = (t instanceof Element) ? t : (t && t.parentElement);
      if (!el) return;
      const btn = el.closest("button[data-action]");
      if (!btn) return;

      const action = btn.getAttribute("data-action");
      try {
        if (action === "toggle-header-more") {
          toggleHeaderMoreMenu();
          return;
        }
        if (action === "refresh") await refreshAll();
        if (action === "open-command") {
          closeHeaderMoreMenu();
          openCommand();
        }
        if (action === "close-command") closeCommand();
        if (action === "command-run") await runCommand(btn.getAttribute("data-command") || "");
        if (action === "open-settings") {
          closeHeaderMoreMenu();
          openSettings();
        }
        if (action === "close-settings") closeSettings();
        if (action === "open-setup") {
          closeHeaderMoreMenu();
          openSetup();
        }
        if (action === "open-advanced") {
          closeHeaderMoreMenu();
          openAdvanced();
        }
        if (action === "refresh-setup-status") await refreshSetupStatus();
        if (action === "setup-apply-persistent-mode") await applySetupPersistentMode();
        if (action === "setup-upload-wheel") await uploadSetupBinary("wheel", false);
        if (action === "setup-clear-wheel-file") clearSetupSelectedFile("wheel");
        if (action === "setup-upload-profile-zip") await uploadSetupBinary("profile", false);
        if (action === "setup-clear-profile-file") clearSetupSelectedFile("profile");
        if (action === "setup-build-target-profile") await buildSetupTargetProfile(false);
        if (action === "setup-rebuild-target-profile") await buildSetupTargetProfile(true);
        if (action === "setup-copy-config-snippet") await copySetupConfigSnippet();
        if (action === "setup-delete-wheel") deleteSetupWheel(btn.getAttribute("data-filename") || "");
        if (action === "setup-delete-profile") deleteSetupProfile(btn.getAttribute("data-profile") || "");
        if (action === "refresh-package-cache") await refreshPackageCache();
        if (action === "prune-package-cache") await prunePackageCache();
        if (action === "purge-package-cache") await purgePackageCache();
        if (action === "refresh-package-profiles") await refreshPackageProfiles();
        if (action === "build-package-profile") await buildPackageProfile(btn.getAttribute("data-profile") || "", false);
        if (action === "rebuild-package-profile") await buildPackageProfile(btn.getAttribute("data-profile") || "", true);
        if (action === "close-setup") closeSetup();
        if (action === "close-advanced") closeAdvanced();
        if (action === "back-to-jobs") setPane("jobs");
        if (action === "clear-filters") clearFilters();
        if (action === "clear-user-filter") {
          filterUser = "";
          currentPage = 1;
          if (els.filter_user) els.filter_user.value = "";
          storageSet("pjr_filter_user", "");
          applyFilters();
          updateClearButtonVisibility();
          updateFiltersSummaryUi();
        }
        if (action === "focus-search" && els.search) els.search.focus();
        if (action === "reset-ui") openConfirm({ title: "Reset UI settings?", body: "Saved UI preferences such as density, sorting, and filters will be cleared.", confirmLabel: "Reset UI", onConfirm: async () => resetUi() });
        if (action === "jump-error") jumpToNextError();
        if (action === "set-view") setView(btn.getAttribute("data-view") || "all");
        if (action === "set-sort") setSort(btn.getAttribute("data-sort") || "newest", btn);
        if (action === "set-date-preset") setDatePreset(btn.getAttribute("data-preset") || "clear");
        if (action === "close-filters-panel") closeJobsFiltersPanel({ returnFocus: true });
        if (action === "page-prev") goToNextPage(-1);
        if (action === "page-next") goToNextPage(1);
        if (action === "purge") await purgeState(btn.getAttribute("data-state") || "");
        if (action === "set-tab") setTab(btn.getAttribute("data-tab") || "stdout");
        if (action === "find-next") findNext();
        if (action === "find-prev") findPrev();
        if (action === "clear-search") clearSearch();
        if (action === "copy-curl") await copyCurl();
        if (action === "copy-sample-task") await copySampleTask();
        if (action === "copy-about-curl") await copyAboutCurl();
        if (action === "open-about") {
          closeHeaderMoreMenu();
          await openAbout();
        }
        if (action === "close-about") closeAbout();
        if (action === "close-confirm") closeConfirm();
        if (action === "confirm-accept") await acceptConfirm();
        if (action === "row-popover-view") await runRowPopoverAction("view");
        if (action === "row-menu-view") await runRowMenuAction("view");
        if (action === "row-menu-copy-id") await runRowMenuAction("copy-id");
        if (action === "row-menu-stdout") await runRowMenuAction("stdout");
        if (action === "row-menu-stderr") await runRowMenuAction("stderr");
        if (action === "row-menu-curl") await runRowMenuAction("curl");
        if (action === "copy-base") await copyBase();
        if (action === "open-info") window.open(apiUrl("info.json"), "_blank", "noopener,noreferrer");
        if (action === "copy-endpoint") await copyEndpoint(btn);
        if (action === "download-zip") await downloadZip();
        if (action === "download-text") await downloadText(btn.getAttribute("data-which") || "stdout");
        if (action === "cancel") await cancelJob();
        if (action === "delete") await deleteJob();
        if (action === "go-live") await goLive();
        if (action === "toggle-pause") await togglePauseResume();
        if (action === "jump-latest") await jumpLatest();
        if (action === "clear-log") clearCurrentLog();
        if (action === "toggle-hterm") toggleHighlightTerm(btn.getAttribute("data-term") || "");
        if (action === "add-hterm") addHighlightTermFromInput();
        if (action === "clear-hterms") clearHighlightTerms();
      } catch (e) {
        toast("err", "Action failed", e && e.message ? e.message : String(e));
      }
    });

    if (els.about_overlay) {
      els.about_overlay.addEventListener("click", (ev) => {
        if (ev.target === els.about_overlay) closeAbout();
      });
    }

    if (els.setup_overlay) {
      els.setup_overlay.addEventListener("click", (ev) => {
        if (ev.target === els.setup_overlay) closeSetup();
      });
    }

    if (els.adv_overlay) {
      els.adv_overlay.addEventListener("click", (ev) => {
        if (ev.target === els.adv_overlay) closeAdvanced();
      });
    }

    if (els.settings_overlay) {
      els.settings_overlay.addEventListener("click", (ev) => {
        if (ev.target === els.settings_overlay) closeSettings();
      });
    }

    if (els.command_overlay) {
      els.command_overlay.addEventListener("click", (ev) => {
        if (ev.target === els.command_overlay) closeCommand();
      });
    }

    if (els.confirm_overlay) {
      els.confirm_overlay.addEventListener("click", (ev) => {
        if (ev.target === els.confirm_overlay) closeConfirm();
      });
    }

    document.addEventListener("click", (ev) => {
      if (!els.header_more_panel || !els.header_more_toggle || els.header_more_panel.hidden) return;
      const target = ev.target;
      if (!(target instanceof Element)) return;
      if (isHeaderMoreElement(target)) return;
      closeHeaderMoreMenu();
    });

    document.addEventListener("click", (ev) => {
      if (!els.row_menu || els.row_menu.hidden) return;
      const target = ev.target;
      if (!(target instanceof Element)) return;
      if (target.closest("#row_menu") || target.closest(".row-overflow")) return;
      closeRowMenu();
    });

    document.addEventListener("click", (ev) => {
      if (!els.row_popover || els.row_popover.hidden) return;
      const target = ev.target;
      if (!(target instanceof Element)) return;
      if (target.closest("#row_popover") || target.closest(".state-badge-trigger") || target.closest(".hover-preview-trigger") || target.closest(".jobbtn")) return;
      closeRowPopover();
    });

    if (els.row_popover) {
      els.row_popover.addEventListener("mouseenter", () => {
        window.clearTimeout(hoverPopoverCloseTimer);
      });
      els.row_popover.addEventListener("mouseleave", () => {
        if (rowPopoverMode === "hover") closeRowPopover(true);
      });
    }


    if (els.about_close) {
      const close = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        closeAbout();
      };
      els.about_close.addEventListener("click", close);
      els.about_close.addEventListener("touchend", close, { passive: false });
    }


    if (els.setup_close) {
      const close = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        closeSetup();
      };
      els.setup_close.addEventListener("click", close);
      els.setup_close.addEventListener("touchend", close, { passive: false });
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

    if (els.settings_close) {
      const close = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        closeSettings();
      };
      els.settings_close.addEventListener("click", close);
      els.settings_close.addEventListener("touchend", close, { passive: false });
    }

    if (els.command_close) {
      const close = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        closeCommand();
      };
      els.command_close.addEventListener("click", close);
      els.command_close.addEventListener("touchend", close, { passive: false });
    }

    if (els.confirm_close) {
      const close = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        closeConfirm();
      };
      els.confirm_close.addEventListener("click", close);
      els.confirm_close.addEventListener("touchend", close, { passive: false });
    }

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") {
        const filtersPanel = document.getElementById("filters_menu");
        if (filtersPanel && filtersPanel.open) {
          closeJobsFiltersPanel({ returnFocus: true });
          return;
        }
        if (els.header_more_panel && !els.header_more_panel.hidden) closeHeaderMoreMenu({ returnFocus: true });
        if (els.command_overlay && !els.command_overlay.hidden) closeCommand();
        if (els.confirm_overlay && !els.confirm_overlay.hidden) closeConfirm();
        if (els.row_menu && !els.row_menu.hidden) closeRowMenu();
        if (els.row_popover && !els.row_popover.hidden) closeRowPopover();
        if (!els.about_overlay.hidden) closeAbout();
        if (!els.setup_overlay.hidden) closeSetup();
        if (!els.adv_overlay.hidden) closeAdvanced();
        if (!els.settings_overlay.hidden) closeSettings();
        return;
      }
      if (ev.key === "Tab") {
        if (els.command_overlay && !els.command_overlay.hidden) trapTabKey(ev, els.command_modal || els.command_overlay);
        if (els.confirm_overlay && !els.confirm_overlay.hidden) trapTabKey(ev, els.confirm_modal || els.confirm_overlay);
        if (!els.about_overlay.hidden) trapTabKey(ev, els.about_modal || els.about_overlay);
        if (!els.setup_overlay.hidden) trapTabKey(ev, els.setup_modal || els.setup_overlay);
        if (!els.adv_overlay.hidden) trapTabKey(ev, els.adv_modal || els.adv_overlay);
        if (!els.settings_overlay.hidden) trapTabKey(ev, els.settings_modal || els.settings_overlay);
      }
    });

    if (els.setup_wheel_file) {
      els.setup_wheel_file.addEventListener("change", () => updateSetupPickerSummary("wheel"));
    }
    if (els.setup_profile_zip_file) {
      els.setup_profile_zip_file.addEventListener("change", () => updateSetupPickerSummary("profile"));
    }

    els.pollms.addEventListener("change", () => {
      setPollMsFromInput();
      storageSet("pjr_pollms", String(pollMs));
    });
    els.search.addEventListener("input", () => {
      currentPage = 1;
      storageSet("pjr_search", String(els.search.value || ""));
      applyFilters();
      updateClearButtonVisibility();
    });
    if (els.filter_has_result) {
      els.filter_has_result.addEventListener("change", () => {
        filterHasResult = !!els.filter_has_result.checked;
        currentPage = 1;
        storageSet("pjr_has_result", filterHasResult ? "1" : "0");
        applyFilters();
        updateClearButtonVisibility();
        updateFiltersSummaryUi();
      });
    }

    if (els.filter_user) {
      els.filter_user.addEventListener("input", () => {
        filterUser = String(els.filter_user.value || "").trim();
        currentPage = 1;
        storageSet("pjr_filter_user", filterUser);
        applyFilters();
        updateClearButtonVisibility();
        updateFiltersSummaryUi();
      });
    }

    if (els.filter_since) {
      els.filter_since.addEventListener("change", () => {
        filterSince = String(els.filter_since.value || "").trim();
        currentPage = 1;
        storageSet("pjr_filter_since", filterSince);
        applyFilters();
        updateClearButtonVisibility();
        updateFiltersSummaryUi();
      });
    }
    if (els.auto) {
      els.auto.addEventListener("change", () => {
        auto = !!els.auto.checked;
        storageSet("pjr_auto", auto ? "1" : "0");
      });
    }

    if (els.settings_default_sort) {
      els.settings_default_sort.addEventListener("change", () => {
        sortMode = els.settings_default_sort.value || "newest";
        currentPage = 1;
        storageSet("pjr_sort", sortMode);
        applyFilters();
        updateClearButtonVisibility();
      });
    }

    if (els.settings_keep_secondary) {
      els.settings_keep_secondary.addEventListener("change", () => {
        keepSecondaryFilters = !!els.settings_keep_secondary.checked;
        storageSet("pjr_keep_secondary", keepSecondaryFilters ? "1" : "0");
      });
    }

    if (els.settings_density) {
      els.settings_density.addEventListener("change", () => {
        uiDensity = els.settings_density.value === "compact" ? "compact" : "comfortable";
        storageSet("pjr_density", uiDensity);
        updateDensityUi();
      });
    }

    if (els.settings_direction) {
      els.settings_direction.addEventListener("change", () => {
        uiDirection = ["auto", "ltr", "rtl"].includes(els.settings_direction.value) ? els.settings_direction.value : "auto";
        storageSet("pjr_dir", uiDirection);
        updateDirectionUi();
      });
    }

    if (els.command_input) {
      els.command_input.addEventListener("input", () => updateCommandList(els.command_input.value));
      els.command_input.addEventListener("keydown", async (ev) => {
        if (ev.key === "Enter") {
          const first = els.command_list ? els.command_list.querySelector("button[data-action='command-run']") : null;
          if (first) {
            ev.preventDefault();
            await runCommand(first.getAttribute("data-command") || "");
          }
        }
      });
    }

    els.follow.addEventListener("change", () => {
      follow = !!els.follow.checked;
      storageSet("pjr_follow", follow ? "1" : "0");
    });

    els.wrap.addEventListener("change", () => {
      wrap = !!els.wrap.checked;
      storageSet("pjr_wrap", wrap ? "1" : "0");
      applyLogStyle();
      renderLog(currentTab);
    });

    els.font.addEventListener("input", () => {
      fontSize = clampInt(els.font.value, 11, 18, fontSize);
      storageSet("pjr_font", String(fontSize));
      applyLogStyle();
    });

    if (els.pause) {
      els.pause.addEventListener("change", () => {
        paused = !!els.pause.checked;
        storageSet("pjr_pause", paused ? "1" : "0");
      });
    }
    if (els.hilite) {
      els.hilite.addEventListener("change", () => {
        hilite = !!els.hilite.checked;
        storageSet("pjr_hilite", hilite ? "1" : "0");
        renderLog(currentTab);
      });
    }

    els.logsearch.addEventListener("input", onLogSearchDebounced);
    if (els.logview) {
      els.logview.addEventListener("scroll", () => {
        onLogScrollAutoPause();
      }, { passive: true });
    }
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

    window.addEventListener("keydown", (ev) => {
      if ((ev.metaKey || ev.ctrlKey) && String(ev.key).toLowerCase() === "k") {
        ev.preventDefault();
        openCommand();
        return;
      }
      if (ev.defaultPrevented) return;
      if (ev.key !== "/") return;
      const active = document.activeElement;
      const isTyping = active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable);
      if (isTyping) return;
      if (!els.search) return;
      ev.preventDefault();
      els.search.focus();
    });

    if (els.desktop_splitter) {
      els.desktop_splitter.addEventListener("pointerdown", (ev) => {
        if (window.innerWidth < 1100) return;
        ev.preventDefault();
        const startX = ev.clientX;
        const startWidth = jobsPaneWidth;
        document.body.classList.add("splitter-dragging");
        const onMove = (moveEv) => {
          const dir = document.documentElement.getAttribute("dir") === "rtl" ? -1 : 1;
          jobsPaneWidth = startWidth + ((moveEv.clientX - startX) * dir);
          updateSplitUi();
        };
        const onUp = () => {
          document.body.classList.remove("splitter-dragging");
          storageSet("pjr_jobs_pane_width", String(Math.round(jobsPaneWidth)));
          window.removeEventListener("pointermove", onMove);
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp, { once: true });
      });
    }

    window.addEventListener("resize", () => {
      updateSplitUi();
    });
  }

  function cacheEls() {
    els.statuspill = document.getElementById("statuspill");
    els.statusline = document.getElementById("statusline");
    els.lastupdated = document.getElementById("lastupdated");
    els.ha_host_pill = document.getElementById("ha_host_pill");
    els.ha_host_label = document.getElementById("ha_host_label");
    els.meta_ha_host = document.getElementById("meta_ha_host");
    els.meta_access_mode = document.getElementById("meta_access_mode");
    els.meta_allowed_cidrs = document.getElementById("meta_allowed_cidrs");

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

    els.pollms = document.getElementById("pollms");
    els.search = document.getElementById("search");
    els.job_sort = document.getElementById("job_sort");
    els.filter_has_result = document.getElementById("filter_has_result");
    els.filter_user = document.getElementById("filter_user");
    els.filter_user_list = document.getElementById("filter_user_list");
    els.clear_user_filter = document.querySelector('[data-action="clear-user-filter"]');
    els.filter_since = document.getElementById("filter_since");
    els.clear_filters = document.getElementById("clear_filters");
    els.jobs_count = document.getElementById("jobs_count");
    els.jobs_pagination = document.getElementById("jobs_pagination");
    els.page_prev = document.getElementById("page_prev");
    els.page_next = document.getElementById("page_next");
    els.page_summary = document.getElementById("page_summary");
    els.main_header = document.getElementById("main_header");
    els.header_more_toggle = document.getElementById("header_more_toggle");
    els.header_more_panel = document.getElementById("header_more_panel");
    els.desktop_splitter = document.getElementById("desktop_splitter");

    els.detail = document.getElementById("detail");
    els.detail_empty = document.getElementById("detail_empty");
    els.jobid = document.getElementById("jobid");
    els.meta = document.getElementById("meta");
    els.detail_state_banner = document.getElementById("detail_state_banner");
    els.state_badge = document.getElementById("state_badge");
    els.state_title = document.getElementById("state_title");
    els.state_description = document.getElementById("state_description");
    els.detail_timeline = document.getElementById("detail_timeline");
    els.detail_result_summary = document.getElementById("detail_result_summary");
    els.detail_limits_summary = document.getElementById("detail_limits_summary");
    els.detail_failure_summary = document.getElementById("detail_failure_summary");
    els.detail_inline_state = document.getElementById("detail_inline_state");
    els.detail_progress_shell = document.getElementById("detail_progress_shell");
    els.detail_progress = document.getElementById("detail_progress");
    els.detail_progress_bar = document.getElementById("detail_progress_bar");
    els.detail_progress_copy = document.getElementById("detail_progress_copy");
    els.detail_breadcrumb_current = document.getElementById("detail_breadcrumb_current");

    els.follow = document.getElementById("follow");
    els.btn_live = document.getElementById("btn_live");
    els.btn_pause_resume = document.getElementById("btn_pause_resume");
    els.btn_jump_latest = document.getElementById("btn_jump_latest");
    els.btn_clear_log = document.getElementById("btn_clear_log");
    els.livepill = document.getElementById("livepill");
    els.livestate = document.getElementById("livestate");

    els.hterm_input = document.getElementById("hterm_input");
    els.hterms_custom = document.getElementById("hterms_custom");
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

    els.command_overlay = document.getElementById("command_overlay");
    els.command_modal = document.getElementById("command_modal");
    els.command_close = document.getElementById("command_close");
    els.command_input = document.getElementById("command_input");
    els.command_list = document.getElementById("command_list");
    els.confirm_overlay = document.getElementById("confirm_overlay");
    els.confirm_modal = document.getElementById("confirm_modal");
    els.confirm_close = document.getElementById("confirm_close");
    els.confirm_title = document.getElementById("confirm_title");
    els.confirm_body = document.getElementById("confirm_body");
    els.confirm_accept = document.getElementById("confirm_accept");
    els.row_popover = document.getElementById("row_popover");
    els.row_popover_label = document.getElementById("row_popover_label");
    els.row_popover_list = document.getElementById("row_popover_list");
    els.row_popover_progress_shell = document.getElementById("row_popover_progress_shell");
    els.row_popover_progress = document.getElementById("row_popover_progress");
    els.row_popover_progress_bar = document.getElementById("row_popover_progress_bar");
    els.row_popover_progress_copy = document.getElementById("row_popover_progress_copy");
    els.row_menu = document.getElementById("row_menu");
    els.row_menu_label = document.getElementById("row_menu_label");
    els.row_menu_zip = document.getElementById("row_menu_zip");

    els.about_overlay = document.getElementById("about_overlay");
    els.setup_overlay = document.getElementById("setup_overlay");
    els.setup_modal = document.getElementById("setup_modal");
    els.setup_close = document.getElementById("setup_close");
    els.setup_refresh = document.getElementById("setup_refresh");
    els.setup_status_banner = document.getElementById("setup_status_banner");
    els.setup_persistent_mode_summary = document.getElementById("setup_persistent_mode_summary");
    els.setup_apply_persistent_mode = document.getElementById("setup_apply_persistent_mode");
    els.setup_target_summary = document.getElementById("setup_target_summary");
    els.setup_settings_summary = document.getElementById("setup_settings_summary");
    els.setup_settings_list = document.getElementById("setup_settings_list");
    els.setup_wheels_summary = document.getElementById("setup_wheels_summary");
    els.setup_wheel_file = document.getElementById("setup_wheel_file");
    els.setup_upload_wheel = document.getElementById("setup_upload_wheel");
    els.setup_clear_wheel_file = document.getElementById("setup_clear_wheel_file");
    els.setup_wheel_picker_summary = document.getElementById("setup_wheel_picker_summary");
    els.setup_wheels_list = document.getElementById("setup_wheels_list");
    els.setup_profiles_summary = document.getElementById("setup_profiles_summary");
    els.setup_profile_zip_file = document.getElementById("setup_profile_zip_file");
    els.setup_upload_profile_zip = document.getElementById("setup_upload_profile_zip");
    els.setup_clear_profile_zip_file = document.getElementById("setup_clear_profile_zip_file");
    els.setup_profile_picker_summary = document.getElementById("setup_profile_picker_summary");
    els.setup_profiles_list = document.getElementById("setup_profiles_list");
    els.setup_readiness_summary = document.getElementById("setup_readiness_summary");
    els.setup_build_target_profile = document.getElementById("setup_build_target_profile");
    els.setup_rebuild_target_profile = document.getElementById("setup_rebuild_target_profile");
    els.setup_copy_config_snippet = document.getElementById("setup_copy_config_snippet");
    els.setup_build_summary = document.getElementById("setup_build_summary");
    els.setup_config_snippet = document.getElementById("setup_config_snippet");
    els.setup_restart_guidance = document.getElementById("setup_restart_guidance");
    els.setup_blockers_list = document.getElementById("setup_blockers_list");
    els.setup_warnings_list = document.getElementById("setup_warnings_list");
    els.setup_next_steps_list = document.getElementById("setup_next_steps_list");
    els.about_modal = document.getElementById("about_modal");
    els.about_close = document.getElementById("about_close");
    els.about_sub = document.getElementById("about_sub");
    els.about_api = document.getElementById("about_api");
    els.about_python = document.getElementById("about_python");
    els.about_curl = document.getElementById("about_curl");

    els.settings_overlay = document.getElementById("settings_overlay");
    els.settings_modal = document.getElementById("settings_modal");
    els.settings_close = document.getElementById("settings_close");
    els.settings_default_sort = document.getElementById("settings_default_sort");
    els.settings_keep_secondary = document.getElementById("settings_keep_secondary");
    els.settings_density = document.getElementById("settings_density");
    els.settings_direction = document.getElementById("settings_direction");

    els.adv_overlay = document.getElementById("adv_overlay");
    els.adv_modal = document.getElementById("adv_modal");
    els.adv_close = document.getElementById("adv_close");
    els.package_cache_summary = document.getElementById("package_cache_summary");
    els.package_cache_list = document.getElementById("package_cache_list");
    els.package_profiles_summary = document.getElementById("package_profiles_summary");
    els.package_profiles_list = document.getElementById("package_profiles_list");
    els.auto = document.getElementById("auto");
    els.btn_back = document.getElementById("btn_back");
    els.btn_cancel = document.getElementById("btn_cancel");
    els.btn_delete = document.getElementById("btn_delete");
    els.logtools = document.getElementById("logtools");
    els.hilitebar = document.getElementById("hilitebar");
    els.findbar = document.getElementById("findbar");
  }

  /**
   * Initialise the UI: cache DOM elements, bind event handlers and restore persisted state.
   *
   * Loads settings from localStorage (view, tab, poll interval, auto, search, sort, filters, follow,
   * wrap, font, pause, hilite, pane), updates the UI to reflect those settings, loads highlight terms,
   * applies log styling and pane layout, attaches scroll/resize and window lifecycle listeners, triggers
   * an initial full refresh and restores any selected job, then starts the regular tick loop.
   */
  async function init() {
    cacheEls();
    bindEvents();

    const savedView = storageGet("pjr_view");
    if (savedView) view = savedView;

    const savedTab = storageGet("pjr_tab");
    if (savedTab) currentTab = savedTab;

    const savedPoll = storageGet("pjr_pollms");
    if (savedPoll) pollMs = clampInt(savedPoll, 250, 10000, pollMs);
    els.pollms.value = String(pollMs);

    const savedAuto = storageGet("pjr_auto");
    if (savedAuto !== null) auto = (savedAuto === "1");
    if (els.auto) els.auto.checked = auto;

    const savedSearch = storageGet("pjr_search");
    if (savedSearch !== null) els.search.value = savedSearch;

    const savedSort = storageGet("pjr_sort");
    if (savedSort) sortMode = savedSort;
    if (els.job_sort) els.job_sort.value = sortMode;

    const savedKeepSecondary = storageGet("pjr_keep_secondary");
    if (savedKeepSecondary !== null) keepSecondaryFilters = (savedKeepSecondary === "1");
    if (els.settings_keep_secondary) els.settings_keep_secondary.checked = keepSecondaryFilters;

    const savedHasResult = storageGet("pjr_has_result");
    if (savedHasResult !== null && keepSecondaryFilters) filterHasResult = (savedHasResult === "1");
    if (els.filter_has_result) els.filter_has_result.checked = filterHasResult;

    const savedUserFilter = storageGet("pjr_filter_user");
    if (savedUserFilter !== null) filterUser = savedUserFilter;
    if (els.filter_user) els.filter_user.value = filterUser;

    const savedSinceFilter = storageGet("pjr_filter_since");
    if (savedSinceFilter !== null) filterSince = savedSinceFilter;
    if (els.filter_since) els.filter_since.value = filterSince;
    updateFiltersSummaryUi();

    const savedDensity = storageGet("pjr_density");
    if (savedDensity) uiDensity = savedDensity === "compact" ? "compact" : "comfortable";
    if (els.settings_density) els.settings_density.value = uiDensity;
    updateDensityUi();

    const savedDirection = storageGet("pjr_dir");
    if (savedDirection && ["auto", "ltr", "rtl"].includes(savedDirection)) uiDirection = savedDirection;
    if (els.settings_direction) els.settings_direction.value = uiDirection;
    updateDirectionUi();

    const savedFollow = storageGet("pjr_follow");
    if (savedFollow !== null) follow = (savedFollow === "1");
    els.follow.checked = follow;

    const savedWrap = storageGet("pjr_wrap");
    if (savedWrap !== null) wrap = (savedWrap === "1");
    els.wrap.checked = wrap;

    const savedFont = storageGet("pjr_font");
    if (savedFont) fontSize = clampInt(savedFont, 11, 18, fontSize);
    els.font.value = String(fontSize);

    const savedPause = storageGet("pjr_pause");
    if (savedPause !== null) paused = (savedPause === "1");
    if (els.pause) els.pause.checked = paused;
    updateLiveUi();

    const savedHilite = storageGet("pjr_hilite");
    if (savedHilite !== null) hilite = (savedHilite === "1");
    if (els.hilite) els.hilite.checked = hilite;

    _loadHighlightTerms();
    updateHighlightUi();

    if (els.settings_default_sort) els.settings_default_sort.value = sortMode;

    const savedPaneWidth = storageGet("pjr_jobs_pane_width");
    if (savedPaneWidth) jobsPaneWidth = clampInt(savedPaneWidth, 360, 900, jobsPaneWidth);
    updateSplitUi();

    const savedPane = storageGet("pjr_pane");
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
    updateClearButtonVisibility();
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
