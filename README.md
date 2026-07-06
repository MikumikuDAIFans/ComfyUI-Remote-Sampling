# ComfyUI Remote Workflow Runtime

This project is evolving from a single remote-sampling custom node into a workflow-level ComfyUI plugin. Its purpose is to run the sampling stage on a remote Linux server while keeping image input, VAE encode/decode, workflow editing, WebUI interaction, and final image output on the local machine.

The intended privacy boundary is:

- local machine: image input, VAE encode, VAE decode, final image save
- remote server: model loading, LoRA loading, latent sampling, latent transfer
- remote server should not read or save RGB input/output images for remote sampling jobs

The plugin package is in `ComfyUI-Remote-Sampling`.

The recommended user-facing entry is the local ComfyUI floating panel:

- `Plan Current Workflow`: analyze the current graph, list model/LoRA/custom-node dependencies, and create an audit bundle without queueing.
- `Convert`: generate a fresh per-run converted prompt and remote execution plan without queueing.
- `Run Guarded`: create a fresh workflow runtime plan, poll `workflow_status.json` / `workflow_events.jsonl` while backend guards run, check/sync remote resources and custom nodes, run dependency planning and remote import smoke, perform runtime conversion, then ask the backend watcher to queue and monitor the converted prompt.

Do not use old converted workflow files as the formal entry point. The workflow-level path is designed to convert from the current source prompt for every run, preventing stale LoRA/profile contamination.

If a frontend or script reuses an existing workflow `run_id`, the supplied source prompt/workflow hash must match the run bundle manifest. A mismatch fails in local preflight with `SourcePromptHashMismatch` or `SourceWorkflowHashMismatch`; the system will not proceed to remote resource checks, conversion, latent upload, or sampling.

Local output nodes such as `VAEDecode` and `SaveImage` are allowed to remain in the local converted prompt. The privacy gate checks the generated remote sampling profile/prompt instead. If a remote profile would construct `LoadImage`, `VAEEncode`, `VAELoader`, `VAEDecode`, `PreviewImage`, or `SaveImage`, conversion fails with `RemotePromptForbiddenImageNodes`.

## Main Components

- `Remote_Sampling_local`: local ComfyUI node that receives conditioning, latent and sampler parameters, submits a remote sampling job, downloads the output latent, and returns `LATENT`.
- `Remote_Sampling_remote`: remote ComfyUI node that performs sampling and writes progress/status data for the local bridge.
- `workflow_runtime.py`: workflow-level planner/converter routes for the floating panel.
- `workflow_analyzer.py`: extracts samplers, model chains, CLIP, VAE, LoRA, unsupported nodes, and custom node classes from the current API prompt.
- `resource_planner.py`: maps local model/LoRA/CLIP/VAE resources to mirrored remote paths.
- `custom_node_planner.py`: maps workflow custom node classes to local packages and remote `custom_nodes` targets.
- `tools/remote_sampling_job_cli.py`: bridge CLI for preflight checks, latent upload/download, remote prompt submission, progress polling, reports and remote service locking.
- `tools/convert_ksampler_to_remote_sampling.py`: workflow converter that replaces `KSampler` nodes with `Remote_Sampling_local` and can generate remote profiles.
- `tools/check_remote_resource_plan.py`: checks planned model resources on the remote server.
- `tools/check_remote_custom_nodes_plan.py`: checks planned custom node packages on the remote server.
- `tools/sync_remote_custom_nodes.py`: archives local custom node packages and extracts them under remote `ComfyUI/custom_nodes` with path sandbox validation, dry-run reporting and backup-before-replace.
- `tools/generic_ssh_exec.py`: generic OpenSSH command executor compatible with `REMOTE_SAMPLING_SERVER_EXEC` for public non-lab deployments.
- `tools/sync_remote_resources.py`: uploads model/LoRA resources that are missing remotely.
- `tools/install_remote_custom_node_dependencies.py`: builds or executes remote dependency install commands. Default mode is dry-run.
- `tools/remote_custom_node_import_smoke.py`: starts remote ComfyUI when needed and checks `object_info` for required custom node classes.

## Current Monitoring Features

Each job can produce:

- `status.json`
- `events.jsonl`
- `remote_sampling_report.txt`
- transfer metrics for upload/download speed
- remote sampling progress with `step`, `steps`, `percent`, elapsed time and ETA

Workflow-level runs also produce:

- `workflow_status.json`
- `workflow_events.jsonl`
- `workflow_runtime_report.txt`

The frontend reads `/remote_workflow/runtime/run_status?run_id=...&project_root=...` while `Run Guarded` is preparing and executing a workflow. The backend watcher owns prompt queueing and terminal state updates, so `workflow_status.json`, `workflow_events.jsonl` and `workflow_runtime_report.txt` still reach `complete` or `failed` if the browser is refreshed after queue submission.

The local node keeps its first output as `LATENT` for workflow compatibility.

## Resource Preflight

Before uploading latent inputs, the system checks resources in two layers:

- workflow-level planning records required resources and remote targets
- node-level bridge preflight checks the remote profile before latent upload

- UNET
- CLIP
- VAE in workflow-level planning
- LoRA

If resources are missing, the job fails before latent upload and reports expected remote paths plus upload command hints.

Model and LoRA paths are mirrored by relative path, for example:

```text
local:  ComfyUI/models/loras/Anima/角色/example.safetensors
remote: /home/user02/remote_ComfyUI/ComfyUI/models/loras/Anima/角色/example.safetensors
```

## Workflow-Level Guardrails

The workflow runtime is fail-closed by default:

- missing local model/LoRA resources block conversion
- unsupported model or CLIP chains block conversion
- missing remote model/LoRA resources are uploaded before queueing when auto-sync is enabled
- remote custom node packages are checked/synced before queueing
- custom node dependency commands are recorded; actual pip install requires explicit approval
- remote ComfyUI import smoke must find required custom node classes in `object_info`
- ambiguous custom node package discovery fails closed instead of silently choosing a package
- fixed debug profiles such as `anima_qwen_aella_xcn` are refused unless explicitly allowed
- remote RGB image nodes remain forbidden for remote sampling jobs
- each workflow run writes a fresh bundle under `runs/workflow_runtime_<timestamp>_<id>`
- converted prompts and profile snapshots are hashed and tied to the source prompt hash

Current supported conversion scope is intentionally narrow: base `KSampler`, `UNETLoader`, `CLIPLoader`, `VAELoader`, `LoraLoader`, and `Lora Loader (LoraManager)`. Complex ControlNet/IPAdapter/AnimateDiff/custom sampler flows should fail closed until explicitly supported.

## Remote Service Locking

Remote sampling on the default port `8197` is protected by a remote lock directory:

```text
/home/user02/remote_ComfyUI/locks/remote_sampling_port_8197.lock
```

This prevents overlapping bridge jobs from reusing and killing the same temporary remote ComfyUI process mid-sampling.

The managed remote ComfyUI service also writes an owner token under:

```text
/home/user02/remote_ComfyUI/locks/remote_comfy_service_8197.owner.json
```

`tools/remote_comfy_service.py stop` only stops an owned tmux session. It no longer uses broad `pkill` as a fallback.

## Usage

See:

- `docs/remote_sampling_usage.md`
- `docs/remote_sampling_workflow_conversion_rules.md`
- `docs/plan.md`

Development notes, task books and goal prompts are collected in `docs/`.

The long-running workflow-runtime upgrade plan and evidence are in:

```text
docs/remote_workflow_runtime_upgrade/
```

## Environment-Specific Defaults

The committed paths are examples from the original development environment.
They are safe to publish, but most users should replace them before running the
tools. The main configurable values are:

```text
REMOTE_SAMPLING_PROJECT_ROOT       local project root used by the ComfyUI node
REMOTE_SAMPLING_BRIDGE_PYTHON      Python executable used to launch the bridge CLI
REMOTE_SAMPLING_SERVER_EXEC        SSH/tunnel command executor; can be the lab helper or tools/generic_ssh_exec.py
REMOTE_SAMPLING_SSH_TARGET         generic SSH target, for example user@example.com
REMOTE_SAMPLING_SSH_PORT           generic SSH port
REMOTE_SAMPLING_SSH_KEY            generic SSH private key path
REMOTE_SAMPLING_REMOTE_BASE        remote project root, for example /home/user02/remote_ComfyUI
REMOTE_SAMPLING_REMOTE_PYTHON      remote Python interpreter inside the ComfyUI venv
REMOTE_SAMPLING_REMOTE_PORT        remote ComfyUI sampling service port, default 8197
REMOTE_SAMPLING_TMUX_SESSION       tmux session name for the managed remote service
REMOTE_SAMPLING_LOCAL_COMFY_ROOT   local ComfyUI root for decode/helper scripts
REMOTE_SAMPLING_LOCAL_COMFY_MODELS local ComfyUI models directory for preflight hints
REMOTE_SAMPLING_LOCAL_LORA_ROOT    local LoRA root used by the workflow converter
REMOTE_SAMPLING_REMOTE_JOB_ROOT    remote job root used by Remote_Sampling_remote
REMOTE_SAMPLING_SERVICE_OWNER      owner token for managed remote ComfyUI service
REMOTE_SAMPLING_REMOTE_CUSTOM_NODES_ROOT path sandbox root for custom node sync
REMOTE_SAMPLING_REMOTE_TRANSFER_ROOT path sandbox root for custom node archives
```

The workflow runtime panel exposes `Runtime Config` for `project_root`,
`python_executable`, `local_comfy_api`, `timeout_sec`, `remote_executor` and
`remote_profile`. The node UI also exposes node-level `project_root`,
`python_executable`, `remote_profile`, `timeout_sec` and `sampler_id`, so common
path changes can be made directly in ComfyUI without editing Python files.

This repository intentionally excludes runtime jobs, latent files, model archives, generated images, local logs and credentials via `.gitignore`.
