# Phase 4 Discovery And SSH Evidence

- Date: `2026-07-06`

## Implemented

- `ComfyUI-Remote-Sampling/custom_node_planner.py`
  - Adds discovery metadata for text-scan matches.
  - Detects equal-score ambiguous package matches.
  - Fails closed with `CustomNodePackageAmbiguous` instead of silently choosing a package.

- `tools/generic_ssh_exec.py`
  - Adds a public `--cmd` executor compatible with scripts that use `REMOTE_SAMPLING_SERVER_EXEC`.
  - Uses OpenSSH command-line configuration through environment variables.

- `.env.example`
  - Documents company-lab helper as option A.
  - Documents generic SSH executor as option B.

## Validation

Python syntax:

```text
python -m py_compile ComfyUI-Remote-Sampling\custom_node_planner.py tools\generic_ssh_exec.py
```

Ambiguous discovery fixture:

```json
{
  "fatal": true,
  "error_type": "CustomNodePackageAmbiguous",
  "candidate_count": 2
}
```

Generic SSH unconfigured failure:

```text
Set REMOTE_SAMPLING_SSH_TARGET or REMOTE_SAMPLING_SSH_HOST.
exit_code: 1
```

## Archived Artifacts

- `fixture_comfy/`
- `ambiguous_discovery_plan.json`
