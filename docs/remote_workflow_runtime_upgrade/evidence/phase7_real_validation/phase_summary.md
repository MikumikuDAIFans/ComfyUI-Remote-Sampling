# Phase 7 Summary

- Phase: `Phase 7: Real Workflow Validation Matrix`
- Status: `partial done`
- Result: `pass for current clean, LoRA, and fail-closed cases`

## Validation Results

| Scenario | Result | Evidence |
|---|---|---|
| Missing LoRA fail-closed | pass | `/remote_workflow/runtime/convert` returned HTTP 400 before queueing; no new job was created. |
| Clean guarded smoke | pass | Covered in Phase 6 with `phase6_guarded_smoke_20260705_003730`. |
| Real LoRA guarded smoke | pass | `phase7_lora_smoke_20260705_004202` completed; remote preflight checked exactly UNET/CLIP/Aella/xcn and no missing resources. |
| Clean formal 20-step guarded run | pass | `phase7_clean_formal20_20260705_004520` completed; profile LoRA count was `0`; remote had no image outputs. |
| Remote privacy boundary | pass | Remote job dirs and remote `ComfyUI/output` had no PNG/JPG/JPEG/WEBP for Phase 7 runs. |

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

## Remote Privacy Evidence

For both Phase 7 successful runs:

```text
remote job images: none
remote ComfyUI/output recent images: none
locks: empty
```

## Remaining Phase 7 Work

- Add a fresh small-animal prompt workflow as a named fixture rather than reusing the existing clean fixture.
- Add at least one custom-node-heavy workflow that either succeeds after sync or fails closed for unsupported conversion.
- Repeat a 20-30 step LoRA formal run if image quality validation, not just runtime correctness, is required.
