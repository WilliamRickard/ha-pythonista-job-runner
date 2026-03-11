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
