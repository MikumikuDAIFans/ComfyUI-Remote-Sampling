## Remote Sampling Audit Tool Samples

Date: 2026-07-04

Tool:

```powershell
python F:\TieguoDun\Remote_comfyui\tools\audit_remote_sampling_workflow.py
```

### Fixed Profile Workflow

Command:

```powershell
python tools\audit_remote_sampling_workflow.py --workflow workflows\runs\remote_sampling_monitor_smoke_20260701_api.json
```

Result summary:

```text
Node 500 sampler_id=monitor_smoke_500
Profile: anima_qwen_aella_xcn
UNET: anima-base-v1.0.safetensors
CLIP: qwen_3_06b_base.safetensors
LoRA:
  Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors, model 1.1, clip 1.1
  Anima/画风/xcn_ogpt_v1a.safetensors, model 1.0, clip 1.0
Warning: fixed profile anima_qwen_aella_xcn loads Aella/xcn LoRA; unsafe for equivalence tests unless explicitly intended
```

### Auto Base Workflow

Command:

```powershell
python tools\audit_remote_sampling_workflow.py --workflow workflows\runs\remote_sampling_converter_converted_auto_20260701_api.json
```

Result summary:

```text
Node 500 sampler_id=converted_auto_500
Profile: generated/auto_remote_sampling_converter_converted_auto_20260701_api_500
UNET: anima-base-v1.0.safetensors
CLIP: qwen_3_06b_base.safetensors
LoRA: none
```

### Latest Polluted Job

Command:

```powershell
python tools\audit_remote_sampling_workflow.py --job jobs\remote_sampling_20260704_004643_4437fd3f_final_screenshot_smoke_20260703_123638
```

Result summary:

```text
Job: jobs\remote_sampling_20260704_004643_4437fd3f_final_screenshot_smoke_20260703_123638
Profile: anima_qwen_aella_xcn
LoRA:
  Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors, model 1.1, clip 1.1
  Anima/画风/xcn_ogpt_v1a.safetensors, model 1.0, clip 1.0
Remote classes: UNETLoader, CLIPLoader, LoraLoader, LoraLoader, Remote_Sampling_remote
Remote LoraLoader count: 2
Forbidden image nodes: []
status.json exists: True
result.json exists: True
Warning: fixed profile anima_qwen_aella_xcn loads Aella/xcn LoRA; unsafe for equivalence tests unless explicitly intended
```
