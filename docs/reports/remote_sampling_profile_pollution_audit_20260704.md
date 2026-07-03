## Remote Sampling Profile Pollution Audit

Date: 2026-07-04

### Summary

This audit freezes the current evidence for the reported issue: workflows that should not use a character LoRA can still produce Aella-like results when they are run through an old fixed-profile remote sampling workflow.

The immediate cause is not latent transport corruption. Recent jobs and several historical workflow files explicitly use the fixed profile `anima_qwen_aella_xcn`. That profile loads:

- `Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors`, strength model `1.1`, strength clip `1.1`
- `Anima/画风/xcn_ogpt_v1a.safetensors`, strength model `1.0`, strength clip `1.0`

Therefore a base-only local workflow can be polluted if it is manually or historically converted to `remote_profile: anima_qwen_aella_xcn`.

### Fixed Profile Contents

Profile file:

```text
F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\anima_qwen_aella_xcn.json
```

Resolved resources:

```text
UNET: anima-base-v1.0.safetensors
CLIP: qwen_3_06b_base.safetensors
LoRA:
  Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors, model 1.1, clip 1.1
  Anima/画风/xcn_ogpt_v1a.safetensors, model 1.0, clip 1.0
```

The base profile does not contain LoRA:

```text
Profile: anima_qwen_base
UNET: anima-base-v1.0.safetensors
CLIP: qwen_3_06b_base.safetensors
LoRA: none
```

### Recent Job Evidence

The most recent 15 `remote_sampling_*` job directories all used `remote_profile: anima_qwen_aella_xcn`. Each corresponding `job.json` includes the two LoRA entries above, and each remote prompt class list contains:

```text
UNETLoader, CLIPLoader, LoraLoader, LoraLoader, Remote_Sampling_remote
```

Representative latest job:

```text
F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260704_004643_4437fd3f_final_screenshot_smoke_20260703_123638
remote_profile: anima_qwen_aella_xcn
remote prompt classes: UNETLoader, CLIPLoader, LoraLoader, LoraLoader, Remote_Sampling_remote
```

The same fixed-profile pattern appears in these recent jobs:

```text
remote_sampling_20260704_004643_4437fd3f_final_screenshot_smoke_20260703_123638
remote_sampling_20260704_003950_90349790_final_screenshot_smoke_20260703_123638
remote_sampling_20260703_225219_e2c32c02_final_screenshot_smoke_20260703_123638
remote_sampling_20260703_222106_5ee17217_panel_v6_repeat_seed_20260703_221814
remote_sampling_20260703_221823_d1d70b40_panel_v6_repeat_seed_20260703_221814
remote_sampling_20260703_221222_45d697c1_panel_v6_repeat_20260703_221208
remote_sampling_20260703_220149_a1f02c42_final_screenshot_smoke_20260703_123638
remote_sampling_20260703_193804_1e01d22c_panel_v5_real_20260703_193745
remote_sampling_20260703_190952_bace2be0_panel_live_fix_20260703_190944
remote_sampling_20260703_190123_2f1e1b67_panel_poll_fix_20260703_190115
remote_sampling_20260703_184247_3b9865ab_panel_refresh_fix_20260703_183949
remote_sampling_20260703_183944_2538a154_final_screenshot_smoke_20260703_123638
remote_sampling_20260703_183745_e6b58222_final_screenshot_smoke_20260703_123638
remote_sampling_20260703_182713_4b55e4e1_final_screenshot_smoke_20260703_123638
remote_sampling_20260703_123638_4f81077d_final_screenshot_smoke_20260703_123638
```

### Workflow File Evidence

The following `workflows\runs` files contain `Remote_Sampling_local.remote_profile: anima_qwen_aella_xcn` and are unsafe for resource-equivalence testing unless the original local workflow actually used the same Aella/xcn LoRA chain:

```text
ComfyUI_00042_remote_sampling_converted_20260630_api.json
ComfyUI_00042_remote_sampling_converted_full_20260701_api.json
ComfyUI_00042_remote_sampling_converted_reduced_20260630_1825_api.json
converted_00003_fixed_steps30_20260701_api.json
remote_sampling_converter_converted_20260630_1755_api.json
remote_sampling_g2_8188_smoke_20260701_api.json
remote_sampling_g4_audit_final_20260701_api.json
remote_sampling_g4_hash_audit_20260701_api.json
remote_sampling_metadata_20260630_1818_api.json
remote_sampling_monitor_quality20_20260701_api.json
remote_sampling_monitor_smoke_20260701_api.json
remote_sampling_node_dual_20260630_1745_local_api.json
remote_sampling_node_img2img_20260630_1735_local_api.json
remote_sampling_node_smoke_20260630_1500_local_api.json
remote_sampling_node_smoke_local_api.json
remote_sampling_profile_config_20260630_1810_api.json
```

### Existing Clean Auto Profile Evidence

The existing auto-converted base workflow uses a generated profile with no LoRA:

```text
Workflow:
F:\TieguoDun\Remote_comfyui\workflows\runs\remote_sampling_converter_converted_auto_20260701_api.json

Profile:
F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\generated\auto_remote_sampling_converter_converted_auto_20260701_api_500.json

UNET: anima-base-v1.0.safetensors
CLIP: qwen_3_06b_base.safetensors
LoRA: none
```

The existing auto-converted LoRA workflow contains Aella/xcn because its original model chain contained Aella/xcn:

```text
Workflow:
F:\TieguoDun\Remote_comfyui\workflows\runs\ComfyUI_00042_remote_sampling_converted_auto_20260701_api.json

Profile:
F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\generated\auto_ComfyUI_00042_remote_sampling_converted_auto_20260701_api_19.json

LoRA:
  Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors, model 1.1, clip 1.1
  Anima/画风/xcn_ogpt_v1a.safetensors, model 1.0, clip 1.0
```

### Conclusion

The current fixed-profile artifacts should be treated as deprecated for equivalence testing. The formal conversion path must use `--remote-profile auto` and must make fixed profile usage explicit, noisy, and optionally forbidden.

Next implementation steps:

1. Add a reusable audit CLI for workflows, job directories, and profiles.
2. Add fixed-profile protection to the converter.
3. Re-run base-only and LoRA conversions through the auto path and validate the remote prompt/resource lists.
