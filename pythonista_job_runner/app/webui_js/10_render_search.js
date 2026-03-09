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
    let jobs = jobsCache.slice(0);

    if (view !== "all") {
      jobs = jobs.filter((j) => (j.state || "queued") === view);
    }

    if (filterHasResult) {
      jobs = jobs.filter((j) => !!j.result_ready);
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

    renderJobs(jobs, q);
    updateSortUi();
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

    const tdJob = document.createElement("td");
    tdJob.setAttribute("data-label", "Job");
    const wrap = document.createElement("div");
    wrap.className = "jobcell";
    const line = document.createElement("div");
    line.className = "jobline";

    const btnJob = document.createElement("button");
    btnJob.type = "button";
    btnJob.className = "small jobbtn";
    btnJob.addEventListener("click", () => selectJob(tr.dataset.jobId || ""));

    const inlineState = document.createElement("span");
    inlineState.className = "state-badge-inline";

    line.append(btnJob, inlineState);

    const meta = document.createElement("div");
    meta.className = "jobmeta";

    wrap.append(line, meta);
    tdJob.appendChild(wrap);

    const tdState = document.createElement("td");
    tdState.setAttribute("data-label", "State");

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

    const overflow = document.createElement("details");
    overflow.className = "row-overflow";
    const summary = document.createElement("summary");
    summary.setAttribute("aria-label", "More actions");
    summary.textContent = "More";

    const menu = document.createElement("div");
    menu.className = "row-overflow-menu";

    const zip = document.createElement("a");
    zip.className = "linkbtn secondary";
    zip.textContent = "Zip";
    zip.target = "_blank";
    zip.rel = "noopener noreferrer";

    const copyId = document.createElement("button");
    copyId.type = "button";
    copyId.className = "small secondary";
    copyId.textContent = "Copy id";
    copyId.addEventListener("click", async (ev) => {
      ev.preventDefault();
      const id = tr.dataset.jobId || "";
      if (!id) return;
      try {
        await copyTextToClipboard(id);
        toast("ok", "Copied", "Job id copied");
        overflow.open = false;
      } catch (err) {
        toast("err", "Copy failed", (err && err.message) ? err.message : "Could not copy job id to clipboard");
      }
    });

    menu.append(zip, copyId);
    overflow.append(summary, menu);
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
    const isSelected = !!(currentJob && jobId === currentJob);
    tr.classList.toggle("selected", isSelected);
    tr.setAttribute("aria-selected", isSelected ? "true" : "false");

    const tdJob = tr.children[0];
    const btnJob = tdJob.querySelector(".jobbtn");
    if (btnJob) {
      btnJob.textContent = jobId;
      btnJob.title = jobId;
    }

    const meta = tdJob.querySelector(".jobmeta");
    if (meta) {
      meta.textContent = "";
      const addMeta = (label, value) => {
        const v = String(value || "");
        if (!v) return;
        const span = document.createElement("span");
        span.className = "meta";
        span.textContent = `${label}: ${v}`;
        meta.appendChild(span);
      };

      addMeta("Age", age);
      addMeta("Duration", dur);
      addMeta("User", user);
      if (j.exit_code !== undefined && j.exit_code !== null && String(j.exit_code) !== "") addMeta("Exit", String(j.exit_code));
    }

    const inlineState = tdJob.querySelector(".state-badge-inline");
    if (inlineState) {
      inlineState.textContent = "";
      inlineState.appendChild(badgeEl(state));
    }

    const tdState = tr.children[1];
    if (!tdState) return;
    tdState.textContent = "";
    tdState.appendChild(badgeEl(state));

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
  function renderJobs(jobs, query) {
    const tbody = els.jobtable_tbody;
    const hasJobs = jobs.length !== 0;
    els.empty.hidden = hasJobs;
    const tableWrap = document.querySelector(".tablewrap");
    const tableRegion = document.querySelector(".table-region");
    if (tableWrap) tableWrap.hidden = !hasJobs;
    if (tableRegion) tableRegion.classList.toggle("has-jobs", hasJobs);
    if (els.jobs_count) els.jobs_count.textContent = String(jobs.length);

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
        } else if (view !== "all" || (query && String(query).trim())) {
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
          } else if (view !== "all" || (query && String(query).trim())) {
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
      let tr = _ensureRow(jobId);
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
  let _settingsReturnFocus = null;
  let _commandReturnFocus = null;
  let _confirmReturnFocus = null;
  let confirmActionHandler = null;

  function commandItems() {
    return [
      { key: "refresh", title: "Refresh now", description: "Reload queue stats, jobs, and the selected detail view.", hint: "Action", action: async () => refreshAll() },
      { key: "search", title: "Focus search", description: "Jump straight to the Jobs search field.", hint: "/", action: async () => { if (els.search) els.search.focus(); } },
      { key: "settings", title: "Open settings", description: "Change runtime and UI preferences.", hint: "Panel", action: async () => openSettings() },
      { key: "help", title: "Open help", description: "See quick start, samples, and troubleshooting.", hint: "Panel", action: async () => openAbout() },
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
