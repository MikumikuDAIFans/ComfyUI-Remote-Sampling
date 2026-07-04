import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

const PANEL_ID = "remote-workflow-runtime-controller";

window.__remoteWorkflowRuntimeControllerVersion = "20260705-guarded-run-v2";

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

function setMessage(panel, html, className = "") {
  panel.querySelector(".rwr-body").innerHTML = `<div class="rwr-message ${className}">${html}</div>`;
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

async function queuePrompt(prompt) {
  return postJson("/prompt", {
    prompt,
    client_id: api.clientId || crypto.randomUUID(),
  });
}

async function currentWorkflowRequest(panel, endpoint, buttonSelector, workingMessage, doneMessage) {
  const button = panel.querySelector(buttonSelector);
  button.disabled = true;
  try {
    setMessage(panel, "Building API prompt from current graph...");
    const { prompt, workflow } = await graphPrompt();
    setMessage(panel, workingMessage);
    const plan = await postJson(endpoint, { prompt, workflow });
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
  try {
    setMessage(panel, "Building API prompt from current graph...");
    const { prompt, workflow } = await graphPrompt();
    setMessage(panel, "Preparing guarded workflow runtime: resources, custom nodes, conversion...");
    const converted = await postJson("/remote_workflow/runtime/run", { prompt, workflow });
    if (!converted.converted_prompt_object) {
      throw new Error("Conversion did not return converted_prompt_object.");
    }
    setMessage(panel, `Conversion passed. Queueing converted prompt...<pre>${escapeHtml(summarizePlan(converted))}</pre>`, "rwr-ok");
    const queued = await queuePrompt(converted.converted_prompt_object);
    setMessage(
      panel,
      `Queued guarded remote workflow run.<pre>${escapeHtml(summarizePlan(converted))}\n\nprompt_id: ${queued.prompt_id}</pre>`,
      "rwr-ok",
    );
  } catch (error) {
    const detail = error.payload ? JSON.stringify(error.payload, null, 2) : error.stack || error.message;
    setMessage(panel, `Guarded workflow run failed:<pre>${escapeHtml(detail)}</pre>`, "rwr-error");
  } finally {
    button.disabled = false;
  }
}

function createPanel() {
  ensureStyle();
  let panel = document.getElementById(PANEL_ID);
  if (panel) return panel;
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
      <div class="rwr-message">Ready. Planning creates a workflow-level bundle without sampling or latent upload.</div>
    </div>
  `;
  document.body.appendChild(panel);
  panel.querySelector(".rwr-toggle").addEventListener("click", () => {
    panel.classList.toggle("collapsed");
    panel.querySelector(".rwr-toggle").textContent = panel.classList.contains("collapsed") ? "Show" : "Hide";
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
