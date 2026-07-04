# Remote Workflow Runtime Upgrade

This directory is the canonical planning system for repositioning `ComfyUI-Remote-Sampling` from a single remote sampler custom node into a workflow-level remote runtime plugin.

## Canonical Files

- `plan-manifest.md`: file index, gates, and execution state.
- `00_master_goal_index.md`: product target, scope, safety boundaries, and phase map.
- `01_remote_workflow_runtime_upgrade_task_book.md`: canonical long task book and progress ledger.
- `02_testing_and_evidence_governance.md`: required tests, evidence paths, failure handling, and cleanup rules.
- `03_goal_prompt.md`: executable `/goal` prompt for a future implementation session.

## Current Status

- Execution readiness: `drafting`
- Current active phase: `Phase 0: Baseline Freeze And Architecture Preflight`
- Next action: review this plan with the user, then mark it `approved for execution` before implementation starts.

## Design North Star

The system should become a workflow-level plugin:

```text
local original workflow
  -> enable remote workflow runtime
  -> analyze workflow
  -> align local/remote resources
  -> sync models, LoRA and custom nodes
  -> convert samplers to remote samplers
  -> execute remote latent-only sampling
  -> return latent to local decode/save
```

The remote server remains a compute resource. It must not read or save RGB input/output images for remote workflow runtime jobs.
