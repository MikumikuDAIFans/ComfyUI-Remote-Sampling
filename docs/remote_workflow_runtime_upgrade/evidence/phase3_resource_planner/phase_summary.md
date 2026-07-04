# Phase 3 Summary

- Phase: `Phase 3: Resource Inventory And Sync Planner`
- Status: `done`
- Result: `pass`

## Implemented

- Added resource planner module: `ComfyUI-Remote-Sampling\resource_planner.py`.
- Updated workflow runtime plan bundles to include:
  - `resources_plan.json`
  - `resources_plan_sha256`
  - resource summary in `manifest.json`
- Added remote diff tool:
  - `tools\check_remote_resource_plan.py`

## Resource Plan Behavior

Each analyzed resource is mapped from local ComfyUI models relative path to remote ComfyUI models relative path.

Examples:

```text
local:  ComfyUI\models\loras\Anima\角色\AellaStella_v1_anima_char-000018-2c97.safetensors
remote: /home/user02/remote_ComfyUI/ComfyUI/models/loras/Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors
```

The plan records:

- kind: `unet`, `clip`, `vae`, `lora`
- relative path
- local existence
- local candidate paths
- local file size
- inline SHA256 for files up to the configured threshold
- deferred hash policy for large files
- remote primary path and candidates
- upload command hint

## Validation Results

| Test type | Result | Evidence |
|---|---|---|
| Unit | pass | `py_compile` passed for `resource_planner.py`, `workflow_runtime.py`, `workflow_analyzer.py`, `check_remote_resource_plan.py`. |
| Contract | pass | `/remote_workflow/runtime/plan` returns `resources-plan-v1`. |
| Integration | pass | `tools/check_remote_resource_plan.py` read a route-generated plan and wrote `resources_diff.json`. |
| Gray | pass | Synthetic remote-missing and size-mismatch resource plans returned `upload_required` and `size_mismatch`. |
| Real | pass | Real LoRA workflow resource plan checked five remote resources and all were ready. |
| Zero-Short | pass | A new route-generated bundle contains `workflow_analysis.json`, `resources_plan.json`, and can be remote-checked without stale generated profile dependency. |

## Route Evidence

Route-generated LoRA plan:

```text
run_id: workflow_runtime_20260705_000917_f45f570f
schema: resources-plan-v1
summary:
  total: 5
  local_missing: 0
  needs_remote_check: 5
```

Resources:

```text
unet  anima-base-v1.0.safetensors
  -> /home/user02/remote_ComfyUI/ComfyUI/models/diffusion_models/anima-base-v1.0.safetensors
lora  Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors
  -> /home/user02/remote_ComfyUI/ComfyUI/models/loras/Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors
lora  Anima/画风/xcn_ogpt_v1a.safetensors
  -> /home/user02/remote_ComfyUI/ComfyUI/models/loras/Anima/画风/xcn_ogpt_v1a.safetensors
clip  qwen_3_06b_base.safetensors
  -> /home/user02/remote_ComfyUI/ComfyUI/models/clip/qwen_3_06b_base.safetensors
vae   qwen_image_vae_2.safetensors
  -> /home/user02/remote_ComfyUI/ComfyUI/models/vae/qwen_image_vae_2.safetensors
```

Remote diff:

```text
output: runs\workflow_runtime_20260705_000917_f45f570f\resources_diff.json
summary:
  total: 5
  ready: 5
  upload_required: 0
  size_mismatch: 0
  blocked_local_missing: 0
```

## Gray Evidence

Synthetic remote missing:

```text
summary:
  total: 1
  upload_required: 1
```

Synthetic size mismatch:

```text
summary:
  total: 1
  size_mismatch: 1
ok: false
```

## Boundary

Phase 3 checks model-resource alignment only. It does not install custom nodes or Python dependencies. That work starts in Phase 4.
