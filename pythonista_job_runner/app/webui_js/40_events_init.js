function toggleAuto() {
    auto = !auto;
    if (els.auto) els.auto.checked = auto;
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
        if (action === "open-settings") openSettings();
        if (action === "close-settings") closeSettings();
        if (action === "open-advanced") openAdvanced();
        if (action === "close-advanced") closeAdvanced();
        if (action === "back-to-jobs") setPane("jobs");
        if (action === "clear-filters") clearFilters();
        if (action === "focus-search" && els.search) els.search.focus();
        if (action === "reset-ui") resetUi();
        if (action === "jump-error") jumpToNextError();
        if (action === "set-view") setView(btn.getAttribute("data-view") || "all");
        if (action === "purge") await purgeState(btn.getAttribute("data-state") || "");
        if (action === "set-tab") setTab(btn.getAttribute("data-tab") || "stdout");
        if (action === "find-next") findNext();
        if (action === "find-prev") findPrev();
        if (action === "clear-search") clearSearch();
        if (action === "copy-curl") await copyCurl();
        if (action === "copy-sample-task") await copySampleTask();
        if (action === "copy-about-curl") await copyAboutCurl();
        if (action === "open-about") await openAbout();
        if (action === "close-about") closeAbout();
        if (action === "copy-base") await copyBase();
        if (action === "open-info") window.open(apiUrl("info.json"), "_blank", "noopener,noreferrer");
        if (action === "copy-endpoint") await copyEndpoint(btn);
        if (action === "download-zip") downloadZip();
        if (action === "download-text") downloadText(btn.getAttribute("data-which") || "stdout");
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

    if (els.settings_close) {
      const close = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        closeSettings();
      };
      els.settings_close.addEventListener("click", close);
      els.settings_close.addEventListener("touchend", close, { passive: false });
    }

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") {
        if (!els.about_overlay.hidden) closeAbout();
        if (!els.adv_overlay.hidden) closeAdvanced();
        if (!els.settings_overlay.hidden) closeSettings();
        return;
      }
      if (ev.key === "Tab") {
        if (!els.about_overlay.hidden) trapTabKey(ev, els.about_modal || els.about_overlay);
        if (!els.adv_overlay.hidden) trapTabKey(ev, els.adv_modal || els.adv_overlay);
        if (!els.settings_overlay.hidden) trapTabKey(ev, els.settings_modal || els.settings_overlay);
      }
    });

    els.pollms.addEventListener("change", () => {
      setPollMsFromInput();
      storageSet("pjr_pollms", String(pollMs));
    });
    els.search.addEventListener("input", () => {
      storageSet("pjr_search", String(els.search.value || ""));
      applyFilters();
      updateClearButtonVisibility();
    });
    if (els.job_sort) {
      els.job_sort.addEventListener("change", () => {
        sortMode = els.job_sort.value || "newest";
        storageSet("pjr_sort", sortMode);
        applyFilters();
        updateClearButtonVisibility();
      });
    }
    if (els.filter_has_result) {
      els.filter_has_result.addEventListener("change", () => {
        filterHasResult = !!els.filter_has_result.checked;
        storageSet("pjr_has_result", filterHasResult ? "1" : "0");
        applyFilters();
        updateClearButtonVisibility();
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
        if (els.job_sort) els.job_sort.value = sortMode;
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
      if (ev.defaultPrevented) return;
      if (ev.key !== "/") return;
      const active = document.activeElement;
      const isTyping = active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable);
      if (isTyping) return;
      if (!els.search) return;
      ev.preventDefault();
      els.search.focus();
    });
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

    els.pollms = document.getElementById("pollms");
    els.search = document.getElementById("search");
    els.job_sort = document.getElementById("job_sort");
    els.filter_has_result = document.getElementById("filter_has_result");
    els.clear_filters = document.getElementById("clear_filters");
    els.jobs_count = document.getElementById("jobs_count");
    els.main_header = document.getElementById("main_header");

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

    els.about_overlay = document.getElementById("about_overlay");
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

    els.adv_overlay = document.getElementById("adv_overlay");
    els.adv_modal = document.getElementById("adv_modal");
    els.adv_close = document.getElementById("adv_close");
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

    const savedDensity = storageGet("pjr_density");
    if (savedDensity) uiDensity = savedDensity === "compact" ? "compact" : "comfortable";
    if (els.settings_density) els.settings_density.value = uiDensity;
    updateDensityUi();

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
