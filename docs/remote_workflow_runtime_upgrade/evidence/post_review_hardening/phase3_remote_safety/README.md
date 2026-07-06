# Phase 3 Remote Safety Evidence

- Date: `2026-07-06`

## Implemented

- `tools/remote_comfy_service.py`
  - Adds owner token metadata at `/home/user02/remote_ComfyUI/locks/remote_comfy_service_8197.owner.json`.
  - `start` refuses to replace an existing tmux session unless owner token matches.
  - `stop` refuses broad `pkill`; it only stops the owned tmux session and reports remaining listeners fail-closed.
  - `status` reports owner metadata.

- `tools/sync_remote_custom_nodes.py`
  - Validates `remote_path` under `/home/user02/remote_ComfyUI/ComfyUI/custom_nodes`.
  - Validates archive destination under `/home/user02/remote_ComfyUI/transfer/custom_nodes`.
  - Adds `--dry-run`.
  - Backs up an existing remote custom node directory before replacement.

## Validation

Python syntax:

```text
python -m py_compile tools\remote_comfy_service.py tools\sync_remote_custom_nodes.py
```

Unsafe path fail-closed:

```json
{
  "UnsafeExit": 1,
  "SafeExit": 0,
  "UnsafeHasEscapes": true,
  "SafeReport": true
}
```

Remote service status:

```json
{
  "session": "remote-comfyui-8197",
  "port": 8197,
  "tmux_running": false,
  "port_listeners": [],
  "api_ready": false,
  "owner": null
}
```

Remote service empty stop:

```json
{
  "ok": true,
  "changed": false,
  "session": "remote-comfyui-8197",
  "port": 8197,
  "remaining_listeners": []
}
```

## Archived Artifacts

- `unsafe_custom_nodes_plan.json`
- `unsafe_path_fail_closed.txt`
- `safe_custom_nodes_plan.json`
- `safe_dry_run_report.json`
- `safe_dry_run_stdout.txt`
