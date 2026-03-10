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
