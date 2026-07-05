# Phase 9 Final Smoke Report

- Time: `2026-07-05 13:08 +08:00`
- Source: ordinary `KSampler` API prompt derived from `workflows/runs/remote_sampling_converter_source_20260630_1755_api.json`
- Source prompt type: clean base workflow, no LoRA
- Result: `pass`

## Run Summary

```text
tag: phase9_final_clean_animal_rerun_20260705_130317
workflow_run_id: workflow_runtime_20260705_130317_c9da533c
run_dir: F:\TieguoDun\Remote_comfyui\runs\workflow_runtime_20260705_130317_c9da533c
prompt_id: fb176de6-6085-44e1-835c-28ebbb11cd3f
history_status: success
manifest_stage: complete
workflow_status_stage: complete
workflow_status_percent: 100.0
job_id: remote_sampling_20260705_130350_0850f33b_phase9_final_clean_animal_rerun_20260705_130317_500
total_elapsed_sec: 84.151
```

## Conversion And Privacy Audit

```text
profile_lora_counts: [0]
remote_prompt_forbidden_image_node_count: 0
remote prompt reconstructed classes:
  UNETLoader
  CLIPLoader
  Remote_Sampling_remote
privacy_scope: remote_profile_prompt_reconstruction
```

The source prompt started with ordinary `KSampler`. The workflow-level runtime generated the converted prompt and remote profile for this run; it did not rely on a stale converted workflow.

## Transfer And Sampling Metrics

```text
sampling: {"elapsed_sec": 2.781, "eta_sec": 0.0, "percent": 100.0, "sec_per_step": 0.695, "step": 4, "steps": 4}
upload: {"bytes": 286714, "bytes_done": 286714, "bytes_total": 286714, "elapsed_sec": 12.204, "mb": 0.273, "mbps": 0.022, "percent": 100.0}
download: {"bytes": 394786, "bytes_done": 394786, "bytes_total": 394786, "elapsed_sec": 6.898, "mb": 0.376, "mbps": 0.055, "percent": 100.0}
```

## Hash Coverage

The run manifest contains:

```text
source_prompt_sha256: present
workflow_analysis_sha256: present
resources_plan_sha256: present
resources_diff_sha256: present
custom_nodes_plan_sha256: present
remote_environment_report_sha256: present
remote_custom_node_dependency_install_sha256: present
remote_custom_node_import_smoke_sha256: present
converted_local_prompt_sha256: present
remote_execution_plan_sha256: present
runtime_conversion_manifest_sha256: present
workflow_status_sha256: present
workflow_events_sha256: present
workflow_report_sha256: present
```

## Local Output

The image is intentionally not committed.

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\phase9_final_clean_animal_rerun_20260705_130317_00001_.png
size: 348879 bytes
visual check: red panda / small animal; no white-haired girl or old character LoRA feature visible
```

## Remote Privacy/Cleanup Check

Command scope: read-only under `/home/user02/remote_ComfyUI`.

```text
REMOTE_PWD=/home/user02/remote_ComfyUI
find jobs -path "*phase9_final_clean_animal_rerun_20260705_130317*" image files -> no output
find ComfyUI/output image files modified in last 180 minutes -> no output
ss -ltnp | grep ":8197 " -> no output
ps ... "ComfyUI/main.py|remote_submit_prompt" -> no output
find locks -maxdepth 2 -> locks
```

## Gate Decision

Final smoke gate: `pass`

This smoke proves the current loaded local ComfyUI package can convert a clean ordinary `KSampler` workflow through the workflow-level runtime, run remote latent-only sampling, persist workflow status/events/report, return latent to local decode/save, and keep the remote side free of RGB image artifacts.
