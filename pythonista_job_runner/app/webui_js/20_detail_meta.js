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
