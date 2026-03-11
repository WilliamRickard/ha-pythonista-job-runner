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
    span.textContent = cls;
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
