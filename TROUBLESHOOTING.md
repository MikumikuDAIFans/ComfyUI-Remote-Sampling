# Troubleshooting

## The Workflow Is Using an Old Remote Workflow

Use `Check & Sync` and `Convert Canvas` from the current canvas. The runtime records `source_prompt_sha256` and `source_workflow_sha256`; if a stale `run_id` is reused with a changed workflow, it should fail in local preflight with `SourcePromptHashMismatch` or `SourceWorkflowHashMismatch`.

Check:

- `runs/workflow_runtime_<id>/manifest.json`
- `runs/workflow_runtime_<id>/workflow_runtime_report.txt`
- frontend `Recent Runs` JSON copy button

## Missing LoRA or Model

Resource sync mirrors local relative paths under remote `ComfyUI/models`.

Example:

```text
local:  ComfyUI/models/loras/Anima/画风/example.safetensors
remote: /home/user/remote_ComfyUI/ComfyUI/models/loras/Anima/画风/example.safetensors
```

If sync is disabled or fails, inspect:

- `resources_plan.json`
- `resources_diff.json`
- `resources_sync_report.json`

The system should fail before latent upload when required remote resources are missing.

## Custom Node Missing on Remote

Inspect:

- `custom_nodes_plan.json`
- `remote_environment_report.json`
- `custom_nodes_sync_report.json`
- `remote_custom_node_dependency_install.json`
- `remote_custom_node_import_smoke.json`

If archive sync fails, install the same package on remote with ComfyUI Manager or copy/clone it manually into the same relative `ComfyUI/custom_nodes/<package>` path, then rerun `Check & Sync`.

If the workflow has no custom nodes, the system should skip remote custom-node checks and mark `remote_environment_short_circuit: true`.

## Dependency Install Is Not Executed

Dependency installation is dry-run by default. The tool writes planned commands to `remote_custom_node_dependency_install.json`.

Run dependency installation only after reviewing the commands. Some custom nodes have Linux system dependencies that cannot be solved by `pip install`; install those manually on the remote environment only when explicitly approved.

## Remote Sampling Progress Is Missing

Check node-level job files:

- `jobs/remote_sampling_<id>/status.json`
- `jobs/remote_sampling_<id>/events.jsonl`
- `jobs/remote_sampling_<id>/remote_sampling_report.txt`

The workflow-level panel shows preparation and recent run diagnostics. The actual latent upload, sampling step progress and latent download are node-level job metrics.

## SSH or Tunnel Failures

Retryable failures include SSH banner errors, local tunnel port failures, connection reset/refused and timeout errors. Re-run `Check & Sync` or the ComfyUI queue after confirming the remote host is reachable.

For generic SSH deployments, verify:

```powershell
python tools\generic_ssh_exec.py --cmd "hostname; pwd"
```

For custom server executors, verify that `REMOTE_SAMPLING_SERVER_EXEC` accepts `--cmd "<command>"` and returns the remote command output.

## Remote Privacy Check

Remote sampling jobs should not create image files. Check the latest remote job dir and remote `ComfyUI/output`:

```bash
find /home/user/remote_ComfyUI/jobs -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp'
find /home/user/remote_ComfyUI/ComfyUI/output -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp'
```

Expected remote job files are `pt`, `json`, `jsonl` and `txt`.

## Sampler Mismatch or Bad Images

Start with `euler/normal` for equivalence testing. Some samplers are more sensitive to local/remote ComfyUI version and platform differences. Use:

```powershell
python tools\run_sampler_parity_matrix.py --steps 4 --seed 2026070807 --output runs\sampler_parity_matrix.json
```

Treat risk-warning sampler combinations as unverified until the visual result is accepted.
