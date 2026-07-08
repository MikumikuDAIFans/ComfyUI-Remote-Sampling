import { app } from "/scripts/app.js";

const PANEL_ID = "remote-workflow-runtime-controller";
const CONFIG_KEY = "remoteWorkflowRuntime.config.v1";
const POSITION_KEY = "remoteWorkflowRuntime.position.v1";
const DEFAULT_CONFIG = {
  project_root: "F:\\TieguoDun\\Remote_comfyui",
  python_executable: "C:\\Python314\\python.exe",
  local_comfy_api: "http://127.0.0.1:8188",
  timeout_sec: 2400,
  remote_executor: "company_lab",
  remote_profile: "auto",
};

window.__remoteWorkflowRuntimeControllerVersion = "20260706-convert-canvas-v1";

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
      cursor: move;
      user-select: none;
    }
    #${PANEL_ID} .rwr-title {
      color: #f8fafc;
      font-weight: 700;
    }
    #${PANEL_ID} .rwr-actions {
      display: flex;
      gap: 8px;
      cursor: default;
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
    #${PANEL_ID} .rwr-diagnostics {
      border-top: 1px solid #263244;
      margin-top: 10px;
      padding-top: 10px;
    }
    #${PANEL_ID} .rwr-diagnostics-header {
      align-items: center;
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
    }
    #${PANEL_ID} .rwr-diagnostics-title {
      color: #f8fafc;
      font-weight: 700;
    }
    #${PANEL_ID} .rwr-run-list {
      display: grid;
      gap: 7px;
    }
    #${PANEL_ID} .rwr-run-item {
      background: #0b1220;
      border: 1px solid #263244;
      border-radius: 8px;
      display: grid;
      gap: 5px;
      padding: 8px;
    }
    #${PANEL_ID} .rwr-run-top,
    #${PANEL_ID} .rwr-run-actions {
      align-items: center;
      display: flex;
      gap: 6px;
      justify-content: space-between;
      min-width: 0;
    }
    #${PANEL_ID} .rwr-run-id {
      color: #dbe4ef;
      font-family: Consolas, monospace;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    #${PANEL_ID} .rwr-run-stage {
      border: 1px solid #334155;
      border-radius: 999px;
      color: #9be8ff;
      flex: 0 0 auto;
      font-weight: 700;
      padding: 2px 7px;
    }
    #${PANEL_ID} .rwr-run-stage.failed,
    #${PANEL_ID} .rwr-run-stage.error {
      border-color: #ef4444;
      color: #fca5a5;
    }
    #${PANEL_ID} .rwr-run-stage.complete {
      border-color: #22c55e;
      color: #8ef0ad;
    }
    #${PANEL_ID} .rwr-run-message {
      color: #94a3b8;
      line-height: 1.25;
      max-height: 3.8em;
      overflow: hidden;
    }
    #${PANEL_ID} .rwr-mini-button {
      font-size: 11px;
      padding: 3px 7px;
      white-space: nowrap;
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

function clampPanelPosition(left, top, panel) {
  const margin = 8;
  const rect = panel.getBoundingClientRect();
  const maxLeft = Math.max(margin, window.innerWidth - rect.width - margin);
  const maxTop = Math.max(margin, window.innerHeight - rect.height - margin);
  return {
    left: Math.min(Math.max(margin, left), maxLeft),
    top: Math.min(Math.max(margin, top), maxTop),
  };
}

function loadPanelPosition() {
  try {
    const saved = JSON.parse(localStorage.getItem(POSITION_KEY) || "null");
    if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) {
      return saved;
    }
  } catch {
    return null;
  }
  return null;
}

function savePanelPosition(panel) {
  const rect = panel.getBoundingClientRect();
  localStorage.setItem(POSITION_KEY, JSON.stringify({ left: Math.round(rect.left), top: Math.round(rect.top) }));
}

function applyPanelPosition(panel) {
  const saved = loadPanelPosition();
  if (!saved) return;
  const next = clampPanelPosition(saved.left, saved.top, panel);
  panel.style.left = `${next.left}px`;
  panel.style.top = `${next.top}px`;
  panel.style.right = "auto";
  panel.style.bottom = "auto";
}

function enablePanelDrag(panel) {
  const header = panel.querySelector(".rwr-header");
  if (!header) return;
  let drag = null;
  header.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest("button")) return;
    const rect = panel.getBoundingClientRect();
    drag = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
    };
    panel.style.left = `${rect.left}px`;
    panel.style.top = `${rect.top}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    header.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  header.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const next = clampPanelPosition(event.clientX - drag.offsetX, event.clientY - drag.offsetY, panel);
    panel.style.left = `${next.left}px`;
    panel.style.top = `${next.top}px`;
  });
  const finish = (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag = null;
    savePanelPosition(panel);
  };
  header.addEventListener("pointerup", finish);
  header.addEventListener("pointercancel", finish);
  window.addEventListener("resize", () => {
    const rect = panel.getBoundingClientRect();
    const next = clampPanelPosition(rect.left, rect.top, panel);
    panel.style.left = `${next.left}px`;
    panel.style.top = `${next.top}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
    savePanelPosition(panel);
  });
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

async function copyText(panel, text, label = "value") {
  if (!text) {
    setMessage(panel, `Nothing to copy for ${escapeHtml(label)}.`, "rwr-error");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    setMessage(panel, `Copied ${escapeHtml(label)}.`, "rwr-ok");
  } catch (error) {
    setMessage(panel, `Copy failed:<pre>${escapeHtml(error.message || String(error))}</pre>`, "rwr-error");
  }
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

function findInputSlot(node, name) {
  return (node.inputs || []).findIndex((input) => input?.name === name);
}

function setWidgetValue(node, name, value) {
  const widget = (node.widgets || []).find((item) => item?.name === name);
  if (!widget) return false;
  widget.value = value;
  if (typeof widget.callback === "function") {
    widget.callback(value, app.canvas, node, app.canvas?.graph_mouse, {});
  }
  return true;
}

function convertedSamplerInputs(convertedPrompt, nodeId) {
  const convertedNode = convertedPrompt?.[String(nodeId)];
  if (!convertedNode || convertedNode.class_type !== "Remote_Sampling_local") return null;
  return convertedNode.inputs || {};
}

function copyRemoteSamplerWidgets(node, inputs) {
  const widgetNames = [
    "seed",
    "steps",
    "cfg",
    "sampler_name",
    "scheduler",
    "denoise",
    "remote_profile",
    "project_root",
    "python_executable",
    "timeout_sec",
    "sampler_id",
    "allow_fixed_profile",
  ];
  for (const name of widgetNames) {
    const value = inputs[name];
    if (!Array.isArray(value) && value !== undefined) {
      setWidgetValue(node, name, value);
    }
  }
}

function replaceSamplerNodeOnCanvas(oldNode, convertedPrompt) {
  const inputs = convertedSamplerInputs(convertedPrompt, oldNode.id);
  if (!inputs) {
    throw new Error(`Converted prompt does not contain Remote_Sampling_local for node ${oldNode.id}.`);
  }
  const graph = app.graph;
  const oldId = oldNode.id;
  const oldPos = [oldNode.pos[0], oldNode.pos[1]];
  const oldSize = oldNode.size ? [oldNode.size[0], Math.max(oldNode.size[1], 330)] : undefined;
  const oldTitle = oldNode.title && oldNode.title !== oldNode.type ? oldNode.title : "Remote Sampling Local";
  const oldInputLinks = {};
  for (const input of oldNode.inputs || []) {
    if (input?.link != null) oldInputLinks[input.name] = graph.links?.[input.link];
  }
  const oldOutputLinks = [];
  for (const output of oldNode.outputs || []) {
    for (const linkId of output?.links || []) {
      const link = graph.links?.[linkId];
      if (link) oldOutputLinks.push(link);
    }
  }

  graph.remove(oldNode);

  const liteGraph = globalThis.LiteGraph;
  if (!liteGraph?.createNode) {
    throw new Error("ComfyUI frontend does not expose LiteGraph.createNode().");
  }
  const remoteNode = liteGraph.createNode("Remote_Sampling_local");
  if (!remoteNode) {
    throw new Error("Could not create Remote_Sampling_local. Reload ComfyUI and confirm the custom node is installed locally.");
  }
  remoteNode.id = oldId;
  remoteNode.pos = oldPos;
  remoteNode.size = oldSize;
  remoteNode.title = oldTitle;
  graph.add(remoteNode);
  copyRemoteSamplerWidgets(remoteNode, inputs);

  for (const name of ["positive", "negative", "latent_image"]) {
    const link = oldInputLinks[name];
    const targetSlot = findInputSlot(remoteNode, name);
    if (link && targetSlot >= 0) {
      const origin = graph.getNodeById(link.origin_id);
      if (origin) origin.connect(link.origin_slot, remoteNode, targetSlot);
    }
  }

  for (const link of oldOutputLinks) {
    const target = graph.getNodeById(link.target_id);
    if (target) remoteNode.connect(0, target, link.target_slot);
  }
  return remoteNode;
}

function applyConvertedPromptToCanvas(convertedPrompt, convertedNodeIds = []) {
  if (!convertedPrompt || typeof convertedPrompt !== "object") {
    throw new Error("Conversion did not return a converted_prompt_object.");
  }
  const graph = app.graph;
  const targetIds = convertedNodeIds.length
    ? convertedNodeIds.map((id) => String(id))
    : Object.entries(convertedPrompt)
        .filter(([, node]) => node?.class_type === "Remote_Sampling_local")
        .map(([id]) => String(id));
  if (!targetIds.length) {
    throw new Error("Converted prompt contains no Remote_Sampling_local nodes.");
  }

  const replaced = [];
  for (const id of targetIds) {
    const node = graph.getNodeById(Number(id)) || graph.getNodeById(id);
    if (!node) {
      throw new Error(`Current canvas does not contain sampler node ${id}. Reload the original workflow and convert again.`);
    }
    if (node.type === "Remote_Sampling_local") {
      copyRemoteSamplerWidgets(node, convertedSamplerInputs(convertedPrompt, id) || {});
      replaced.push(id);
      continue;
    }
    if (!["KSampler", "KSamplerAdvanced"].includes(node.type)) {
      throw new Error(`Node ${id} is ${node.type}, not a supported KSampler node.`);
    }
    replaceSamplerNodeOnCanvas(node, convertedPrompt);
    replaced.push(id);
  }

  graph.setDirtyCanvas(true, true);
  app.canvas?.setDirty?.(true, true);
  return replaced;
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

function runStatusUrl(runId, projectRoot, tail = 20) {
  const params = new URLSearchParams({ run_id: runId, tail: String(tail) });
  if (projectRoot) params.set("project_root", projectRoot);
  return `/remote_workflow/runtime/run_status?${params.toString()}`;
}

function recentRunsUrl(projectRoot, limit = 8) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (projectRoot) params.set("project_root", projectRoot);
  return `/remote_workflow/runtime/recent?${params.toString()}`;
}

function errorSummaryForRun(run) {
  const error = run?.error;
  if (error && typeof error === "object") {
    return `${error.type || "Error"}: ${error.message || JSON.stringify(error)}`;
  }
  if (run?.fatal || run?.stage === "failed") {
    return run?.message || "Run failed without a structured error message.";
  }
  return "";
}

function renderRecentRuns(panel, payload) {
  const target = panel.querySelector(".rwr-diagnostics");
  if (!target) return;
  const runs = Array.isArray(payload?.runs) ? payload.runs : [];
  const items = runs.length
    ? runs
        .map((run) => {
          const stage = String(run.stage || "unknown");
          const errorSummary = errorSummaryForRun(run);
          const copyPayload = {
            run_id: run.run_id,
            run_dir: run.run_dir,
            stage,
            message: run.message,
            prompt_id: run.prompt_id,
            job_id: run.job_id,
            status: run.workflow_status,
            events: run.workflow_events,
            report: run.workflow_report,
            error: run.error || null,
          };
          return `
            <div class="rwr-run-item">
              <div class="rwr-run-top">
                <span class="rwr-run-id" title="${escapeAttr(run.run_id)}">${escapeHtml(run.run_id)}</span>
                <span class="rwr-run-stage ${escapeAttr(stage)}">${escapeHtml(stage)}</span>
              </div>
              <div class="rwr-run-message">${escapeHtml(run.message || "No status message.")}</div>
              <div class="rwr-run-actions">
                <button class="rwr-mini-button" type="button" data-copy-text="${escapeAttr(run.run_dir || "")}" data-copy-label="run directory">Run Dir</button>
                <button class="rwr-mini-button" type="button" data-copy-text="${escapeAttr(run.workflow_status || "")}" data-copy-label="status path">Status</button>
                <button class="rwr-mini-button" type="button" data-copy-text="${escapeAttr(run.workflow_report || "")}" data-copy-label="report path">Report</button>
                <button class="rwr-mini-button" type="button" data-copy-text="${escapeAttr(errorSummary)}" data-copy-label="error summary"${errorSummary ? "" : " disabled"}>Error</button>
                <button class="rwr-mini-button" type="button" data-copy-text="${escapeAttr(JSON.stringify(copyPayload, null, 2))}" data-copy-label="run summary">JSON</button>
              </div>
            </div>
          `;
        })
        .join("")
    : `<div class="rwr-event">No workflow runtime runs found.</div>`;
  target.innerHTML = `
    <div class="rwr-diagnostics-header">
      <div class="rwr-diagnostics-title">Recent Runs</div>
      <button class="rwr-refresh-runs rwr-mini-button" type="button">Refresh</button>
    </div>
    <div class="rwr-run-list">${items}</div>
  `;
}

async function refreshRecentRuns(panel) {
  const config = configFromPanel(panel);
  try {
    const payload = await getJson(recentRunsUrl(config.project_root, 8));
    renderRecentRuns(panel, payload);
  } catch (error) {
    const detail = error.payload ? JSON.stringify(error.payload, null, 2) : error.message;
    const target = panel.querySelector(".rwr-diagnostics");
    if (target) {
      target.innerHTML = `<div class="rwr-message rwr-error">Recent runs failed:<pre>${escapeHtml(detail)}</pre></div>`;
    }
  }
}

function startStatusPolling(panel, runId, projectRoot) {
  let stopped = false;
  let lastRecentRefresh = 0;
  const poll = async () => {
    if (stopped) return;
    try {
      const status = await getJson(runStatusUrl(runId, projectRoot, 20));
      renderRuntimeStatus(panel, status);
      const now = Date.now();
      if (now - lastRecentRefresh > 5000) {
        lastRecentRefresh = now;
        refreshRecentRuns(panel);
      }
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
  const button = panel.querySelector(".rwr-plan");
  button.disabled = true;
  let stopPolling = null;
  try {
    setMessage(panel, "Building API prompt from current graph...");
    const { prompt, workflow } = await graphPrompt();
    const config = configFromPanel(panel);
    saveRuntimeConfig(config);
    setMessage(panel, "Checking workflow and aligning remote resources...");
    const plan = await postJson("/remote_workflow/runtime/plan", runtimePayload(panel, { prompt, workflow }));
    stopPolling = startStatusPolling(panel, plan.run_id, config.project_root);
    const ready = await postJson(
      "/remote_workflow/runtime/run",
      runtimePayload(panel, { run_id: plan.run_id, prompt, workflow }),
    );
    renderRuntimeStatus(
      panel,
      { status: ready.status, manifest: ready, events: [] },
      `<pre>${escapeHtml(summarizePlan(ready))}</pre>`,
    );
  } catch (error) {
    const detail = error.payload ? JSON.stringify(error.payload, null, 2) : error.stack || error.message;
    setMessage(panel, `Check and sync failed:<pre>${escapeHtml(detail)}</pre>`, "rwr-error");
  } finally {
    if (stopPolling) stopPolling();
    button.disabled = false;
  }
}

async function convertCurrentWorkflow(panel) {
  const button = panel.querySelector(".rwr-convert");
  button.disabled = true;
  let stopPolling = null;
  try {
    setMessage(panel, "Building API prompt from current graph...");
    const { prompt, workflow } = await graphPrompt();
    const config = configFromPanel(panel);
    saveRuntimeConfig(config);
    setMessage(panel, "Checking remote readiness and preparing canvas conversion...");
    const plan = await postJson("/remote_workflow/runtime/plan", runtimePayload(panel, { prompt, workflow }));
    stopPolling = startStatusPolling(panel, plan.run_id, config.project_root);
    const converted = await postJson(
      "/remote_workflow/runtime/run",
      runtimePayload(panel, { run_id: plan.run_id, prompt, workflow }),
    );
    const remotePlan = converted.remote_execution_plan_object || {};
    const replaced = applyConvertedPromptToCanvas(
      converted.converted_prompt_object,
      remotePlan.converted_node_ids || converted.converted_node_ids || [],
    );
    renderRuntimeStatus(
      panel,
      { status: converted.status, manifest: converted, events: [] },
      `<pre>${escapeHtml(`${summarizePlan(converted)}\n\ncanvas converted nodes: ${replaced.join(", ")}\n\nNext: click ComfyUI's native Queue/Run button to generate.`)}</pre>`,
    );
  } catch (error) {
    const detail = error.payload ? JSON.stringify(error.payload, null, 2) : error.stack || error.message;
    setMessage(panel, `Canvas conversion failed:<pre>${escapeHtml(detail)}</pre>`, "rwr-error");
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
        <button class="rwr-plan" type="button">Check & Sync</button>
        <button class="rwr-convert" type="button">Convert Canvas</button>
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
        <div class="rwr-message">Ready. Check & Sync aligns the remote side. Convert Canvas replaces local KSampler nodes, then use ComfyUI's native Queue/Run button.</div>
      </div>
      <div class="rwr-diagnostics">
        <div class="rwr-diagnostics-header">
          <div class="rwr-diagnostics-title">Recent Runs</div>
          <button class="rwr-refresh-runs rwr-mini-button" type="button">Refresh</button>
        </div>
        <div class="rwr-event">Loading workflow runtime history...</div>
      </div>
    </div>
  `;
  document.body.appendChild(panel);
  applyPanelPosition(panel);
  enablePanelDrag(panel);
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
  panel.addEventListener("click", (event) => {
    const copyButton = event.target.closest("[data-copy-text]");
    if (copyButton) {
      copyText(panel, copyButton.getAttribute("data-copy-text") || "", copyButton.getAttribute("data-copy-label") || "value");
      return;
    }
    if (event.target.closest(".rwr-refresh-runs")) {
      refreshRecentRuns(panel);
    }
  });
  refreshRecentRuns(panel);
  return panel;
}

app.registerExtension({
  name: "ComfyUI.RemoteWorkflowRuntime.Controller",
  async setup() {
    createPanel();
  },
});
