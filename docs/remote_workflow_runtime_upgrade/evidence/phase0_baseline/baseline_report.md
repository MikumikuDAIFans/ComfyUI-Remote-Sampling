# Phase 0 Baseline Report

## Metadata

- Phase: `Phase 0: Baseline Freeze And Architecture Preflight`
- Time: `2026-07-04 23:35-23:42 +08:00`
- Local project root: `F:\TieguoDun\Remote_comfyui`
- Current commit: `ff1df3d Add runtime workflow conversion runner`
- Current branch: `main`
- Remote workspace: `/home/user02/remote_ComfyUI`

## Current Module Boundary

The current system already has a working runtime-conversion sampling path, but not yet a full workflow-level resource synchronizer.

| Module | Current artifact | Baseline behavior to preserve |
|---|---|---|
| Route registration | `ComfyUI-Remote-Sampling\__init__.py` | Provides `/remote_sampling/runtime/status`, `/remote_sampling/convert`, and `/remote_sampling/status`. |
| Runtime conversion | `ComfyUI-Remote-Sampling\runtime_conversion.py` | Creates per-run bundles under `runs/runtime_*`, writes source/converted prompt, profile snapshots, audit and manifest. |
| Frontend runtime entry | `ComfyUI-Remote-Sampling\web\remote_sampling_runtime_runner.js` | Provides right-bottom `Remote Sampling` panel and `Run Current Workflow` button. |
| Node monitoring panel | `ComfyUI-Remote-Sampling\web\remote_sampling_panel.js` | Keeps node-level upload/sampling/download progress display. |
| Local sampler node | `ComfyUI-Remote-Sampling\nodes\remote_sampling_local.py` | First output remains `LATENT`; fixed profile is refused before latent serialization/upload. |
| Bridge CLI | `ComfyUI-Remote-Sampling\tools\remote_sampling_job_cli.py` | Performs remote resource preflight before latent upload; rebuilds remote prompt per job; forbids remote image nodes. |
| Converter | `tools\convert_ksampler_to_remote_sampling.py` | Defaults to `remote_profile=auto`; fixed `anima_qwen_aella_xcn` is refused unless explicitly allowed. |
| Audit tool | `tools\audit_remote_sampling_workflow.py` | Audits workflow/job/bundle/profile and reports LoRA, remote classes, forbidden nodes and runtime alignment hashes. |

## Unit Validation

Command:

```powershell
python -m py_compile ComfyUI-Remote-Sampling\__init__.py ComfyUI-Remote-Sampling\runtime_conversion.py ComfyUI-Remote-Sampling\nodes\remote_sampling_local.py ComfyUI-Remote-Sampling\nodes\remote_sampling_remote.py ComfyUI-Remote-Sampling\protocol.py ComfyUI-Remote-Sampling\tools\remote_sampling_job_cli.py tools\convert_ksampler_to_remote_sampling.py tools\audit_remote_sampling_workflow.py
```

Result: passed.

## Contract Validation

Local 8188 runtime status and frontend extension check:

```json
{
  "ok": true,
  "runtime_status": {
    "ok": true,
    "version": "runtime-conversion-v1",
    "policy_version": "fail-closed-v1",
    "capabilities": {
      "convert": true,
      "convert_and_queue": true,
      "queue_mode": "frontend_converts_then_posts_converted_prompt",
      "expects_api_prompt": true,
      "accepts_frontend_workflow_snapshot": true,
      "default_remote_profile": "auto",
      "fixed_profiles_fail_closed": true,
      "remote_prompt_rebuilt_per_job": true
    }
  },
  "runner_js_has_button": true,
  "panel_version_present": true,
  "has_local_node": true,
  "has_remote_node": true,
  "object_count": 2361
}
```

## Remote Baseline

Remote command stayed under `/home/user02/remote_ComfyUI`.

```text
/home/user02/remote_ComfyUI
comfy_exists=yes
remote_sampling_node=yes
locks
```

No process was listening on port `8197` during the baseline check, and the remote lock directory only contained `locks`.

## Integration And Real Validation: Clean Animal Runtime Smoke

Fresh local API prompt was constructed in the validation script. It requested a small rabbit scene, explicitly negative prompted humans/girls/white hair, and used `steps=4` only for smoke validation.

Result:

```json
{
  "ok": true,
  "tag": "phase0_clean_animal_20260704_233614",
  "run_id": "runtime_20260704_233614_b882fea5",
  "run_dir": "F:\\TieguoDun\\Remote_comfyui\\runs\\runtime_20260704_233614_b882fea5",
  "lora_counts": [0],
  "prompt_id": "518c7748-d74e-4431-9bba-cba6e0c323ed",
  "job_dir": "F:\\TieguoDun\\Remote_comfyui\\jobs\\remote_sampling_20260704_233615_b18af4dd_phase0_clean_animal_20260704_233614_500",
  "image": "F:\\TieguoDun\\ComfyUI_NEW\\ComfyUI_windows_portable\\ComfyUI\\output\\remote_sampling_node\\phase0_clean_animal_20260704_233614_00001_.png",
  "elapsed_sec": 75.1
}
```

Visual inspection: the smoke image is low quality because it used only 4 steps, but it does not show a white-haired girl or character LoRA traits.

Bundle audit:

```text
Run: runtime_20260704_233614_b882fea5
Source prompt sha256: 3a3068cb4d9335e70e6b5b25fc3d8f0edfc723478be5345ff95d9e61ad59f54d
Converted prompt sha256: f352ef8ea3ae24c8506b5198f2ee01f7b107dfdd51a842c5415f3e6e5e51864b
Node 500 LoRA count: 0
```

Job audit:

```text
Remote classes: UNETLoader, CLIPLoader, Remote_Sampling_remote
Remote LoraLoader count: 0
Forbidden image nodes: []
Runtime bundle id: runtime_20260704_233614_b882fea5
Profile sha256: 2f78591b1d50a26032a7ab4923afb05db4bb4a05b311352ef0f5fe4e43d7fc38
Remote prompt sha256: 94293e3bcedef6652ceadead815a7ffd2a5a696eae9eae078efc0462a2187daa
Remote prompt rebuilt per job: True
```

Remote privacy check:

```text
job_images:
recent_output_images:
locks:
locks
```

No PNG/JPG/JPEG/WEBP was found in the remote job directory or recent remote `ComfyUI/output`.

## Gray Validation: Old Fixed Workflow Fails Closed

Old fixed-profile workflow source:

```text
F:\TieguoDun\Remote_comfyui\workflows\runs\remote_sampling_monitor_smoke_20260701_api.json
```

Validation tag:

```text
phase0_fixed_guard_20260704_233754
```

Result:

```json
{
  "prompt_id": "3f3c325a-2f0c-4524-a885-3b87aee4f86b",
  "history_status": "error",
  "job_dir": "F:\\TieguoDun\\Remote_comfyui\\jobs\\remote_sampling_20260704_233755_64075cc6_phase0_fixed_guard_20260704_233754",
  "job_files": ["events.jsonl", "job.json", "remote_sampling_report.txt", "status.json"],
  "has_inputs_pt": false,
  "status_stage": "failed",
  "error_type": "FixedRemoteProfileRefused"
}
```

The fixed profile was refused before latent upload.

## LoRA Baseline Evidence

Existing runtime LoRA job audited as a current baseline:

```text
Job: F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260704_021457_64943a70_runtime_lora_202660704_021457
Bundle: F:\TieguoDun\Remote_comfyui\runs\runtime_20260704_021457_c7d4d301
```

Audit summary:

```text
Remote classes: UNETLoader, CLIPLoader, LoraLoader, LoraLoader, Remote_Sampling_remote
Remote LoraLoader count: 2
LoRA:
  - Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors (model=1.1, clip=1.1)
  - Anima/画风/xcn_ogpt_v1a.safetensors (model=1.0, clip=1.0)
Remote prompt rebuilt per job: True
```

## Zero-Short Frontend Validation

Playwright opened `http://127.0.0.1:8188/` in a fresh browser tab and captured an accessibility snapshot after ComfyUI finished loading.

Evidence:

- `phase0-comfyui-snapshot-ready.md`
- `phase0-comfyui-ui.png` exists locally but is ignored by Git because `*.png` is ignored.

Snapshot excerpt:

```text
generic [box=999,593,360,104]:
  generic [box=1000,594,358,48]:
    generic: Remote Sampling
    button "Run Current Workflow"
    button "Hide"
  generic: Ready. Uses the current graph, converts it at runtime, audits it, then queues the converted prompt.
```

## Preserve List For Later Phases

- Keep `Remote_Sampling_local` first output as `LATENT`.
- Keep fixed-profile refusal defaulting to `allow_fixed_profile=false`.
- Keep remote resource preflight before `inputs.pt` upload.
- Keep remote prompt rebuilt per job.
- Keep forbidden remote image nodes blocked.
- Keep node-level monitoring panel while adding workflow-level UI.
- Keep run bundle/profile snapshot/audit as the traceability anchor.

## Phase 0 Gate Result

`RWR-GATE-01 Baseline Frozen`: pass.

Known limitations carried forward:

- Current runtime conversion is limited to simple KSampler/model/CLIP/LoRA chains.
- Full workflow-level resource synchronization does not exist yet.
- Custom node Linux compatibility is not yet managed.
- Large model transfer resume/hash policies are not yet implemented.
