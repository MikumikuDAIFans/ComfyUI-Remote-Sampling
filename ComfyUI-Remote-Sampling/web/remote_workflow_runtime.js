import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

const PANEL_ID = "remote-workflow-runtime-controller";
const CONFIG_KEY = "remoteWorkflowRuntime.config.v1";
const DEFAULT_CONFIG = {
  project_root: "F:\\TieguoDun\\Remote_comfyui",
  python_executable: "C:\\Python314\\python.exe",
  local_comfy_api: "http://127.0.0.1:8188",
  timeout_sec: 2400,
  remote_executor: "company_lab",
  remote_profile: "auto",
};

window.__remoteWorkflowRuntimeControllerVersion = "20260705-workflow-status-events-v1";

function ensureStyle() {
  if (document.getElementById(`${PANEL_ID}-style`)) return;
  const style = document.createElement("style");
  style.id = `${PANEL_ID}-style`;
  style.textContent = `
    #${PANEL_ID} {
      position: fixed;
      right: 18px;
      bottom: 138px;
      z-index: 9998;
      width: 390px;
      max-height: 58vh;
      overflow: hidden;
      border: 1px solid #334155;
      border-radius: 8px;
      background: #101620;
      color: #dbe4ef;
      font: 12px Arial, sans-serif;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.34);
    }
    #${PANEL_ID}.collapsed {
      width: auto;
    }
    #${PANEL_ID} .rwr-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 12px;
      border-bottom: 1px solid #263244;
      background: #172033;
    }
    #${PANEL_ID} .rwr-title {
      color: #f8fafc;
      font-weight: 700;
    }
    #${PANEL_ID} .rwr-actions {
      display: flex;
      gap: 8px;
    }
    #${PANEL_ID} button {
      border: 1px solid #22d3ee;
      border-radius: 6px;
      background: #102535;
      color: #9be8ff;
      cursor: pointer;
      font-weight: 700;
      padding: 5px 9px;
    }
    #${PANEL_ID} button:disabled {
      border-color: #475569;
      color: #64748b;
      cursor: wait;
    }
    #${PANEL_ID}.collapsed .rwr-body,
    #${PANEL_ID}.collapsed .rwr-plan {
      display: none;
    }
    #${PANEL_ID} .rwr-body {
      max-height: calc(58vh - 46px);
      overflow: auto;
      padding: 10px 12px 12px;
    }
    #${PANEL_ID} .rwr-config {
      border: 1px solid #263244;
      border-radius: 8px;
      margin-bottom: 10px;
      padding: 8px;
    }
    #${PANEL_ID} .rwr-config summary {
      color: #f8fafc;
      cursor: pointer;
      font-weight: 700;
    }
    #${PANEL_ID} .rwr-config-grid {
      display: grid;
      gap: 7px;
      margin-top: 8px;
    }
    #${PANEL_ID} .rwr-field {
      display: grid;
      gap: 3px;
    }
    #${PANEL_ID} .rwr-field label {
      color: #94a3b8;
      font-size: 11px;
      font-weight: 700;
    }
    #${PANEL_ID} .rwr-field input,
    #${PANEL_ID} .rwr-field select {
      background: #111827;
      border: 1px solid #334155;
      border-radius: 6px;
      color: #e2e8f0;
      min-width: 0;
      padding: 6px 7px;
    }
    #${PANEL_ID} .rwr-config-actions {
      display: flex;
      gap: 8px;
      margin-top: 8px;
    }
    #${PANEL_ID} .rwr-message {
      color: #aeb8c8;
      line-height: 1.35;
      white-space: pre-wrap;
    }
    #${PANEL_ID} .rwr-ok {
      color: #8ef0ad;
    }
    #${PANEL_ID} .rwr-error {
      color: #fca5a5;
    }
    #${PANEL_ID} pre {
      background: #0b1019;
      border-radius: 6px;
      color: #dbe4ef;
      margin: 8px 0 0;
      max-height: 260px;
      overflow: auto;
      padding: 8px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    #${PANEL_ID} .rwr-status-card {
      background: #0b1220;
      border: 1px solid #263244;
      border-radius: 8px;
      padding: 10px;
    }
    #${PANEL_ID} .rwr-progress-track {
      background: #1e293b;
      border-radius: 999px;
      height: 8px;
      margin: 8px 0 6px;
      overflow: hidden;
    }
    #${PANEL_ID} .rwr-progress-fill {
      background: linear-gradient(90deg, #22d3ee, #38bdf8);
      height: 100%;
      transition: width 180ms ease;
    }
    #${PANEL_ID} .rwr-stage-line {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      color: #cbd5e1;
    }
    #${PANEL_ID} .rwr-stage {
      color: #f8fafc;
      font-weight: 700;
    }
    #${PANEL_ID} .rwr-events {
      border-top: 1px solid #263244;
      margin-top: 8px;
      padding-top: 8px;
    }
    #${PANEL_ID} .rwr-event {
      color: #94a3b8;
      line-height: 1.3;
      margin-top: 4px;
    }
    #${PANEL_ID} .rwr-event strong {
      color: #dbe4ef;
    }
  `;
  document.head.appendChild(style);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

function loadRuntimeConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem(CONFIG_KEY) || "{}");
    return { ...DEFAULT_CONFIG, ...(saved && typeof saved === "object" ? saved : {}) };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

function saveRuntimeConfig(config) {
  localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
}

function configFromPanel(panel) {
  const field = (name) => panel.querySelector(`[data-rwr-config="${name}"]`);
  const timeout = Number(field("timeout_sec")?.value || DEFAULT_CONFIG.timeout_sec);
  return {
    project_root: field("project_root")?.value?.trim() || DEFAULT_CONFIG.project_root,
    python_executable: field("python_executable")?.value?.trim() || DEFAULT_CONFIG.python_executable,
    local_comfy_api: field("local_comfy_api")?.value?.trim() || DEFAULT_CONFIG.local_comfy_api,
    timeout_sec: Number.isFinite(timeout) && timeout > 0 ? timeout : DEFAULT_CONFIG.timeout_sec,
    remote_executor: field("remote_executor")?.value?.trim() || DEFAULT_CONFIG.remote_executor,
    remote_profile: field("remote_profile")?.value?.trim() || DEFAULT_CONFIG.remote_profile,
  };
}

function runtimePayload(panel, extra = {}) {
  const config = configFromPanel(panel);
  saveRuntimeConfig(config);
  return {
    ...extra,
    project_root: config.project_root,
    local_comfy_api: config.local_comfy_api,
    timeout_sec: config.timeout_sec,
    options: {
      ...(extra.options || {}),
      project_root: config.project_root,
      python_executable: config.python_executable,
      timeout_sec: config.timeout_sec,
      remote_executor: config.remote_executor,
      remote_profile: config.remote_profile,
    },
  };
}

function setMessage(panel, html, className = "") {
  panel.querySelector(".rwr-output").innerHTML = `<div class="rwr-message ${className}">${html}</div>`;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok || data?.ok === false) {
    const message = data?.error?.message || data?.message || `request failed: ${response.status}`;
    const error = new Error(message);
    error.payload = data;
    throw error;
  }
  return data;
}

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  const data = await response.json();
  if (!response.ok || data?.ok === false) {
    const message = data?.error?.message || data?.message || `request failed: ${response.status}`;
    const error = new Error(message);
    error.payload = data;
    throw error;
  }
  return data;
}

async function graphPrompt() {
  if (typeof app.graphToPrompt !== "function") {
    throw new Error("ComfyUI frontend does not expose app.graphToPrompt().");
  }
  const result = await app.graphToPrompt();
  const prompt = result?.output || result?.prompt || result;
  const workflow = result?.workflow || app.graph?.serialize?.();
  if (!prompt || typeof prompt !== "object") {
    throw new Error("Current graph did not produce a ComfyUI API prompt.");
  }
  return { prompt, workflow };
}

function summarizePlan(plan) {
  const lines = [];
  lines.push(`run_id: ${plan.run_id}`);
  lines.push(`run_dir: ${plan.run_dir}`);
  lines.push(`source_prompt_sha256: ${plan.source_prompt_sha256}`);
  lines.push(`workflow_analysis_sha256: ${plan.workflow_analysis_sha256}`);
  lines.push("");
  lines.push(`nodes: ${plan.analysis_summary?.node_count ?? 0}`);
  lines.push(`samplers: ${plan.analysis_summary?.sampler_count ?? 0}`);
  lines.push(`custom node classes: ${plan.analysis_summary?.custom_node_class_count ?? 0}`);
  lines.push(`custom node packages: ${plan.analysis_summary?.custom_node_package_count ?? 0}`);
  lines.push(`model resources: ${plan.analysis_summary?.resource_count ?? 0}`);
  if (plan.analysis?.samplers?.length) {
    lines.push("");
    lines.push("samplers:");
    for (const sampler of plan.analysis.samplers) {
      lines.push(`  - node ${sampler.node_id}: ${sampler.class_type}`);
    }
  }
  if (plan.analysis?.custom_node_classes?.length) {
    lines.push("");
    lines.push("custom node classes:");
    for (const cls of plan.analysis.custom_node_classes) lines.push(`  - ${cls}`);
  }
  if (plan.custom_nodes_plan?.packages?.length) {
    lines.push("");
    lines.push("custom node packages:");
    for (const pkg of plan.custom_nodes_plan.packages) {
      lines.push(`  - ${pkg.package_name}`);
      lines.push(`    remote: ${pkg.remote_path}`);
      lines.push(`    classes: ${(pkg.classes || []).join(", ")}`);
    }
  }
  if (plan.resources_plan?.summary) {
    lines.push("");
    lines.push(
      `resources: total=${plan.resources_plan.summary.total} local_missing=${plan.resources_plan.summary.local_missing} remote_check=${plan.resources_plan.summary.needs_remote_check}`,
    );
  }
  if (plan.remote_execution_plan_object) {
    const remotePlan = plan.remote_execution_plan_object;
    lines.push("");
    lines.push("conversion:");
    lines.push(`  converted nodes: ${(remotePlan.converted_node_ids || []).join(", ")}`);
    lines.push(`  converted prompt sha256: ${remotePlan.converted_prompt_sha256}`);
    lines.push(`  stale policy: ${remotePlan.stale_workflow_policy}`);
    if (remotePlan.profile_snapshots?.length) {
      lines.push("  profile snapshots:");
      for (const profile of remotePlan.profile_snapshots) {
        lines.push(`    - node ${profile.node}: loras=${profile.lora_count ?? 0}`);
        for (const lora of profile.loras || []) {
          lines.push(`      ${lora.lora_name} model=${lora.strength_model} clip=${lora.strength_clip}`);
        }
      }
    }
  }
  if (plan.warnings?.length) {
    lines.push("");
    lines.push("warnings:");
    for (const warning of plan.warnings) lines.push(`  - ${warning}`);
  }
  return lines.join("\n");
}

function renderRuntimeStatus(panel, statusPayload, footerHtml = "") {
  const status = statusPayload?.status || {};
  const manifest = statusPayload?.manifest || {};
  const events = statusPayload?.events || [];
  const percent = Math.max(0, Math.min(100, Number(status.overall_percent ?? 0)));
  const recentEvents = events.slice(-5).reverse();
  const eventHtml = recentEvents.length
    ? recentEvents
        .map((event) => {
          const label = `${event.stage || "stage"}/${event.event || "event"}`;
          return `<div class="rwr-event"><strong>${escapeHtml(label)}</strong> ${escapeHtml(event.message || "")}</div>`;
        })
        .join("")
    : `<div class="rwr-event">Waiting for workflow runtime events...</div>`;
  panel.querySelector(".rwr-output").innerHTML = `
    <div class="rwr-status-card">
      <div class="rwr-stage-line">
        <span class="rwr-stage">${escapeHtml(status.stage || manifest.stage || "preparing")}</span>
        <span>${percent.toFixed(0)}%</span>
      </div>
      <div class="rwr-progress-track"><div class="rwr-progress-fill" style="width: ${percent}%"></div></div>
      <div>${escapeHtml(status.message || "Preparing workflow runtime...")}</div>
      <div class="rwr-events">${eventHtml}</div>
      ${footerHtml}
    </div>
  `;
}

function findRemoteSamplingReport(historyItem) {
  const outputs = historyItem?.outputs || {};
  for (const output of Object.values(outputs)) {
    for (const text of output?.text || []) {
      if (typeof text === "string" && text.includes("Remote Sampling Report")) return text;
    }
  }
  return "";
}

function reportLineValue(report, label) {
  const line = report.split("\n").find((item) => item.startsWith(`${label}:`));
  return line ? line.slice(label.length + 1).trim() : "";
}

function reportJsonValue(report, label) {
  const value = reportLineValue(report, label);
  if (!value || !value.startsWith("{")) return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function remoteSamplingReportDetails(report) {
  if (!report) return {};
  return {
    job_id: reportLineValue(report, "job_id"),
    total_elapsed_sec: Number(reportLineValue(report, "total_elapsed_sec")) || null,
    upload: reportJsonValue(report, "upload"),
    sampling: reportJsonValue(report, "sampling"),
    download: reportJsonValue(report, "download"),
  };
}

async function postWorkflowClientEvent(converted, stage, message, percent, promptId, details = {}, fatal = false) {
  try {
    return await postJson("/remote_workflow/runtime/client_event", {
      run_id: converted.run_id,
      project_root: converted.project_root,
      stage,
      message,
      overall_percent: percent,
      prompt_id: promptId,
      details,
      fatal,
    });
  } catch (error) {
    console.warn("Remote workflow client_event failed", error);
    return null;
  }
}

function renderQueuedPromptStatus(panel, converted, promptId, state, historyItem = null) {
  const report = findRemoteSamplingReport(historyItem);
  let footer = `<pre>${escapeHtml(`workflow_run_id: ${converted.run_id}\nprompt_id: ${promptId}`)}</pre>`;
  if (report) {
    const sampling = reportLineValue(report, "sampling");
    const upload = reportLineValue(report, "upload");
    const download = reportLineValue(report, "download");
    footer = `<pre>${escapeHtml(
      [
        `workflow_run_id: ${converted.run_id}`,
        `prompt_id: ${promptId}`,
        `job: ${reportLineValue(report, "job_id")}`,
        `total: ${reportLineValue(report, "total_elapsed_sec")} sec`,
        `upload: ${upload}`,
        `sampling: ${sampling}`,
        `download: ${download}`,
      ].join("\n"),
    )}</pre>`;
  }
  renderRuntimeStatus(
    panel,
    {
      status: {
        stage: state.stage,
        message: state.message,
        overall_percent: state.percent,
        fatal: false,
      },
      manifest: converted,
      events: [
        {
          stage: state.stage,
          event: "prompt",
          message: state.message,
          overall_percent: state.percent,
        },
      ],
    },
    footer,
  );
}

async function waitForQueuedPrompt(panel, converted, promptId) {
  await postWorkflowClientEvent(
    converted,
    "queue",
    "Converted prompt submitted to ComfyUI.",
    76,
    promptId,
    { prompt_id: promptId },
  );
  renderQueuedPromptStatus(panel, converted, promptId, {
    stage: "sampling",
    message: "Converted prompt queued. Waiting for remote sampling job progress and completion...",
    percent: 78,
  });
  let samplingEventWritten = false;
  for (let attempt = 0; attempt < 1800; attempt += 1) {
    const history = await getJson(`/history/${encodeURIComponent(promptId)}`);
    const item = history?.[promptId];
    if (item?.status?.completed) {
      const report = findRemoteSamplingReport(item);
      await postWorkflowClientEvent(
        converted,
        "complete",
        "Guarded remote workflow run completed.",
        100,
        promptId,
        {
          prompt_id: promptId,
          remote_sampling_report: remoteSamplingReportDetails(report),
        },
      );
      renderQueuedPromptStatus(
        panel,
        converted,
        promptId,
        {
          stage: "complete",
          message: "Guarded remote workflow run completed.",
          percent: 100,
        },
        item,
      );
      return item;
    }
    const messages = item?.status?.messages || [];
    if (messages.some((message) => message?.[0] === "execution_error")) {
      await postWorkflowClientEvent(
        converted,
        "failed",
        "Converted prompt execution failed.",
        100,
        promptId,
        { prompt_id: promptId, messages },
        true,
      );
      renderQueuedPromptStatus(
        panel,
        converted,
        promptId,
        {
          stage: "failed",
          message: "Converted prompt execution failed.",
          percent: 100,
        },
        item,
      );
      throw new Error("Converted prompt execution failed.");
    }
    if (attempt % 3 === 0) {
      if (!samplingEventWritten) {
        await postWorkflowClientEvent(
          converted,
          "sampling",
          "Converted prompt is running in ComfyUI.",
          84,
          promptId,
          { prompt_id: promptId },
        );
        samplingEventWritten = true;
      }
      renderQueuedPromptStatus(panel, converted, promptId, {
        stage: "sampling",
        message: "Converted prompt is running in ComfyUI. Node-level report will be summarized here when complete.",
        percent: 84,
      });
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("Timed out waiting for queued guarded workflow prompt.");
}

function runStatusUrl(runId, projectRoot, tail = 20) {
  const params = new URLSearchParams({ run_id: runId, tail: String(tail) });
  if (projectRoot) params.set("project_root", projectRoot);
  return `/remote_workflow/runtime/run_status?${params.toString()}`;
}

function startStatusPolling(panel, runId, projectRoot) {
  let stopped = false;
  const poll = async () => {
    if (stopped) return;
    try {
      const status = await getJson(runStatusUrl(runId, projectRoot, 20));
      renderRuntimeStatus(panel, status);
    } catch (error) {
      if (!stopped) {
        const detail = error.payload ? JSON.stringify(error.payload, null, 2) : error.message;
        setMessage(panel, `Runtime status poll failed:<pre>${escapeHtml(detail)}</pre>`, "rwr-error");
      }
    }
  };
  poll();
  const timer = setInterval(poll, 1000);
  return () => {
    stopped = true;
    clearInterval(timer);
  };
}

async function waitForBackendWorkflowRun(panel, runId, projectRoot) {
  for (let attempt = 0; attempt < 2400; attempt += 1) {
    const status = await getJson(runStatusUrl(runId, projectRoot, 20));
    renderRuntimeStatus(panel, status);
    const stage = status?.status?.stage;
    if (stage === "complete") return status;
    if (stage === "failed") {
      const message = status?.status?.message || "Backend workflow runtime failed.";
      const error = new Error(message);
      error.payload = status;
      throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("Timed out waiting for backend workflow runtime watcher.");
}

async function currentWorkflowRequest(panel, endpoint, buttonSelector, workingMessage, doneMessage) {
  const button = panel.querySelector(buttonSelector);
  button.disabled = true;
  try {
    setMessage(panel, "Building API prompt from current graph...");
    const { prompt, workflow } = await graphPrompt();
    setMessage(panel, workingMessage);
    const plan = await postJson(endpoint, runtimePayload(panel, { prompt, workflow }));
    setMessage(panel, `${doneMessage}<pre>${escapeHtml(summarizePlan(plan))}</pre>`, "rwr-ok");
  } catch (error) {
    const detail = error.payload ? JSON.stringify(error.payload, null, 2) : error.stack || error.message;
    setMessage(panel, `Workflow runtime request failed:<pre>${escapeHtml(detail)}</pre>`, "rwr-error");
  } finally {
    button.disabled = false;
  }
}

async function planCurrentWorkflow(panel) {
  return currentWorkflowRequest(
    panel,
    "/remote_workflow/runtime/plan",
    ".rwr-plan",
    "Generating workflow-level remote runtime plan...",
    "Workflow runtime plan generated.",
  );
}

async function convertCurrentWorkflow(panel) {
  return currentWorkflowRequest(
    panel,
    "/remote_workflow/runtime/convert",
    ".rwr-convert",
    "Generating workflow-level conversion bundle...",
    "Workflow runtime conversion generated without queue submission.",
  );
}

async function runCurrentWorkflow(panel) {
  const button = panel.querySelector(".rwr-run");
  button.disabled = true;
  let stopPolling = null;
  try {
    setMessage(panel, "Building API prompt from current graph...");
    const { prompt, workflow } = await graphPrompt();
    const config = configFromPanel(panel);
    saveRuntimeConfig(config);
    setMessage(panel, "Creating workflow runtime plan...");
    const plan = await postJson("/remote_workflow/runtime/plan", runtimePayload(panel, { prompt, workflow }));
    stopPolling = startStatusPolling(panel, plan.run_id, config.project_root);
    const converted = await postJson(
      "/remote_workflow/runtime/run",
      runtimePayload(panel, { run_id: plan.run_id, prompt, workflow }),
    );
    if (!converted.converted_prompt_object) {
      throw new Error("Conversion did not return converted_prompt_object.");
    }
    renderRuntimeStatus(
      panel,
      { status: converted.status, manifest: converted, events: [] },
      `<pre>${escapeHtml(summarizePlan(converted))}</pre>`,
    );
    await postJson("/remote_workflow/runtime/queue_and_watch", runtimePayload(panel, {
      run_id: converted.run_id,
    }));
    await waitForBackendWorkflowRun(panel, converted.run_id, config.project_root);
  } catch (error) {
    if (stopPolling) stopPolling();
    const detail = error.payload ? JSON.stringify(error.payload, null, 2) : error.stack || error.message;
    setMessage(panel, `Guarded workflow run failed:<pre>${escapeHtml(detail)}</pre>`, "rwr-error");
  } finally {
    if (stopPolling) stopPolling();
    button.disabled = false;
  }
}

function createPanel() {
  ensureStyle();
  let panel = document.getElementById(PANEL_ID);
  if (panel) return panel;
  const config = loadRuntimeConfig();
  panel = document.createElement("div");
  panel.id = PANEL_ID;
  panel.innerHTML = `
    <div class="rwr-header">
      <div class="rwr-title">Remote Workflow Runtime</div>
      <div class="rwr-actions">
        <button class="rwr-plan" type="button">Plan Current Workflow</button>
        <button class="rwr-convert" type="button">Convert</button>
        <button class="rwr-run" type="button">Run Guarded</button>
        <button class="rwr-toggle" type="button">Hide</button>
      </div>
    </div>
    <div class="rwr-body">
      <details class="rwr-config">
        <summary>Runtime Config</summary>
        <div class="rwr-config-grid">
          <div class="rwr-field">
            <label>project_root</label>
            <input data-rwr-config="project_root" value="${escapeAttr(config.project_root)}" spellcheck="false" />
          </div>
          <div class="rwr-field">
            <label>python_executable</label>
            <input data-rwr-config="python_executable" value="${escapeAttr(config.python_executable)}" spellcheck="false" />
          </div>
          <div class="rwr-field">
            <label>local_comfy_api</label>
            <input data-rwr-config="local_comfy_api" value="${escapeAttr(config.local_comfy_api)}" spellcheck="false" />
          </div>
          <div class="rwr-field">
            <label>timeout_sec</label>
            <input data-rwr-config="timeout_sec" type="number" min="30" step="30" value="${escapeAttr(config.timeout_sec)}" />
          </div>
          <div class="rwr-field">
            <label>remote_executor</label>
            <select data-rwr-config="remote_executor">
              <option value="company_lab"${config.remote_executor === "company_lab" ? " selected" : ""}>company_lab</option>
              <option value="ssh"${config.remote_executor === "ssh" ? " selected" : ""}>ssh</option>
            </select>
          </div>
          <div class="rwr-field">
            <label>remote_profile</label>
            <input data-rwr-config="remote_profile" value="${escapeAttr(config.remote_profile)}" spellcheck="false" />
          </div>
        </div>
        <div class="rwr-config-actions">
          <button class="rwr-save-config" type="button">Save</button>
          <button class="rwr-reset-config" type="button">Reset</button>
        </div>
      </details>
      <div class="rwr-output">
        <div class="rwr-message">Ready. Planning creates a workflow-level bundle without sampling or latent upload.</div>
      </div>
    </div>
  `;
  document.body.appendChild(panel);
  panel.querySelector(".rwr-toggle").addEventListener("click", () => {
    panel.classList.toggle("collapsed");
    panel.querySelector(".rwr-toggle").textContent = panel.classList.contains("collapsed") ? "Show" : "Hide";
  });
  panel.querySelector(".rwr-save-config").addEventListener("click", () => {
    saveRuntimeConfig(configFromPanel(panel));
    setMessage(panel, "Runtime config saved.", "rwr-ok");
  });
  panel.querySelector(".rwr-reset-config").addEventListener("click", () => {
    localStorage.removeItem(CONFIG_KEY);
    const defaults = loadRuntimeConfig();
    for (const [key, value] of Object.entries(defaults)) {
      const input = panel.querySelector(`[data-rwr-config="${key}"]`);
      if (input) input.value = value;
    }
    setMessage(panel, "Runtime config reset.", "rwr-ok");
  });
  panel.querySelector(".rwr-plan").addEventListener("click", () => planCurrentWorkflow(panel));
  panel.querySelector(".rwr-convert").addEventListener("click", () => convertCurrentWorkflow(panel));
  panel.querySelector(".rwr-run").addEventListener("click", () => runCurrentWorkflow(panel));
  return panel;
}

app.registerExtension({
  name: "ComfyUI.RemoteWorkflowRuntime.Controller",
  async setup() {
    createPanel();
  },
});
