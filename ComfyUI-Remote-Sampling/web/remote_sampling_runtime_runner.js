import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

const PANEL_ID = "remote-sampling-runtime-runner";

window.__remoteSamplingRuntimeRunnerVersion = "20260704-runtime-v1";

function ensureStyle() {
  if (document.getElementById(`${PANEL_ID}-style`)) return;
  const style = document.createElement("style");
  style.id = `${PANEL_ID}-style`;
  style.textContent = `
    #${PANEL_ID} {
      position: fixed;
      right: 18px;
      bottom: 18px;
      z-index: 9999;
      width: 360px;
      max-height: 72vh;
      overflow: hidden;
      border: 1px solid #2d3748;
      border-radius: 8px;
      background: #111722;
      color: #d7dde8;
      font: 12px Arial, sans-serif;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.38);
    }
    #${PANEL_ID}.remote-sampling-collapsed {
      width: auto;
    }
    #${PANEL_ID} .rs-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 12px;
      border-bottom: 1px solid #243044;
      background: #151d2a;
    }
    #${PANEL_ID} .rs-title {
      font-weight: 700;
      color: #f8fafc;
    }
    #${PANEL_ID} .rs-actions {
      display: flex;
      gap: 8px;
    }
    #${PANEL_ID} button {
      border: 1px solid #38bdf8;
      border-radius: 6px;
      background: #0f2333;
      color: #8bd3ff;
      font-weight: 700;
      padding: 5px 9px;
      cursor: pointer;
    }
    #${PANEL_ID} button:disabled {
      border-color: #475569;
      color: #64748b;
      cursor: wait;
    }
    #${PANEL_ID} .rs-body {
      padding: 10px 12px 12px;
      max-height: calc(72vh - 46px);
      overflow: auto;
    }
    #${PANEL_ID}.remote-sampling-collapsed .rs-body,
    #${PANEL_ID}.remote-sampling-collapsed .rs-run {
      display: none;
    }
    #${PANEL_ID} .rs-message {
      color: #aeb8c8;
      line-height: 1.35;
      white-space: pre-wrap;
    }
    #${PANEL_ID} .rs-ok {
      color: #8ef0ad;
    }
    #${PANEL_ID} .rs-warn {
      color: #ffd28a;
    }
    #${PANEL_ID} .rs-error {
      color: #fca5a5;
    }
    #${PANEL_ID} pre {
      white-space: pre-wrap;
      word-break: break-word;
      margin: 8px 0 0;
      padding: 8px;
      border-radius: 6px;
      background: #0b1019;
      color: #d7dde8;
      max-height: 260px;
      overflow: auto;
    }
  `;
  document.head.appendChild(style);
}

function createPanel() {
  ensureStyle();
  let panel = document.getElementById(PANEL_ID);
  if (panel) return panel;
  panel = document.createElement("div");
  panel.id = PANEL_ID;
  panel.innerHTML = `
    <div class="rs-header">
      <div class="rs-title">Remote Sampling</div>
      <div class="rs-actions">
        <button class="rs-run" type="button">Run Current Workflow</button>
        <button class="rs-toggle" type="button">Hide</button>
      </div>
    </div>
    <div class="rs-body">
      <div class="rs-message">Ready. Uses the current graph, converts it at runtime, audits it, then queues the converted prompt.</div>
    </div>
  `;
  document.body.appendChild(panel);
  panel.querySelector(".rs-toggle").addEventListener("click", () => {
    panel.classList.toggle("remote-sampling-collapsed");
    panel.querySelector(".rs-toggle").textContent = panel.classList.contains("remote-sampling-collapsed") ? "Show" : "Hide";
  });
  panel.querySelector(".rs-run").addEventListener("click", () => runCurrentWorkflow(panel));
  return panel;
}

function setMessage(panel, html, className = "") {
  const body = panel.querySelector(".rs-body");
  body.innerHTML = `<div class="rs-message ${className}">${html}</div>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
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

async function getGraphPrompt() {
  if (typeof app.graphToPrompt !== "function") {
    throw new Error("ComfyUI frontend does not expose app.graphToPrompt(); cannot build API prompt from current graph.");
  }
  const result = await app.graphToPrompt();
  const prompt = result?.output || result?.prompt || result;
  const workflow = result?.workflow || app.graph?.serialize?.();
  if (!prompt || typeof prompt !== "object") {
    throw new Error("Current graph did not produce a ComfyUI API prompt.");
  }
  return { prompt, workflow };
}

async function queuePrompt(prompt) {
  const payload = {
    prompt,
    client_id: api.clientId || crypto.randomUUID(),
  };
  return postJson("/prompt", payload);
}

function summarizeConversion(result) {
  const lines = [];
  lines.push(`run_id: ${result.run_id}`);
  lines.push(`run_dir: ${result.run_dir}`);
  lines.push(`source_prompt_sha256: ${result.source_prompt_sha256}`);
  lines.push(`converted_prompt_sha256: ${result.converted_prompt_sha256}`);
  lines.push("");
  for (const profile of result.profile_snapshots || []) {
    lines.push(`node ${profile.node}`);
    lines.push(`  profile: ${profile.snapshot_profile}`);
    lines.push(`  lora_count: ${profile.lora_count}`);
    for (const lora of profile.loras || []) {
      lines.push(`  - ${lora.lora_name} model=${lora.strength_model} clip=${lora.strength_clip}`);
    }
  }
  if (result.warnings?.length) {
    lines.push("");
    lines.push("warnings:");
    for (const warning of result.warnings) lines.push(`  - ${warning}`);
  }
  return lines.join("\n");
}

async function runCurrentWorkflow(panel) {
  const button = panel.querySelector(".rs-run");
  button.disabled = true;
  try {
    setMessage(panel, "Building API prompt from current graph...");
    const { prompt, workflow } = await getGraphPrompt();
    setMessage(panel, "Converting and auditing current workflow...");
    const converted = await postJson("/remote_sampling/convert", {
      prompt,
      workflow,
      options: {
        bypass_local_lora_clip: true,
      },
    });
    if (converted.errors?.length) {
      setMessage(panel, `Conversion blocked:<pre>${escapeHtml(JSON.stringify(converted.errors, null, 2))}</pre>`, "rs-error");
      return;
    }
    setMessage(panel, `Conversion passed. Queueing converted prompt...<pre>${escapeHtml(summarizeConversion(converted))}</pre>`, "rs-ok");
    const queued = await queuePrompt(converted.converted_prompt_object);
    setMessage(
      panel,
      `Queued runtime-converted workflow.<pre>${escapeHtml(summarizeConversion(converted))}\n\nprompt_id: ${queued.prompt_id}</pre>`,
      "rs-ok",
    );
  } catch (error) {
    const detail = error.payload ? JSON.stringify(error.payload, null, 2) : error.stack || error.message;
    setMessage(panel, `Remote runtime run failed:<pre>${escapeHtml(detail)}</pre>`, "rs-error");
  } finally {
    button.disabled = false;
  }
}

app.registerExtension({
  name: "ComfyUI.RemoteSampling.RuntimeRunner",
  async setup() {
    createPanel();
  },
});
