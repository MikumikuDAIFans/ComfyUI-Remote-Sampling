# Remote Workflow Runtime Upgrade

This directory is the canonical planning system for repositioning `ComfyUI-Remote-Sampling` from a single remote sampler custom node into a workflow-level remote runtime plugin.

## Canonical Files

- `plan-manifest.md`: file index, gates, and execution state.
- `00_master_goal_index.md`: product target, scope, safety boundaries, and phase map.
- `01_remote_workflow_runtime_upgrade_task_book.md`: canonical long task book and progress ledger.
- `02_testing_and_evidence_governance.md`: required tests, evidence paths, failure handling, and cleanup rules.
- `03_goal_prompt.md`: executable `/goal` prompt for a future implementation session.
- `00_preflight_governance/`: gate checklist, change control, failure templates and risk authorization rules.
- `01_target_plans/`: target-level acceptance plans.
- `02_long_task_books/00_phase_execution_matrix.md`: compact Phase 0-9 execution matrix.
- `02_long_task_books/post_review_hardening_task_book.md`: follow-up hardening plan from the comprehensive review findings.
- `04_phase_start_checklists/`: phase start gates.
- `05_minimal_feasibility_probe/`: high-risk feasibility probes.
- `06_pre_start_readiness_review.md`: readiness review and remaining boundaries.
- `03_goal_prompt_post_review_hardening.md`: copy-ready `/goal` prompt for the follow-up hardening wave.

## Current Status

- Execution readiness: `executing`
- Current active phase: see `01_remote_workflow_runtime_upgrade_task_book.md`.
- Next action: continue incomplete Phase 7/8 real validation, then Phase 9 release readiness.
- Follow-up next action: review and approve `02_long_task_books/post_review_hardening_task_book.md` before starting the hardening wave.

## Planning Mode

This directory is now normalized as a Full Mode lifecycle/construction plan. It contains:

- lifecycle routing and phase gates
- target acceptance plans
- phase execution and start-gate matrices
- unit / contract / integration / gray / real / Zero-Short testing policy
- evidence cleanup and failure-report rules
- a copy-ready `/goal` prompt for continuing execution

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
