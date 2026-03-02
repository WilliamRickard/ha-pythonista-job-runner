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
      try {
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
      } catch (e) {
        toast("err", "Action failed", e && e.message ? e.message : String(e));
      }
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
    els.logtools = document.getElementById("logtools");
    els.findbar = document.getElementById("findbar");
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
