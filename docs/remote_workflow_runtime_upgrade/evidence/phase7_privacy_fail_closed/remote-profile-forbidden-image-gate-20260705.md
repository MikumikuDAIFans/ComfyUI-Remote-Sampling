# Remote Profile Forbidden Image Gate

- Time: `2026-07-05 12:33 +08:00`
- Phase: `Phase 7 Privacy And Fail-Closed Hardening`
- Scenario: forbidden remote image node guard

## Boundary Clarification

Local workflows are allowed to contain RGB-facing nodes such as:

- `VAEDecode`
- `SaveImage`

Those nodes are local-only. The privacy boundary is violated only if the remote sampling profile/prompt contains image I/O or VAE image nodes.

## Implementation

`ComfyUI-Remote-Sampling/workflow_runtime.py` now derives a remote prompt privacy summary from each generated profile snapshot.

The checked remote class list is reconstructed from:

- profile `unet.class_type`;
- profile `clip.class_type`;
- profile LoRA `class_type` values;
- `Remote_Sampling_remote`.

Forbidden remote classes:

```text
LoadImage
VAEEncode
VAELoader
VAEDecode
PreviewImage
SaveImage
```

If any forbidden class appears in a generated profile, workflow-level conversion fails with:

```text
RemotePromptForbiddenImageNodes
```

## Clean Workflow Probe

Source workflow:

```text
F:\TieguoDun\Remote_comfyui\runs\workflow_runtime_20260705_035631_d4fb64ac\source_prompt.json
```

Result:

```json
{
  "ok": true,
  "run_id": "workflow_runtime_20260705_123226_ca571890",
  "stage": "convert",
  "privacy_scope": "remote_profile_prompt_reconstruction",
  "forbidden_count": 0,
  "forbidden": [],
  "remote_classes": [
    "UNETLoader",
    "CLIPLoader",
    "Remote_Sampling_remote"
  ],
  "local_converted_contains_save_image": true,
  "converted_prompt_exists": true,
  "remote_execution_plan_hash": true
}
```

Interpretation:

- The local converted prompt still contains `SaveImage`, as expected.
- The reconstructed remote sampling prompt contains no RGB image nodes.

## Synthetic Malicious Profile Probe

A synthetic profile was created with:

- `unet.class_type = VAEDecode`
- LoRA `class_type = SaveImage`

Result:

```json
{
  "forbidden_count": 2,
  "forbidden": [
    "SaveImage",
    "VAEDecode"
  ],
  "classes": [
    "VAEDecode",
    "CLIPLoader",
    "SaveImage",
    "Remote_Sampling_remote"
  ],
  "scope": "remote_profile_prompt_reconstruction"
}
```

## Remote Sync

Updated custom node package was synced to:

```text
/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/ComfyUI-Remote-Sampling
```

Remote verification:

```text
grep remote_profile_prompt_reconstruction -> workflow_runtime.py
```

## Gate Result

- Local RGB decode/save remains allowed: `pass`
- Reconstructed remote prompt has forbidden count 0 for clean workflow: `pass`
- Synthetic malicious remote profile is detected: `pass`
- Remote package contains latest privacy gate: `pass`
