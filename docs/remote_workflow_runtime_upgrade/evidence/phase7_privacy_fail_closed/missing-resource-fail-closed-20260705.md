# Missing Resource Fail-Closed

- Time: `2026-07-05 12:26 +08:00`
- Phase: `Phase 7 Privacy And Fail-Closed Hardening`
- Scenario: `Scenario D: Missing Resource`

## Probe

The clean animal source prompt was modified in memory so the UNET loader referenced:

```text
__codex_missing_unet_phase7_20260705__.safetensors
```

The workflow was submitted through:

```text
POST /remote_workflow/runtime/run
```

No remote command or latent upload should happen for this case.

## Result

```json
{
  "http": 400,
  "ok": false,
  "run_id": "workflow_runtime_20260705_122636_257bebbc",
  "stage": "remote_env",
  "error_types": [
    "LocalResourceMissing",
    "LocalResourceMissing"
  ],
  "status_stage": "analysis",
  "status_fatal": true,
  "resources_diff_created": false,
  "converted_prompt_created": false,
  "manifest_events_hash": true,
  "manifest_report_hash": true
}
```

Local job search:

```text
Get-ChildItem jobs -Directory | Where-Object { $_.Name -like '*missing_resource_phase7_20260705*' } -> no output
```

## Gate Result

- Missing local model resource detected before remote resource diff: `pass`
- No converted prompt generated: `pass`
- No remote sampling job created: `pass`
- Workflow-level status/events/report still generated for diagnosis: `pass`
