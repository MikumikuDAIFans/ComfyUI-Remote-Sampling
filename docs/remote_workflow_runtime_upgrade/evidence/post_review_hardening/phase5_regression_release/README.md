# Phase 5 Regression And Release Evidence

- Date: `2026-07-06`
- Final smoke run ID: `workflow_runtime_20260706_210616_4c166176`
- Final smoke prompt ID: `915a527a-d635-4af3-82b1-c7ad4462c149`
- Final smoke remote job ID: `remote_sampling_20260706_210647_5ac17556_workflow_workflow_runtime_20260706_210616_4c166176_500`

## Automated Validation

```text
python -m py_compile ComfyUI-Remote-Sampling\workflow_runtime.py ComfyUI-Remote-Sampling\__init__.py ComfyUI-Remote-Sampling\custom_node_planner.py tools\remote_comfy_service.py tools\sync_remote_custom_nodes.py tools\generic_ssh_exec.py tests\test_post_review_hardening.py
node --check ComfyUI-Remote-Sampling\web\remote_workflow_runtime.js
python -m unittest discover -s tests -p test_post_review_hardening.py -v
git diff --check
```

Result:

```text
Ran 4 tests
OK
```

## Final Smoke

The final smoke started from the source `KSampler` workflow:

```text
workflows\runs\remote_sampling_converter_source_20260630_1755_api.json
```

Observed result:

```json
{
  "stage": "complete",
  "fatal": false,
  "backend_observed_terminal": true,
  "sampling": {
    "step": 4,
    "steps": 4,
    "elapsed_sec": 2.887
  },
  "upload_bytes": 225018,
  "download_bytes": 394786,
  "total_elapsed_sec": "90.425"
}
```

After syncing the `run_status` race fix and restarting local ComfyUI, the existing final smoke run was still readable:

```json
{
  "ok": true,
  "stage": "complete",
  "read_errors": []
}
```

## Remote Privacy Check

Remote check searched the final job directory and recent remote `ComfyUI/output` for PNG/JPG/JPEG/WEBP files.

Observed output:

```text
locks
__exit_status=0
```

No remote image files and no residual `8197` listener were reported.
