# Phase 6 Summary

- Phase: `Phase 6: Sync Engine, Progress UI And Failure Recovery`
- Status: `done for current guarded backend slice`
- Result: `pass for guarded backend run smoke`

## Implemented

- Added workflow-level frontend `Run Guarded` button.
- `Run Guarded` flow:
  - builds current graph API prompt
  - calls `/remote_workflow/runtime/run`
  - backend checks remote resources and syncs missing resources when allowed
  - backend checks/syncs custom nodes and performs remote object_info import smoke
  - backend converts current prompt after guards pass
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
| Contract | pass | `/remote_workflow/runtime/run` returns queueable `converted_prompt_object` plus resources/env/import-smoke hashes. |
| Integration | pass | API smoke performed guarded run prepare -> queue -> history success. |
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

## Guarded Backend Evidence

```text
workflow_run_id: workflow_runtime_20260705_034610_cbf7bcc6
prompt_id: 60a2bc4d-02e4-44d0-bd19-eb5c5bd2ca2c
tag: guarded_v2b_smoke_20260705_034610
history_status: success
```

Manifest hash chain:

```text
source_prompt_sha256: present
workflow_analysis_sha256: present
resources_plan_sha256: present
resources_diff_sha256: present
remote_environment_report_sha256: present
custom_nodes_plan_sha256: present
converted_local_prompt_sha256: present
remote_execution_plan_sha256: present
runtime_conversion_manifest_sha256: present
workflow_status_sha256: present
```

Local job:

```text
job: F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260705_034627_e6220dc1_guarded_v2b_smoke_20260705_034610_500
sampling: 3/3, elapsed_sec=2.432
upload: 183866 bytes, 100%
download: 394786 bytes, 100%
```

Remote privacy check:

```text
remote job images: none
remote ComfyUI/output recent images: none
locks: empty
```

Resource sync gray:

```text
output: synthetic_resource_sync_report.json
summary:
  uploaded: 1
  bytes: 37

output: synthetic_resource_sync_diff_after.json
summary:
  ready: 1
  upload_required: 0
  size_mismatch: 0
```

## Remaining Phase 6 Work

- Add richer workflow-level status/events files for pre-queue phases.
- Add retry/resume UI for resource and custom node sync failures.
