/* VERSION: 0.6.12 */
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
