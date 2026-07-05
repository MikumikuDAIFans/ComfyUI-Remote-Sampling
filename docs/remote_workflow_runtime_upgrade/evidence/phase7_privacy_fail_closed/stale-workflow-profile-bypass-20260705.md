# Stale Workflow/Profile Bypass Guard

- Time: `2026-07-05 12:23 +08:00`
- Phase: `Phase 7 Privacy And Fail-Closed Hardening`
- Scenario: `Scenario F: Stale Workflow/Profile Bypass`

## Risk

When `/remote_workflow/runtime/run` accepts an existing `run_id`, the run must only reuse that plan for the exact same source prompt/workflow hash. Otherwise a stale workflow-level plan or stale profile could be paired with a different current graph, recreating the old LoRA/profile contamination class of bugs.

## Fix

`ComfyUI-Remote-Sampling/workflow_runtime.py` now verifies, inside `_load_plan_for_run()`:

- supplied `prompt` hash equals `manifest.source_prompt_sha256`;
- supplied frontend `workflow` hash equals `manifest.source_workflow_sha256` when both are present.

Mismatch fails in `local_preflight` before:

- remote resource diff;
- custom-node environment check;
- conversion;
- latent upload;
- remote sampling job creation.

Error types:

```text
SourcePromptHashMismatch
SourceWorkflowHashMismatch
```

## Function-Level Probe

Input:

- create plan from clean animal source prompt;
- call guarded run with the same `run_id` but a different LoRA workflow prompt.

Result:

```json
{
  "plan_run_id": "workflow_runtime_20260705_122113_f2d3b32b",
  "result_ok": false,
  "stage": "local_preflight",
  "error_type": "SourcePromptHashMismatch",
  "status_stage": "local_preflight",
  "status_fatal": true,
  "event_count_tail": 5,
  "resources_diff_created": false,
  "client_or_remote_job_files": false
}
```

## Route-Level Probe

After syncing and restarting local ComfyUI 8188:

Input:

- `POST /remote_workflow/runtime/plan` with clean animal source prompt;
- `POST /remote_workflow/runtime/run` with returned `run_id` but a different LoRA workflow prompt.

Result:

```json
{
  "plan_http": 200,
  "run_id": "workflow_runtime_20260705_122317_81f9a3c1",
  "run_http": 400,
  "ok": false,
  "stage": "local_preflight",
  "error_type": "SourcePromptHashMismatch",
  "status_stage": "local_preflight",
  "status_fatal": true,
  "resources_diff_created": false,
  "converted_prompt_created": false
}
```

## Remote Sync

Updated custom node package was synced to:

```text
/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/ComfyUI-Remote-Sampling
```

Remote verification:

```text
grep SourcePromptHashMismatch -> workflow_runtime.py
```

## Gate Result

- Stale source prompt/profile bypass: `pass`
- Failure happens before remote checks or latent upload: `pass`
- Formal workflow-level runs must re-plan if the current graph changes: `pass`
