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
