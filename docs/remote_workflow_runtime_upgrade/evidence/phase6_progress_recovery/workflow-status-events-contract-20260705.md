# Workflow Status And Events Contract Check

- Time: `2026-07-05 04:22 +08:00`
- Scope: workflow-level status/events/report baseline for guarded runtime preparation.
- Code paths:
  - `ComfyUI-Remote-Sampling/workflow_runtime.py`
  - `ComfyUI-Remote-Sampling/__init__.py`
  - `ComfyUI-Remote-Sampling/web/remote_workflow_runtime.js`

## Commands

```powershell
python -m py_compile ComfyUI-Remote-Sampling\__init__.py ComfyUI-Remote-Sampling\workflow_runtime.py ComfyUI-Remote-Sampling\workflow_analyzer.py ComfyUI-Remote-Sampling\resource_planner.py ComfyUI-Remote-Sampling\custom_node_planner.py
node --check ComfyUI-Remote-Sampling\web\remote_workflow_runtime.js
git diff --check
```

## Plan-Only Contract Probe

Input prompt:

```text
F:\TieguoDun\Remote_comfyui\runs\workflow_runtime_20260705_035631_d4fb64ac\source_prompt.json
```

Generated run:

```text
workflow_runtime_20260705_042216_2f9bf94b
```

Observed result:

```json
{
  "ok": true,
  "run_id": "workflow_runtime_20260705_042216_2f9bf94b",
  "stage": "analysis",
  "percent": 30.0,
  "event_count": 4,
  "has_report": true,
  "manifest_has_events": true,
  "manifest_has_report_hash": true
}
```

## Result

- `workflow_status.json` is written during workflow-level planning.
- `workflow_events.jsonl` is appended during planning stages.
- `workflow_runtime_report.txt` is generated and hash-linked from `manifest.json`.
- `/remote_workflow/runtime/run_status` is registered for frontend polling.
- Frontend `Run Guarded` now creates a plan first, polls by `run_id`, then prepares and queues the converted prompt.

## Local UI Evidence

- Local package was copied to:

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\custom_nodes\ComfyUI-Remote-Sampling
```

- Local ComfyUI 8188 was restarted.
- API readiness check:

```text
ready 2361 True True True
```

- Screenshot: `workflow-runtime-panel-20260705.png`
- Screenshot: `workflow-runtime-guarded-status-20260705.png`

The guarded status screenshot used the currently open AuraFlow workflow as a fail-closed UI path. It did not proceed to remote sampling. The generated workflow-level run was:

```text
workflow_runtime_20260705_042623_165ae28d
```

Observed bundle fields:

```json
{
  "run_id": "workflow_runtime_20260705_042623_165ae28d",
  "status_stage": "analysis",
  "status_fatal": true,
  "status_percent": 30.0,
  "event_count": 4,
  "has_report": true,
  "manifest_events_hash": true,
  "manifest_report_hash": true,
  "error_type": null
}
```

## Remaining Validation

- Frontend now continues polling ComfyUI history after queue submission and summarizes the `Remote Sampling Report` into the workflow-level panel when the prompt completes.
- Remaining gap: backend `workflow_status.json` still reaches `queue`; queue-after job progress is currently frontend-observed from ComfyUI history rather than written back into the workflow-level status file.

## Real Guarded Smoke After Remote Sync

- Remote package sync target:

```text
/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/ComfyUI-Remote-Sampling
```

- Sync verification:

```text
grep run_status -> __init__.py, workflow_runtime.py, web/remote_workflow_runtime.js
```

- Workflow run:

```text
workflow_runtime_20260705_042940_2e199900
```

- ComfyUI prompt id:

```text
1ae17b5e-8c90-446e-86a6-25ef051c62e8
```

- Remote sampling job:

```text
remote_sampling_20260705_043003_c7affb69_workflow_status_real_smoke_20260705_0430_500
```

- Result:

```json
{
  "workflow_stage": "queue",
  "workflow_percent": 72.0,
  "workflow_event_count": 15,
  "workflow_report": true,
  "workflow_manifest_hashes": {
    "workflow_status_sha256": true,
    "workflow_events_sha256": true,
    "workflow_report_sha256": true,
    "remote_execution_plan_sha256": true,
    "converted_local_prompt_sha256": true
  },
  "sampling": {
    "step": 4,
    "steps": 4,
    "percent": 100.0,
    "elapsed_sec": 2.917,
    "sec_per_step": 0.729,
    "eta_sec": 0.0
  },
  "upload": {
    "bytes": 257978,
    "percent": 100.0,
    "mbps": 0.062
  },
  "download": {
    "bytes": 394786,
    "percent": 100.0,
    "mbps": 0.128
  }
}
```

- Remote privacy check:

```text
find jobs/remote_sampling_20260705_043003_c7affb69_workflow_status_real_smoke_20260705_0430_500 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.webp" \) -> no output
find ComfyUI/output ... -mmin -20 -> no output
ss -ltnp | grep ":8197 " -> no output
find locks -maxdepth 2 -> locks
```

## Queue-After Frontend Aggregation

- Added frontend history polling after `/prompt` submission.
- During execution, workflow-level panel shows `sampling` and the queued `prompt_id`.
- On completion, workflow-level panel parses `Remote Sampling Report` from ComfyUI history outputs and displays:
  - workflow run id
  - prompt id
  - job id
  - total elapsed seconds
  - upload metrics
  - sampling metrics
  - download metrics
- Latest local and remote custom node packages were synced after this change.
- Remote sync verification:

```text
grep "Guarded remote workflow run completed." -> web/remote_workflow_runtime.js
```

## Client Event Persistence

- Added backend route:

```text
POST /remote_workflow/runtime/client_event
```

- Purpose:
  - allow the workflow-level frontend to persist queue-after observations back into the workflow bundle;
  - update `workflow_status.json`;
  - append `workflow_events.jsonl`;
  - regenerate `workflow_runtime_report.txt`;
  - refresh manifest status/events/report hashes.

- Contract probe:

```json
{
  "ok": true,
  "stage": "complete",
  "percent": 100.0,
  "client_observed": true,
  "job_id": "contract-probe-job",
  "event_tail": 5,
  "manifest_events_hash": true,
  "manifest_status_hash": true,
  "manifest_report_hash": true
}
```

## Real Client Event Smoke

- Workflow run:

```text
workflow_runtime_20260705_121532_7fd71d73
```

- ComfyUI prompt id:

```text
c125bf4d-bcdf-414a-b825-8256fe572499
```

- Remote sampling job:

```text
remote_sampling_20260705_121605_b72e4fcf_workflow_client_event_smoke_20260705_0445_500
```

- Persisted workflow-level status after `client_event` complete:

```json
{
  "status_stage": "complete",
  "status_percent": 100.0,
  "client_observed": true,
  "event_count_tail": 18,
  "sampling": {
    "step": 4,
    "steps": 4,
    "percent": 100.0,
    "elapsed_sec": 2.768,
    "sec_per_step": 0.692,
    "eta_sec": 0.0
  },
  "upload": {
    "bytes": 257978,
    "percent": 100.0,
    "mbps": 0.016
  },
  "download": {
    "bytes": 394786,
    "percent": 100.0,
    "mbps": 0.024
  },
  "manifest_status_hash": true,
  "manifest_events_hash": true,
  "manifest_report_hash": true
}
```

- Remote privacy check:

```text
find jobs/remote_sampling_20260705_121605_b72e4fcf_workflow_client_event_smoke_20260705_0445_500 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.webp" \) -> no output
find ComfyUI/output ... -mmin -20 -> no output
ss -ltnp | grep ":8197 " -> no output
find locks -maxdepth 2 -> locks
```
