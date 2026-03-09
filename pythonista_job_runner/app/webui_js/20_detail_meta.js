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

    if (els.detail_limits_summary) {
      const cpu = (limits.cpu_percent === null || limits.cpu_percent === undefined) ? "?" : String(limits.cpu_percent);
      const mem = (limits.mem_mb === null || limits.mem_mb === undefined) ? "?" : String(limits.mem_mb);
      const threads = (limits.threads === null || limits.threads === undefined) ? "?" : String(limits.threads);
      els.detail_limits_summary.textContent = `CPU ${cpu}% · Memory ${mem} MB · Threads ${threads}`;
    }

    if (els.detail_result_summary) {
      const filename = st.result_filename ? String(st.result_filename) : "result archive";
      if (st.state === "done") {
        els.detail_result_summary.textContent = `${filename} is expected to be ready. Use Download zip to inspect outputs and status.json.`;
      } else if (st.state === "error") {
        els.detail_result_summary.textContent = `Job failed before final results were guaranteed. Check stderr and status details.`;
      } else {
        els.detail_result_summary.textContent = `Result archive not ready yet. Current state: ${String(st.state || "queued")}.`;
      }
    }

    if (els.detail_failure_summary) {
      if (st.state === "error") {
        const err = st.error ? String(st.error) : "Unknown error";
        const exit = (st.exit_code === null || st.exit_code === undefined) ? "" : ` (exit ${st.exit_code})`;
        els.detail_failure_summary.textContent = `${err}${exit}`;
      } else if (st.state === "done") {
        els.detail_failure_summary.textContent = "No failure detected. Inspect stdout/stderr for warnings if needed.";
      } else {
        els.detail_failure_summary.textContent = "Failure diagnosis becomes available when the job finishes.";
      }
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
      ["Result file", s.result_filename || ""],
      ["Input SHA256", s.input_sha256 || ""],
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
    _renderTimeline(s);
    _renderInsights(s);
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
