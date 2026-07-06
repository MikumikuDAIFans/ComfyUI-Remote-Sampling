# Phase 2 Runtime Config Evidence

- Date: `2026-07-06`
- UI screenshot: `runtime_config_panel_loaded.png`
- Non-default project root validation run: `workflow_runtime_20260706_205144_6dad18b6`

## Result

The workflow runtime frontend now has a `Runtime Config` section backed by `localStorage`.

Config fields:

- `project_root`
- `python_executable`
- `local_comfy_api`
- `timeout_sec`
- `remote_executor`
- `remote_profile`

The official Plan/Convert/Run flow now sends config through the request payload. Status polling includes `project_root`, so runs created outside the default project root can be read back correctly.

## API Validation

Plan request used:

```text
project_root: F:\TieguoDun\Remote_comfyui\_phase2_temp_project_root
```

Observed result:

```json
{
  "plan_ok": true,
  "run_id": "workflow_runtime_20260706_205144_6dad18b6",
  "run_dir_under_temp": true,
  "status_ok": true,
  "status_stage": "analysis"
}
```

## Static Validation

- `python -m py_compile` passed for changed Python files.
- `node --check ComfyUI-Remote-Sampling\web\remote_workflow_runtime.js` passed.
