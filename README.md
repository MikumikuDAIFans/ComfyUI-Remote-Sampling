# ComfyUI Remote Sampling

This project contains a ComfyUI custom node prototype that offloads the sampling stage to a remote Linux server while keeping image encode/decode on the local machine.

The intended privacy boundary is:

- local machine: image input, VAE encode, VAE decode, final image save
- remote server: model loading, LoRA loading, latent sampling, latent transfer
- remote server should not read or save RGB input/output images for remote sampling jobs

The custom node package is in `ComfyUI-Remote-Sampling`.

## Main Components

- `Remote_Sampling_local`: local ComfyUI node that receives conditioning, latent and sampler parameters, submits a remote sampling job, downloads the output latent, and returns `LATENT`.
- `Remote_Sampling_remote`: remote ComfyUI node that performs sampling and writes progress/status data for the local bridge.
- `tools/remote_sampling_job_cli.py`: bridge CLI for preflight checks, latent upload/download, remote prompt submission, progress polling, reports and remote service locking.
- `tools/convert_ksampler_to_remote_sampling.py`: workflow converter that replaces `KSampler` nodes with `Remote_Sampling_local` and can generate remote profiles.

## Current Monitoring Features

Each job can produce:

- `status.json`
- `events.jsonl`
- `remote_sampling_report.txt`
- transfer metrics for upload/download speed
- remote sampling progress with `step`, `steps`, `percent`, elapsed time and ETA

The local node keeps its first output as `LATENT` for workflow compatibility.

## Resource Preflight

Before uploading latent inputs, the bridge checks the remote profile resources:

- UNET
- CLIP
- LoRA

If resources are missing, the job fails before latent upload and reports expected remote paths plus upload command hints.

## Remote Service Locking

Remote sampling on the default port `8197` is protected by a remote lock directory:

```text
/home/user02/remote_ComfyUI/locks/remote_sampling_port_8197.lock
```

This prevents overlapping bridge jobs from reusing and killing the same temporary remote ComfyUI process mid-sampling.

## Usage

See:

- `docs/remote_sampling_usage.md`
- `docs/remote_sampling_workflow_conversion_rules.md`
- `docs/plan.md`

Development notes, task books and goal prompts are collected in `docs/`.

## Environment-Specific Defaults

The committed paths are examples from the original development environment.
They are safe to publish, but most users should replace them before running the
tools. The main configurable values are:

```text
REMOTE_SAMPLING_PROJECT_ROOT       local project root used by the ComfyUI node
REMOTE_SAMPLING_BRIDGE_PYTHON      Python executable used to launch the bridge CLI
REMOTE_SAMPLING_SERVER_EXEC        SSH/tunnel helper script used by the lab tools
REMOTE_SAMPLING_REMOTE_BASE        remote project root, for example /home/user02/remote_ComfyUI
REMOTE_SAMPLING_REMOTE_PYTHON      remote Python interpreter inside the ComfyUI venv
REMOTE_SAMPLING_REMOTE_PORT        remote ComfyUI sampling service port, default 8197
REMOTE_SAMPLING_TMUX_SESSION       tmux session name for the managed remote service
REMOTE_SAMPLING_LOCAL_COMFY_ROOT   local ComfyUI root for decode/helper scripts
REMOTE_SAMPLING_LOCAL_COMFY_MODELS local ComfyUI models directory for preflight hints
REMOTE_SAMPLING_LOCAL_LORA_ROOT    local LoRA root used by the workflow converter
REMOTE_SAMPLING_REMOTE_JOB_ROOT    remote job root used by Remote_Sampling_remote
```

The node UI also exposes `project_root`, `python_executable`,
`remote_profile`, `timeout_sec` and `sampler_id`, so common local path changes
can be made directly in ComfyUI without editing Python files.

This repository intentionally excludes runtime jobs, latent files, model archives, generated images, local logs and credentials via `.gitignore`.
