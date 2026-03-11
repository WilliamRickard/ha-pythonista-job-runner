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
        }
        if (action === "focus-search" && els.search) els.search.focus();
        if (action === "reset-ui") openConfirm({ title: "Reset UI settings?", body: "Saved UI preferences such as density, sorting, and filters will be cleared.", confirmLabel: "Reset UI", onConfirm: async () => resetUi() });
        if (action === "jump-error") jumpToNextError();
        if (action === "set-view") setView(btn.getAttribute("data-view") || "all");
        if (action === "set-sort") setSort(btn.getAttribute("data-sort") || "newest", btn);
        if (action === "set-date-preset") setDatePreset(btn.getAttribute("data-preset") || "clear");
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
      });
    }

    if (els.filter_user) {
      els.filter_user.addEventListener("input", () => {
        filterUser = String(els.filter_user.value || "").trim();
        currentPage = 1;
        storageSet("pjr_filter_user", filterUser);
        applyFilters();
        updateClearButtonVisibility();
      });
    }

    if (els.filter_since) {
      els.filter_since.addEventListener("change", () => {
        filterSince = String(els.filter_since.value || "").trim();
        currentPage = 1;
        storageSet("pjr_filter_since", filterSince);
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
