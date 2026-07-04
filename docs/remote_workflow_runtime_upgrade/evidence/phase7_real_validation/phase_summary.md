# Phase 7 Summary

- Phase: `Phase 7: Real Workflow Validation Matrix`
- Status: `done for current validation slice`
- Result: `pass for current clean, LoRA, custom-node import smoke, and fail-closed cases`

## Validation Results

| Scenario | Result | Evidence |
|---|---|---|
| Missing LoRA fail-closed | pass | `/remote_workflow/runtime/convert` returned HTTP 400 before queueing; no new job was created. |
| Clean guarded smoke | pass | Covered in Phase 6 with `phase6_guarded_smoke_20260705_003730`. |
| Real LoRA guarded smoke | pass | `phase7_lora_smoke_20260705_004202` completed; remote preflight checked exactly UNET/CLIP/Aella/xcn and no missing resources. |
| Clean formal 20-step guarded run | pass | `phase7_clean_formal20_20260705_004520` completed; profile LoRA count was `0`; remote had no image outputs. |
| Clean animal 20-step guarded run | pass | `guarded_clean_animal20_20260705_035631` completed; profile LoRA count was `0`; output is a red panda and not a white-haired girl. |
| Remote privacy boundary | pass | Remote job dirs and remote `ComfyUI/output` had no PNG/JPG/JPEG/WEBP for Phase 7 runs. |
| Guarded missing LoRA fail-closed | pass | `/remote_workflow/runtime/run` returned HTTP 400 before queueing; no job was created. |
| Custom-node workflow prepare | pass | Real LoRA workflow guarded prepare produced resources diff, environment report, import smoke hash, conversion, and exact LoRA profile. |

## Missing LoRA Fail-Closed

```text
run_id: workflow_runtime_20260705_004122_b7818aba
http_status: 400
error: LocalResourceMissing
missing: __missing_phase7_lora__.safetensors
jobs_created: []
```

## Real LoRA Guarded Smoke

```text
workflow_run_id: workflow_runtime_20260705_004202_510c0a7b
prompt_id: 59c5ee34-0861-4bbf-a7bc-ce0eb790c8fd
tag: phase7_lora_smoke_20260705_004202
history_status: success
```

Converted profile:

```text
lora_count: 2
loras:
  Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors
  Anima/画风/xcn_ogpt_v1a.safetensors
```

Remote sampling job:

```text
job: F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260705_004211_31d5ead4_phase7_lora_smoke_20260705_004202_19
sampling: 4/4, elapsed_sec=11.869
upload: 2672570 bytes, 100%
download: 2336290 bytes, 100%
preflight_missing: []
preflight_checked:
  unet anima-base-v1.0.safetensors
  clip qwen_3_06b_base.safetensors
  lora Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors
  lora Anima/画风/xcn_ogpt_v1a.safetensors
```

## Clean Formal 20-Step Guarded Run

```text
workflow_run_id: workflow_runtime_20260705_004520_9b759e8a
prompt_id: 99f6a760-3bf9-4e82-a2cd-55153f01f4f6
tag: phase7_clean_formal20_20260705_004520
history_status: success
profile_lora_counts: [0]
```

Remote sampling job:

```text
job: F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260705_004521_250048cc_phase7_clean_formal20_20260705_004520_500
sampling: 20/20, elapsed_sec=9.319
upload: 183866 bytes, 100%
download: 394786 bytes, 100%
```

Local output:

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\phase7_clean_formal20_20260705_004520_00001_.png
```

## Clean Animal 20-Step Guarded Run

```text
workflow_run_id: workflow_runtime_20260705_035631_d4fb64ac
prompt_id: 95c648f5-9ee7-4a9f-86ec-d8467e4c8a75
tag: guarded_clean_animal20_20260705_035631
history_status: success
profile_lora_counts: [0]
```

Local job:

```text
job: F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260705_035654_c61e6b47_guarded_clean_animal20_20260705_035631_500
sampling: 20/20, elapsed_sec=9.301
upload: 257978 bytes, 100%
download: 394786 bytes, 100%
```

Local output:

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\guarded_clean_animal20_20260705_035631_00001_.png
```

Visual check:

```text
Result shows a red panda in grass. No white-haired girl or old character LoRA feature is visible.
```

## Remote Privacy Evidence

For Phase 7 successful runs:

```text
remote job images: none
remote ComfyUI/output recent images: none
locks: empty
```

## Guarded Run Fail-Closed

```text
run_id: workflow_runtime_20260705_035323_00847d1c
route: /remote_workflow/runtime/run
http_status: 400
error: LocalResourceMissing
missing: __missing_guarded_run_lora__.safetensors
jobs_created: []
```

## Custom-Node Guarded Prepare

```text
workflow_run_id: workflow_runtime_20260705_035146_30d3249a
stage: queue
resources_diff_sha256: present
remote_environment_report_sha256: present
remote_custom_node_import_smoke_sha256: present
converted_prompt_object: present
```

Dependency-aware guarded prepare:

```text
workflow_run_id: workflow_runtime_20260705_040251_7f49bf25
stage: queue
resources_diff_sha256: present
remote_environment_report_sha256: present
remote_custom_node_dependency_install_sha256: present
remote_custom_node_import_smoke_sha256: present
remote_execution_plan_sha256: present
```

Converted profile:

```text
lora_count: 2
loras:
  Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors
  Anima/画风/xcn_ogpt_v1a.safetensors
```

## Remaining Phase 7 Work

- Repeat a 20-30 step LoRA formal run if image quality validation, not just runtime correctness, is required.
