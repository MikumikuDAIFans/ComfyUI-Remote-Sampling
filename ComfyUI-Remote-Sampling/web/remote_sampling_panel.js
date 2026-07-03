import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

const NODE_NAME = "Remote_Sampling_local";
const PANEL_HEIGHT = 194;
const PANEL_MIN_WIDTH = 340;
const PANEL_MARGIN = 10;
const STATUS_POLL_MS = 1000;

const stageLabels = [
  ["preflight", "Preflight"],
  ["upload", "Upload"],
  ["sampling", "Sampling"],
  ["download", "Download"],
];

const panelNodes = new Map();
let activeRemoteNodeId = null;

window.__remoteSamplingPanelVersion = "20260703-refresh-v6";
window.__remoteSamplingPanelStates = window.__remoteSamplingPanelStates || {};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function asNumber(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function formatSeconds(value) {
  const seconds = asNumber(value, 0);
  if (seconds <= 0) return "0.0s";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${rest.toFixed(0)}s`;
}

function formatMB(value) {
  const mb = asNumber(value, 0);
  if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`;
  return `${mb.toFixed(2)} MB`;
}

function formatSpeed(value) {
  const mbps = asNumber(value, 0);
  if (mbps < 0.1) return `${(mbps * 1024).toFixed(1)} KB/s`;
  return `${mbps.toFixed(2)} MB/s`;
}

function roundRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function fillRoundRect(ctx, x, y, width, height, radius, color) {
  ctx.fillStyle = color;
  roundRect(ctx, x, y, width, height, radius);
  ctx.fill();
}

function strokeRoundRect(ctx, x, y, width, height, radius, color, lineWidth = 1) {
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  roundRect(ctx, x, y, width, height, radius);
  ctx.stroke();
}

function drawText(ctx, text, x, y, options = {}) {
  const {
    color = "#d7dde8",
    size = 12,
    weight = "400",
    align = "left",
    baseline = "alphabetic",
    maxWidth = null,
  } = options;
  ctx.fillStyle = color;
  ctx.font = `${weight} ${size}px Arial, sans-serif`;
  ctx.textAlign = align;
  ctx.textBaseline = baseline;
  if (maxWidth) {
    ctx.fillText(String(text ?? ""), x, y, maxWidth);
  } else {
    ctx.fillText(String(text ?? ""), x, y);
  }
}

function drawBar(ctx, x, y, width, height, percent, color) {
  const p = clamp(asNumber(percent, 0), 0, 100);
  fillRoundRect(ctx, x, y, width, height, 4, "#202734");
  if (p > 0) {
    fillRoundRect(ctx, x, y, Math.max(5, width * (p / 100)), height, 4, color);
  }
}

function parseReportLine(line, data) {
  const index = line.indexOf(":");
  if (index === -1) return;
  const key = line.slice(0, index).trim();
  const raw = line.slice(index + 1).trim();
  if (!key) return;
  if (raw.startsWith("{") || raw.startsWith("[")) {
    try {
      data[key] = JSON.parse(raw);
      return;
    } catch (error) {
      data[key] = raw;
      return;
    }
  }
  const numeric = Number(raw);
  data[key] = Number.isFinite(numeric) && raw !== "" ? numeric : raw;
}

function parseReport(text) {
  const data = {};
  for (const line of String(text ?? "").split(/\r?\n/)) {
    parseReportLine(line, data);
  }
  return data;
}

function summarizeStatus(status) {
  if (status.stage === "completed") return "Complete";
  if (status.stage === "failed") return "Failed";
  if (status.stage) return String(status.stage);
  return "Idle";
}

function stagePercent(status, key) {
  if (key === "preflight") {
    if (status.preflight?.ok) return 100;
    return status.stage === "preflight" ? asNumber(status.overall_percent, 8) : 0;
  }
  return asNumber(status[key]?.percent, 0);
}

function makeInitialState() {
  return {
    stage: "idle",
    message: "Waiting for execution",
    overall_percent: 0,
    total_elapsed_sec: 0,
    preflight: null,
    upload: null,
    sampling: null,
    download: null,
    error: null,
    reportText: "",
  };
}

function getWidgetValue(node, name, fallback = "") {
  const widget = (node.widgets || []).find((item) => item.name === name);
  const value = widget?.value;
  if (value == null || value === "") return fallback;
  return String(value);
}

function statusUrlForNode(node) {
  const projectRoot = getWidgetValue(node, "project_root");
  const samplerId = getWidgetValue(node, "sampler_id", "sampler_001");
  if (!projectRoot) return null;
  const params = new URLSearchParams({
    project_root: projectRoot,
    sampler_id: samplerId || "sampler_001",
  });
  return `/remote_sampling/status?${params.toString()}`;
}

function forceWidgetRefresh(node) {
  if (!node?.setSize || !node.size || node.size.length < 2) return;
  const currentWidth = asNumber(node.size[0], PANEL_MIN_WIDTH);
  const currentHeight = asNumber(node.size[1], PANEL_HEIGHT);
  const base = node.__remoteSamplingRefreshBaseSize;
  if (
    !base ||
    Math.abs(currentWidth - base[0]) > 3 ||
    Math.abs(currentHeight - base[1]) > 3
  ) {
    node.__remoteSamplingRefreshBaseSize = [currentWidth, currentHeight];
  }
  const [width, height] = node.__remoteSamplingRefreshBaseSize;
  node.__remoteSamplingRefreshCounter = (node.__remoteSamplingRefreshCounter || 0) + 1;
  const bump = 1 + (node.__remoteSamplingRefreshCounter % 10) / 10;
  node.setSize([width + bump, height + bump]);
}

function requestRedraw(node = null) {
  if (node) {
    forceWidgetRefresh(node);
  }
  app.graph?.setDirtyCanvas(true, true);
  app.canvas?.setDirty?.(true, true);
  requestAnimationFrame(() => app.canvas?.draw?.(true, true));
}

function updateNodeState(node, patch, options = {}) {
  if (!node) return;
  registerPanelNode(node);
  const previous = node.remoteSamplingPanel || makeInitialState();
  const jobChanged = patch.job_id && previous.job_id && patch.job_id !== previous.job_id;
  const base = options.replace || jobChanged ? makeInitialState() : previous;
  const state = {
    ...base,
    ...patch,
  };
  node.remoteSamplingPanel = state;
  if (node.id != null) {
    window.__remoteSamplingPanelStates[String(node.id)] = state;
  }
  node.__remoteSamplingUpdateCount = (node.__remoteSamplingUpdateCount || 0) + 1;
  for (const widget of node.widgets || []) {
    if (widget.name === "remote_sampling_panel") {
      widget.remoteSamplingPanel = state;
      widget.value = state;
    }
  }
  requestRedraw(node);
}

function stopPollingNode(node) {
  if (node?.remoteSamplingPollTimer) {
    clearInterval(node.remoteSamplingPollTimer);
    node.remoteSamplingPollTimer = null;
  }
}

async function pollStatusForNode(node) {
  const url = statusUrlForNode(node);
  if (!url) return;
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    if (!payload?.ok || !payload.status) return;

    const state = {
      ...makeInitialState(),
      ...payload.status,
      job_dir: payload.job_dir,
    };
    if (state.stage === "completed") {
      state.message = state.message || "Remote sampling complete";
      state.overall_percent = 100;
    }
    updateNodesById(node.id, state, { replace: true });
  } catch (error) {
    // Polling is a fallback path; websocket/progress events can still update the panel.
  }
}

function startPollingNode(node) {
  if (!node || node.remoteSamplingPollTimer) return;
  node.remoteSamplingPollTimer = setInterval(() => pollStatusForNode(node), STATUS_POLL_MS);
  pollStatusForNode(node);
}

function registerPanelNode(node) {
  if (!node?.id && node?.id !== 0) return;
  const key = String(node.id);
  if (!panelNodes.has(key)) {
    panelNodes.set(key, new Set());
  }
  panelNodes.get(key).add(node);
}

function unregisterPanelNode(node) {
  if (!node?.id && node?.id !== 0) return;
  stopPollingNode(node);
  const key = String(node.id);
  const nodes = panelNodes.get(key);
  if (!nodes) return;
  nodes.delete(node);
  if (!nodes.size) {
    panelNodes.delete(key);
  }
}

function getGraphNode(nodeId) {
  if (nodeId == null) return null;
  return app.graph?.getNodeById?.(nodeId) || app.graph?.getNodeById?.(String(nodeId)) || null;
}

function getRemoteNodes(nodeId) {
  if (nodeId == null) return [];
  const key = String(nodeId);
  const nodes = [];
  const graphNode = getGraphNode(nodeId);
  if (graphNode) {
    nodes.push(graphNode);
  }
  for (const node of panelNodes.get(key) || []) {
    if (node && !nodes.includes(node)) {
      nodes.push(node);
    }
  }
  return nodes;
}

function updateNodesById(nodeId, patch, options = {}) {
  const nodes = getRemoteNodes(nodeId);
  for (const node of nodes) {
    updateNodeState(node, patch, options);
  }
  return nodes;
}

function stateFromProgressEvent(detail) {
  const eventName = detail.event || detail.stage || "running";
  const state = {
    stage: detail.stage || eventName,
    message: detail.message || progressMessage(eventName),
  };
  if (detail.overall_percent != null) {
    state.overall_percent = clamp(asNumber(detail.overall_percent, 0), 0, 100);
  }
  for (const key of ["preflight", "upload", "sampling", "download", "error"]) {
    if (detail[key] != null) {
      state[key] = detail[key];
    }
  }
  if (detail.job_id != null) {
    state.job_id = detail.job_id;
  }
  if (["preparing", "preflight"].includes(eventName)) {
    state.upload = detail.upload || null;
    state.sampling = detail.sampling || null;
    state.download = detail.download || null;
  }
  if (eventName === "upload") {
    state.sampling = detail.sampling || null;
    state.download = detail.download || null;
  }
  if (["queued", "sampling"].includes(eventName)) {
    state.download = detail.download || null;
  }
  if (eventName === "completed") {
    state.stage = "completed";
    state.message = detail.message || "Remote sampling complete";
    state.overall_percent = 100;
  }
  if (eventName === "failed") {
    state.stage = "failed";
    state.message = detail.message || "Remote sampling failed";
  }
  return state;
}

function progressMessage(eventName) {
  switch (eventName) {
    case "preparing":
      return "Preparing remote sampling job";
    case "preflight":
      return "Checking remote resources";
    case "upload":
      return "Uploading latent package";
    case "queued":
      return "Waiting for remote sampling slot";
    case "sampling":
      return "Remote sampler is running";
    case "download":
      return "Downloading output latent";
    default:
      return "Remote sampling in progress";
  }
}

function getRemoteNode(nodeId) {
  if (nodeId == null) return null;
  return getRemoteNodes(nodeId)[0] || null;
}

function updateNodeSize(node) {
  if (!node) return;
  const nextWidth = Math.max(PANEL_MIN_WIDTH, node.size?.[0] || PANEL_MIN_WIDTH);
  const minHeight = node.computeSize?.([nextWidth, node.size?.[1] || 0])?.[1] || PANEL_HEIGHT;
  node.setSize?.([nextWidth, Math.max(node.size?.[1] || 0, minHeight)]);
}

function createPanelWidget() {
  const widget = {
    name: "remote_sampling_panel",
    type: "remote_sampling_panel",
    serialize: false,
    remoteSamplingPanel: makeInitialState(),
    value: makeInitialState(),
    computeSize(width) {
      return [Math.max(PANEL_MIN_WIDTH, width || PANEL_MIN_WIDTH), PANEL_HEIGHT];
    },
    draw(ctx, node, widgetWidth, widgetY) {
      const panelWidget = (node.widgets || []).find((widget) => widget.name === "remote_sampling_panel");
      const globalState = node.id == null ? null : window.__remoteSamplingPanelStates?.[String(node.id)];
      const state =
        globalState ||
        node.remoteSamplingPanel ||
        panelWidget?.remoteSamplingPanel ||
        panelWidget?.value ||
        this?.remoteSamplingPanel ||
        this?.value ||
        makeInitialState();
      const x = PANEL_MARGIN;
      const y = widgetY + PANEL_MARGIN;
      const width = Math.max(PANEL_MIN_WIDTH - PANEL_MARGIN * 2, widgetWidth - PANEL_MARGIN * 2);
      const height = PANEL_HEIGHT - PANEL_MARGIN * 2;

      fillRoundRect(ctx, x, y, width, height, 8, "#111722");
      strokeRoundRect(ctx, x + 0.5, y + 0.5, width - 1, height - 1, 8, "#2d3748");

      const status = summarizeStatus(state);
      const isFailed = state.stage === "failed" || Boolean(state.error);
      const chipColor = isFailed ? "#ef4444" : state.stage === "completed" ? "#22c55e" : "#38bdf8";
      drawText(ctx, "Remote Sampling", x + 14, y + 24, { size: 13, weight: "700", color: "#f8fafc" });
      fillRoundRect(ctx, x + width - 88, y + 10, 74, 20, 6, `${chipColor}22`);
      strokeRoundRect(ctx, x + width - 88, y + 10, 74, 20, 6, `${chipColor}cc`);
      drawText(ctx, status, x + width - 51, y + 21, { size: 11, weight: "700", color: chipColor, align: "center", baseline: "middle" });

      const overall = clamp(asNumber(state.overall_percent, 0), 0, 100);
      drawBar(ctx, x + 14, y + 40, width - 28, 8, overall, chipColor);
      drawText(ctx, `${overall.toFixed(0)}%`, x + width - 14, y + 60, { size: 11, color: "#aeb8c8", align: "right" });
      drawText(ctx, state.message || "", x + 14, y + 60, { size: 11, color: "#aeb8c8" });

      const stepWidth = (width - 28 - 18) / 4;
      let sx = x + 14;
      for (const [key, label] of stageLabels) {
        const percent = stagePercent(state, key);
        const color = key === "sampling" ? "#f59e0b" : key === "download" ? "#22c55e" : "#38bdf8";
        drawText(ctx, label, sx, y + 82, { size: 10, color: "#aeb8c8", weight: "700" });
        drawBar(ctx, sx, y + 89, stepWidth, 6, percent, color);
        drawText(ctx, `${clamp(percent, 0, 100).toFixed(0)}%`, sx + stepWidth, y + 107, { size: 10, color: "#7f8a9d", align: "right" });
        sx += stepWidth + 6;
      }

      const upload = state.upload || {};
      const sampling = state.sampling || {};
      const download = state.download || {};
      drawText(ctx, `Total ${formatSeconds(state.total_elapsed_sec)}`, x + width - 14, y + 124, {
        size: 11,
        color: "#aeb8c8",
        align: "right",
      });

      const colGap = 10;
      const colWidth = (width - 28 - colGap * 2) / 3;
      const left = x + 14;
      const mid = left + colWidth + colGap;
      const right = mid + colWidth + colGap;
      const rowY = y + 144;
      drawText(ctx, "Upload", left, rowY, { size: 10, weight: "700", color: "#8bd3ff" });
      drawText(ctx, `${formatMB(upload.mb)}  ${formatSpeed(upload.mbps)}`, left, rowY + 17, {
        size: 11,
        color: "#d7dde8",
        maxWidth: colWidth,
      });
      drawText(ctx, "Sampling", mid, rowY, { size: 10, weight: "700", color: "#ffd28a" });
      drawText(ctx, `${sampling.step ?? 0}/${sampling.steps ?? 0}  ${formatSeconds(sampling.elapsed_sec)}`, mid, rowY + 17, {
        size: 11,
        color: "#d7dde8",
        maxWidth: colWidth,
      });
      drawText(ctx, "Download", right, rowY, { size: 10, weight: "700", color: "#8ef0ad" });
      drawText(ctx, `${formatMB(download.mb)}  ${formatSpeed(download.mbps)}`, right, rowY + 17, {
        size: 11,
        color: "#d7dde8",
        maxWidth: colWidth,
      });
    },
  };
  return widget;
}

function installPanel(node) {
  node.remoteSamplingPanel = node.remoteSamplingPanel || makeInitialState();
  if (node.id != null) {
    window.__remoteSamplingPanelStates[String(node.id)] = node.remoteSamplingPanel;
  }
  node.widgets = node.widgets || [];
  let panel = node.widgets.find((widget) => widget.name === "remote_sampling_panel");
  if (!panel) {
    panel = node.addCustomWidget(createPanelWidget());
  }
  panel.remoteSamplingPanel = node.remoteSamplingPanel;
  panel.value = node.remoteSamplingPanel;
  registerPanelNode(node);
  startPollingNode(node);
  updateNodeSize(node);
}

function patchRemoteSamplingNode(nodeType) {
  const originalCreated = nodeType.prototype.onNodeCreated;
  nodeType.prototype.onNodeCreated = function () {
    const result = originalCreated?.apply(this, arguments);
    installPanel(this);
    return result;
  };

  const originalConfigure = nodeType.prototype.configure;
  nodeType.prototype.configure = function () {
    const result = originalConfigure?.apply(this, arguments);
    installPanel(this);
    return result;
  };

  const originalExecuted = nodeType.prototype.onExecuted;
  nodeType.prototype.onExecuted = function (message) {
    const result = originalExecuted?.apply(this, arguments);
    const reportText = Array.isArray(message?.text) ? message.text.join("\n") : message?.text;
    if (reportText) {
      const parsed = parseReport(reportText);
      updateNodesById(this.id, {
        ...parsed,
        reportText,
        stage: parsed.stage || "completed",
        message: parsed.message || "Remote sampling complete",
        overall_percent: 100,
      });
      for (const node of getRemoteNodes(this.id)) {
        updateNodeSize(node);
      }
    }
    return result;
  };

  const originalRemoved = nodeType.prototype.onRemoved;
  nodeType.prototype.onRemoved = function () {
    unregisterPanelNode(this);
    return originalRemoved?.apply(this, arguments);
  };
}

api.addEventListener("executing", (event) => {
  const nodeId = event.detail?.node;
  if (!getRemoteNode(nodeId)) return;
  activeRemoteNodeId = String(nodeId);
  updateNodesById(nodeId, {
    stage: "running",
    message: "Remote bridge is running",
    overall_percent: 1,
    error: null,
  });
});

api.addEventListener("progress", (event) => {
  const detail = event.detail || {};
  const nodeId = detail.node ?? activeRemoteNodeId;
  if (!getRemoteNode(nodeId)) return;
  const value = asNumber(detail.value, 0);
  const max = Math.max(1, asNumber(detail.max, 100));
  const percent = clamp((value / max) * 100, 0, 100);
  updateNodesById(nodeId, {
    stage: "running",
    message: "Remote sampling in progress",
    overall_percent: percent,
  });
});

api.addEventListener("remote_sampling_progress", (event) => {
  const detail = event.detail || {};
  const nodeId = detail.node ?? activeRemoteNodeId;
  if (!getRemoteNode(nodeId)) return;
  activeRemoteNodeId = String(nodeId);
  updateNodesById(nodeId, stateFromProgressEvent(detail));
});

api.addEventListener("executed", (event) => {
  const nodeId = event.detail?.node;
  const node = getRemoteNode(nodeId);
  if (!node) return;
  activeRemoteNodeId = null;
});

api.addEventListener("execution_error", (event) => {
  const nodeId = event.detail?.node_id ?? event.detail?.node;
  const targetNodeId = getRemoteNode(nodeId) ? nodeId : activeRemoteNodeId;
  if (!getRemoteNode(targetNodeId)) return;
  activeRemoteNodeId = null;
  updateNodesById(targetNodeId, {
    stage: "failed",
    message: event.detail?.exception_message || "Remote sampling failed",
    error: event.detail || true,
  });
});

app.registerExtension({
  name: "ComfyUI.RemoteSampling.Panel",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name === NODE_NAME) {
      patchRemoteSamplingNode(nodeType);
    }
  },
});
