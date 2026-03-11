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

  function setupBadgeText(enabled) {
    return enabled ? "Enabled" : "Disabled";
  }

  function createSetupRow(titleText, descriptionText, metaText) {
    const row = document.createElement("div");
    row.className = "item-row";
    const copy = document.createElement("div");
    copy.className = "item-copy";
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = titleText;
    const desc = document.createElement("div");
    desc.className = "item-description";
    desc.textContent = descriptionText;
    copy.append(title, desc);
    row.appendChild(copy);
    if (metaText) {
      const meta = document.createElement("div");
      meta.className = "item-meta";
      meta.textContent = metaText;
      row.appendChild(meta);
    }
    return row;
  }

  function createSetupActionButton(label, action, dataName, dataValue) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "small tertiary";
    btn.textContent = label;
    btn.setAttribute("data-action", action);
    if (dataName) btn.setAttribute(dataName, String(dataValue || ""));
    return btn;
  }

  function createSetupManagedRow(titleText, descriptionText, metaText, buttons) {
    const row = createSetupRow(titleText, descriptionText, metaText);
    if (Array.isArray(buttons) && buttons.length) {
      const actions = document.createElement("div");
      actions.className = "item-actions";
      for (const btn of buttons) {
        if (btn instanceof HTMLElement) actions.appendChild(btn);
      }
      if (actions.childElementCount) row.appendChild(actions);
    }
    return row;
  }

  function renderSetupSectionList(container, rows, emptyText) {
    if (!(container instanceof HTMLElement)) return;
    container.textContent = "";
    if (!Array.isArray(rows) || !rows.length) {
      const empty = document.createElement("div");
      empty.className = "field-hint";
      empty.textContent = emptyText;
      container.appendChild(empty);
      return;
    }
    for (const row of rows) {
      container.appendChild(row);
    }
  }

  function renderSetupTextList(container, heading, items, emptyText) {
    if (!(container instanceof HTMLElement)) return;
    container.textContent = "";
    const values = Array.isArray(items) ? items.filter((item) => String(item || "").trim()) : [];
    if (!values.length) {
      const empty = document.createElement("div");
      empty.className = "field-hint";
      empty.textContent = emptyText;
      container.appendChild(empty);
      return;
    }
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = heading;
    container.appendChild(title);
    for (const item of values) {
      const row = document.createElement("div");
      row.className = "item-row";
      const copy = document.createElement("div");
      copy.className = "item-copy";
      const desc = document.createElement("div");
      desc.className = "item-description";
      desc.textContent = String(item);
      copy.appendChild(desc);
      row.appendChild(copy);
      container.appendChild(row);
    }
  }

  function selectedSetupFile(kind) {
    const input = kind === "profile" ? els.setup_profile_zip_file : els.setup_wheel_file;
    if (!(input instanceof HTMLInputElement) || !input.files || !input.files.length) return null;
    return input.files[0] || null;
  }

  function updateSetupPickerSummary(kind) {
    const file = selectedSetupFile(kind);
    if (kind === "profile") {
      if (els.setup_profile_picker_summary) {
        els.setup_profile_picker_summary.textContent = file
          ? `Selected profile archive: ${file.name}`
          : "Choose one profile archive to upload into /config/package_profiles.";
      }
      if (els.setup_upload_profile_zip) els.setup_upload_profile_zip.disabled = !file;
      if (els.setup_clear_profile_zip_file) els.setup_clear_profile_zip_file.disabled = !file;
      return;
    }
    if (els.setup_wheel_picker_summary) {
      els.setup_wheel_picker_summary.textContent = file
        ? `Selected wheel file: ${file.name}`
        : "Choose one .whl file to upload into /config/wheel_uploads.";
    }
    if (els.setup_upload_wheel) els.setup_upload_wheel.disabled = !file;
    if (els.setup_clear_wheel_file) els.setup_clear_wheel_file.disabled = !file;
  }

  function clearSetupSelectedFile(kind) {
    const input = kind === "profile" ? els.setup_profile_zip_file : els.setup_wheel_file;
    if (input instanceof HTMLInputElement) input.value = "";
    updateSetupPickerSummary(kind);
  }

  async function setupRequest(path, opts) {
    const response = await fetch(apiUrl(path), Object.assign({ credentials: "same-origin" }, opts || {}));
    const ct = response.headers.get("content-type") || "";
    const payload = ct.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const message = (payload && typeof payload === "object" && payload.error)
        ? String(payload.error)
        : `${response.status}`;
      const err = new Error(message);
      err.status = response.status;
      err.payload = payload;
      throw err;
    }
    return payload;
  }

  function setSetupBusy(isBusy, bannerText) {
    const busy = !!isBusy;
    const cached = setupStatusCache && typeof setupStatusCache === "object" ? setupStatusCache : {};
    if (els.setup_refresh) els.setup_refresh.disabled = busy;
    if (els.setup_upload_wheel) els.setup_upload_wheel.disabled = busy || !selectedSetupFile("wheel");
    if (els.setup_clear_wheel_file) els.setup_clear_wheel_file.disabled = busy || !selectedSetupFile("wheel");
    if (els.setup_upload_profile_zip) els.setup_upload_profile_zip.disabled = busy || !selectedSetupFile("profile");
    if (els.setup_clear_profile_zip_file) els.setup_clear_profile_zip_file.disabled = busy || !selectedSetupFile("profile");
    if (els.setup_build_target_profile) els.setup_build_target_profile.disabled = busy || !cached.build_available;
    if (els.setup_rebuild_target_profile) els.setup_rebuild_target_profile.disabled = busy || !cached.rebuild_available;
    if (els.setup_copy_config_snippet) els.setup_copy_config_snippet.disabled = busy || !String(cached.config_snippet || "").trim();
    if (busy && els.setup_status_banner && bannerText) {
      els.setup_status_banner.classList.remove("ok", "warn", "err");
      els.setup_status_banner.textContent = bannerText;
    }
  }

  function applySetupStatusPayload(payload) {
    const nextPayload = (payload && typeof payload === "object" && payload.setup_status && typeof payload.setup_status === "object")
      ? payload.setup_status
      : payload;
    if (nextPayload && typeof nextPayload === "object") {
      renderSetupStatus(nextPayload);
      return;
    }
    refreshSetupStatus().catch((_err) => {});
  }

  async function buildSetupTargetProfile(rebuild) {
    const target = String((setupStatusCache && setupStatusCache.target_profile) || "").trim();
    if (!target) {
      toast("err", "No target profile", "Refresh Setup and try again.");
      return;
    }
    const actionText = rebuild ? "Rebuilding" : "Building";
    setSetupBusy(true, `${actionText} ${target}…`);
    try {
      const payload = await setupRequest("package_profiles/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: target, rebuild: !!rebuild }),
      });
      applySetupStatusPayload(payload || {});
      await refreshPackageProfiles().catch((_err) => {});
      await refreshAll({ silent: true });
      const status = String((payload && payload.status) || "unknown");
      toast(status === "ready" ? "ok" : "err", rebuild ? "Profile rebuilt" : "Profile built", `${target}: ${status}`);
    } catch (err) {
      const payload = err && err.payload && typeof err.payload === "object" ? err.payload : null;
      if (payload) applySetupStatusPayload(payload);
      const msg = payload && payload.error ? String(payload.error) : String(err && err.message ? err.message : err);
      toast("err", rebuild ? "Rebuild failed" : "Build failed", `${target}: ${msg}`);
    } finally {
      setSetupBusy(false);
    }
  }

  async function copySetupConfigSnippet() {
    const snippet = String((setupStatusCache && setupStatusCache.config_snippet) || (els.setup_config_snippet && els.setup_config_snippet.value) || "").trim();
    if (!snippet) {
      toast("err", "No config snippet", "Refresh Setup and try again.");
      return;
    }
    await copyTextToClipboard(snippet);
    toast("ok", "Copied", "Suggested add-on config copied to clipboard");
  }

  async function uploadSetupBinary(kind, overwrite) {
    const file = selectedSetupFile(kind);
    if (!file) {
      toast("err", "No file selected", kind === "profile" ? "Choose a profile archive first." : "Choose a wheel file first.");
      return;
    }
    const path = kind === "profile" ? "setup/upload-profile-zip" : "setup/upload-wheel";
    const noun = kind === "profile" ? "profile archive" : "wheel";
    const query = `${path}?filename=${encodeURIComponent(file.name)}${overwrite ? "&overwrite=1" : ""}`;
    setSetupBusy(true, `Uploading ${file.name}…`);
    try {
      const payload = await setupRequest(query, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
      });
      clearSetupSelectedFile(kind);
      applySetupStatusPayload(payload || {});
      toast("ok", overwrite ? "Replaced" : "Uploaded", `${file.name} ${overwrite ? "replaced" : `${noun} uploaded`}.`);
    } catch (err) {
      const status = Number(err && err.status ? err.status : 0);
      const payload = err && err.payload && typeof err.payload === "object" ? err.payload : null;
      if (!overwrite && status === 409 && payload && String(payload.error || "") === "already_exists") {
        openConfirm({
          title: `Replace ${file.name}?`,
          body: `A file with that name already exists. Replace it with the selected ${noun}?`,
          confirmLabel: "Replace",
          onConfirm: async () => uploadSetupBinary(kind, true),
        });
      } else {
        const msg = payload && payload.error ? String(payload.error) : String(err && err.message ? err.message : err);
        toast("err", `Upload failed`, `${file.name}: ${msg}`);
      }
    } finally {
      setSetupBusy(false);
    }
  }

  async function performDeleteSetupWheel(filename) {
    const safeName = String(filename || "").trim();
    if (!safeName) return;
    setSetupBusy(true, `Deleting ${safeName}…`);
    try {
      const payload = await setupRequest("setup/delete-wheel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: safeName }),
      });
      applySetupStatusPayload(payload || {});
      toast("ok", "Wheel deleted", safeName);
    } catch (err) {
      const payload = err && err.payload && typeof err.payload === "object" ? err.payload : null;
      const msg = payload && payload.error ? String(payload.error) : String(err && err.message ? err.message : err);
      toast("err", "Delete failed", `${safeName}: ${msg}`);
    } finally {
      setSetupBusy(false);
    }
  }

  function deleteSetupWheel(filename) {
    const safeName = String(filename || "").trim();
    if (!safeName) return;
    openConfirm({
      title: `Delete wheel ${safeName}?`,
      body: "This removes the uploaded wheel and its imported copy from the internal wheelhouse.",
      confirmLabel: "Delete wheel",
      onConfirm: async () => performDeleteSetupWheel(safeName),
    });
  }

  async function performDeleteSetupProfile(profileName) {
    const safeName = String(profileName || "").trim();
    if (!safeName) return;
    setSetupBusy(true, `Deleting ${safeName}…`);
    try {
      const payload = await setupRequest("setup/delete-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: safeName }),
      });
      applySetupStatusPayload(payload || {});
      toast("ok", "Profile deleted", safeName);
    } catch (err) {
      const payload = err && err.payload && typeof err.payload === "object" ? err.payload : null;
      const msg = payload && payload.error ? String(payload.error) : String(err && err.message ? err.message : err);
      toast("err", "Delete failed", `${safeName}: ${msg}`);
    } finally {
      setSetupBusy(false);
    }
  }

  function deleteSetupProfile(profileName) {
    const safeName = String(profileName || "").trim();
    if (!safeName) return;
    openConfirm({
      title: `Delete profile ${safeName}?`,
      body: "This removes the uploaded package profile and any cached build artefacts linked to it.",
      confirmLabel: "Delete profile",
      onConfirm: async () => performDeleteSetupProfile(safeName),
    });
  }

  function renderSetupStatus(payload) {
    const data = payload || {};
    setupStatusCache = data;
    const blockers = Array.isArray(data.blockers) ? data.blockers : [];
    const warnings = Array.isArray(data.warnings) ? data.warnings : [];
    const nextSteps = Array.isArray(data.next_steps) ? data.next_steps : [];
    const wheelFiles = Array.isArray(data.wheel_files) ? data.wheel_files : [];
    const profileNames = Array.isArray(data.profile_names) ? data.profile_names : [];
    const ready = !!data.ready_for_example_5;
    const targetProfile = String(data.target_profile || "demo_formatsize_profile");
    const targetWheel = String(data.target_wheel || "pjr_demo_formatsize-0.1.0-py3-none-any.whl");
    const targetSummary = data.target_profile_summary || {};
    const readyState = String(data.ready_state || "not_ready");
    const buildAvailable = !!data.build_available;
    const rebuildAvailable = !!data.rebuild_available;
    const buildRecommended = !!data.build_recommended;
    const targetProfileStatus = String(data.target_profile_status || (data.profile_present ? (data.profile_built ? "ready" : "not_built") : "missing"));
    const targetProfileLastError = String(data.target_profile_last_error || "");
    const restartRequired = !!data.restart_required;
    const restartGuidance = String(data.restart_guidance || "");
    const configSnippet = String(data.config_snippet || "");
    const settingsSummary = [
      `Mode: ${String(data.dependency_mode || "per_job")}`,
      `Requirements: ${setupBadgeText(!!data.install_requirements_enabled)}`,
      `Profiles: ${setupBadgeText(!!data.package_profiles_enabled)}`,
    ].join(" • ");
    const wheelsDir = String(((data.paths || {}).wheel_uploads_dir) || "/config/wheel_uploads");
    const profilesDir = String(((data.paths || {}).profiles_dir) || "/config/package_profiles");

    if (els.setup_status_banner) {
      els.setup_status_banner.classList.remove("ok", "warn", "err");
      if (readyState === "ready") {
        els.setup_status_banner.classList.add("ok");
        els.setup_status_banner.textContent = "Example 5 is ready. The target wheel, profile, and add-on settings are aligned.";
      } else if (readyState === "build_recommended") {
        els.setup_status_banner.classList.add("warn");
        els.setup_status_banner.textContent = `Target files and settings are aligned. Build ${targetProfile} now for a cleaner example 5 run, or let example 5 build it on first use.`;
      } else if (readyState === "build_failed") {
        els.setup_status_banner.classList.add("err");
        els.setup_status_banner.textContent = targetProfileLastError
          ? `The last ${targetProfile} build failed: ${targetProfileLastError}`
          : `The last ${targetProfile} build failed. Rebuild it and inspect the diagnostics bundle if needed.`;
      } else if (readyState === "restart_required") {
        els.setup_status_banner.classList.add("warn");
        els.setup_status_banner.textContent = restartGuidance || "Save the add-on config, restart the add-on, then refresh Setup.";
      } else if (blockers.length) {
        els.setup_status_banner.classList.add("warn");
        els.setup_status_banner.textContent = blockers[0];
      } else {
        els.setup_status_banner.textContent = "Setup information loaded.";
      }
    }
    if (els.setup_target_summary) {
      els.setup_target_summary.textContent = `Target profile: ${targetProfile} • Target wheel: ${targetWheel}`;
    }
    if (els.setup_settings_summary) {
      els.setup_settings_summary.textContent = settingsSummary;
    }
    if (els.setup_wheels_summary) {
      const wheelStatus = wheelFiles.length ? `${wheelFiles.length} wheel uploads found` : "No wheel uploads found yet";
      els.setup_wheels_summary.textContent = `${wheelStatus} • Upload location: ${wheelsDir}`;
    }
    if (els.setup_profiles_summary) {
      const readyCount = Number(((data.inventory || {}).ready_count) || 0);
      const profileStatus = profileNames.length ? `${profileNames.length} profiles found, ${readyCount} ready` : "No package profiles found yet";
      els.setup_profiles_summary.textContent = `${profileStatus} • Profile location: ${profilesDir}`;
    }
    if (els.setup_readiness_summary) {
      if (readyState === "ready") {
        els.setup_readiness_summary.textContent = "Ready to run example 5.";
      } else if (readyState === "build_recommended") {
        els.setup_readiness_summary.textContent = `Build ${targetProfile} now for a cleaner first run.`;
      } else if (readyState === "build_failed") {
        els.setup_readiness_summary.textContent = `${targetProfile} needs a rebuild before you rely on it.`;
      } else if (readyState === "restart_required") {
        els.setup_readiness_summary.textContent = "Restart required after the add-on config change.";
      } else if (blockers.length) {
        els.setup_readiness_summary.textContent = `${blockers.length} blocker${blockers.length === 1 ? "" : "s"} found.`;
      } else if (warnings.length) {
        els.setup_readiness_summary.textContent = `${warnings.length} warning${warnings.length === 1 ? "" : "s"} found.`;
      } else {
        els.setup_readiness_summary.textContent = "No blockers found.";
      }
    }
    if (els.setup_build_summary) {
      if (!data.profile_present) {
        els.setup_build_summary.textContent = `Upload ${targetProfile} before trying to build it.`;
      } else if (readyState === "build_failed") {
        els.setup_build_summary.textContent = targetProfileLastError
          ? `Last build failed: ${targetProfileLastError}`
          : `Last build failed. Try Rebuild for ${targetProfile}.`;
      } else if (data.profile_built) {
        els.setup_build_summary.textContent = `${targetProfile} is already built and ready to attach.`;
      } else if (buildRecommended) {
        els.setup_build_summary.textContent = `${targetProfile} exists but has not been built yet.`;
      } else {
        els.setup_build_summary.textContent = `${targetProfile} status: ${targetProfileStatus}.`;
      }
    }
    if (els.setup_config_snippet) {
      els.setup_config_snippet.value = configSnippet;
    }
    if (els.setup_restart_guidance) {
      els.setup_restart_guidance.textContent = restartGuidance || "Refresh Setup after the next change to confirm the current state.";
    }
    if (els.setup_build_target_profile) {
      els.setup_build_target_profile.disabled = !buildAvailable;
      els.setup_build_target_profile.textContent = data.profile_built ? "Refresh build" : "Build target profile";
    }
    if (els.setup_rebuild_target_profile) {
      els.setup_rebuild_target_profile.disabled = !rebuildAvailable;
    }
    if (els.setup_copy_config_snippet) {
      els.setup_copy_config_snippet.disabled = !configSnippet;
    }

    renderSetupSectionList(els.setup_settings_list, [
      createSetupRow("Install requirements.txt automatically", setupBadgeText(!!data.install_requirements_enabled), null),
      createSetupRow("Dependency handling mode", String(data.dependency_mode || "per_job"), null),
      createSetupRow("Package profiles", setupBadgeText(!!data.package_profiles_enabled), null),
      createSetupRow("Default package profile", String(data.default_profile || "Not set"), !!data.default_profile_exists ? "Found" : "Missing"),
      createSetupRow("Public wheelhouse", setupBadgeText(!!data.package_allow_public_wheelhouse), null),
      createSetupRow("Offline prefer local", setupBadgeText(!!data.package_offline_prefer_local), null),
    ], "No setup settings available.");

    const wheelRows = [
      createSetupRow(
        "Target wheel",
        targetWheel,
        !!data.wheel_present ? "Present" : "Missing"
      ),
      ...wheelFiles.map((name) => createSetupManagedRow(
        "Uploaded wheel",
        String(name),
        name === targetWheel ? "Target match" : null,
        [createSetupActionButton("Delete", "setup-delete-wheel", "data-filename", name)]
      )),
    ];
    renderSetupSectionList(els.setup_wheels_list, wheelRows, "No uploaded wheel files were found.");

    const targetProfileButtons = [];
    if (buildAvailable) targetProfileButtons.push(createSetupActionButton(data.profile_built ? "Refresh build" : "Build", "setup-build-target-profile"));
    if (rebuildAvailable) targetProfileButtons.push(createSetupActionButton("Rebuild", "setup-rebuild-target-profile"));
    const profileRows = [
      createSetupManagedRow(
        "Target profile",
        targetProfile,
        !!data.profile_present ? (data.profile_built ? "Ready" : "Needs build") : "Missing",
        targetProfileButtons
      ),
      ...profileNames.map((name) => {
        let meta = null;
        if (name === targetProfile) meta = !!data.profile_built ? "Target ready" : `Target (${targetProfileStatus})`;
        return createSetupManagedRow(
          "Discovered profile",
          String(name),
          meta,
          [createSetupActionButton("Delete", "setup-delete-profile", "data-profile", name)]
        );
      }),
    ];
    if (targetSummary && typeof targetSummary === "object" && Object.keys(targetSummary).length) {
      profileRows.splice(1, 0, createSetupRow(
        "Target profile source",
        String(targetSummary.requirements_kind || targetSummary.requirements_path || "requirements.txt"),
        String(targetSummary.status || "unknown")
      ));
    }
    renderSetupSectionList(els.setup_profiles_list, profileRows, "No package profiles were found.");

    renderSetupTextList(els.setup_blockers_list, "Blockers", blockers, "No blockers found.");
    renderSetupTextList(els.setup_warnings_list, "Warnings", warnings, "No warnings.");
    renderSetupTextList(els.setup_next_steps_list, "Next steps", nextSteps, "No next steps available.");
    updateSetupPickerSummary("wheel");
    updateSetupPickerSummary("profile");
  }

  async function refreshSetupStatus() {
    const payload = await api("setup/status.json");
    renderSetupStatus(payload || {});
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
