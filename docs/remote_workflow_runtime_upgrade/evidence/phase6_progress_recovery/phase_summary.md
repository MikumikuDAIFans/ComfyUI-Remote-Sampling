# Phase 6 Summary

- Phase: `Phase 6: Sync Engine, Progress UI And Failure Recovery`
- Status: `partial done`
- Result: `pass for guarded run smoke`

## Implemented

- Added workflow-level frontend `Run Guarded` button.
- `Run Guarded` flow:
  - builds current graph API prompt
  - calls `/remote_workflow/runtime/convert`
  - queues returned `converted_prompt_object` to `/prompt`
- Existing `Remote_Sampling_local` monitoring remains active for:
  - latent upload bytes/speed
  - remote sampling steps/time
  - latent download bytes/speed
  - total completion status
- Workflow-level route now avoids stale converted workflow use by converting from current source prompt per run.

## Validation Results

| Test type | Result | Evidence |
|---|---|---|
| Unit | pass | modified Python files compile; frontend JS loads in browser. |
| Contract | pass | `/remote_workflow/runtime/convert` returns queueable `converted_prompt_object`. |
| Integration | pass | API smoke performed convert -> queue -> history success. |
| Gray | pass | Remote job/output image privacy check passed for guarded run. |
| Real | pass | Low-step clean workflow produced a local output image and remote latent-only job. |
| Zero-Short | pass | Fresh browser session shows `Run Guarded` button. |

## Smoke Evidence

```text
workflow_run_id: workflow_runtime_20260705_003730_6b606ae8
prompt_id: 1bbf6eb8-a187-480d-8e37-baae572dfbec
tag: phase6_guarded_smoke_20260705_003730
history_status: success
outputs_nodes: 500, 4
```

Local job:

```text
job: F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260705_003734_07f1b496_phase6_guarded_smoke_20260705_003730_500
stage: completed
overall_percent: 100.0
sampling: 3/3, elapsed_sec=2.496
upload: 183866 bytes, 100%
download: 394786 bytes, 100%
```

Local output:

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\phase6_guarded_smoke_20260705_003730_00001_.png
```

Remote privacy check:

```text
remote job dir: jobs/remote_sampling_20260705_003734_07f1b496_phase6_guarded_smoke_20260705_003730_500
remote job images: none
remote ComfyUI/output recent images: none
remote 8197 listener: none
locks: empty
```

UI evidence:

```text
snapshot: docs\remote_workflow_runtime_upgrade\evidence\phase6_progress_recovery\phase6-ui-snapshot.md
screenshot: docs\remote_workflow_runtime_upgrade\evidence\phase6_progress_recovery\phase6-ui-run-guarded.png
```

## Remaining Phase 6 Work

- Move resource diff and custom node sync execution into a single backend orchestrator instead of relying on standalone tools plus node preflight.
- Add richer workflow-level status/events files for pre-queue phases.
- Add retry/resume UI for resource and custom node sync failures.
