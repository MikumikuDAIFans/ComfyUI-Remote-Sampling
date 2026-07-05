# Phase Execution Matrix

This file is the compact phase task book index. The canonical progress ledger remains `../01_remote_workflow_runtime_upgrade_task_book.md`.

| Phase | Purpose | Deliverables | Must-Test Set | Evidence Directory |
|---|---|---|---|---|
| 0 Baseline | Freeze current system and remote state. | baseline report, commit/remote/package state | py_compile, status routes, clean smoke, no-image scan, UI reload | `evidence/phase0_baseline/` |
| 1 Product Shell | Workflow-level UI/backend entry. | routes, frontend panel, run bundle shell | UI load, route contracts, bundle creation, legacy compatibility | `evidence/phase1_controller/` |
| 2 Analyzer | Prove local workflow is trusted source. | source workflow/prompt, analysis report | fixtures, real LoRA, missing local resource fail | `evidence/phase2_analyzer/` |
| 3 Resources | Mirror model/LoRA paths and sync plan. | resources plan/diff/sync report | path/hash, remote diff, mismatch cases, real LoRA sync | `evidence/phase3_resource_planner/` |
| 4 Custom Env | Sync/install/import-smoke custom nodes. | custom node plan, dependency plan, import report | package sync, dependency dry-run, import fail/success | `evidence/phase4_remote_environment/` |
| 5 Conversion | Fresh conversion and identity guard. | converted prompt, remote plan, profiles, manifest | hash chain, LoRA exact, stale bypass | `evidence/phase5_conversion/` |
| 6 Progress | Observable orchestration and recovery. | status/events/report, UI progress | event schema, client_event, retry/resume, screenshots | `evidence/phase6_progress_recovery/` |
| 7 Privacy | Fail-closed privacy boundaries. | privacy scan, pre-upload failure reports | forbidden nodes, missing resources, remote no-image | `evidence/phase7_privacy_fail_closed/` |
| 8 Real Matrix | Prove real workflows meet target. | real validation report and screenshots | clean animal, LoRA exact, custom-node, incompatible, stale bypass | `evidence/phase8_real_validation/` |
| 9 Release | Productize and hand off. | docs, review, commit, push, maintenance matrix | final py_compile, final smoke, diff check, remote head | `evidence/phase9_release/` |

## Universal Phase Rules

- Update the canonical task book after each meaningful milestone.
- Record tests that are not applicable with a reason and replacement evidence.
- Do not advance if P0/P1 is open without explicit user authorization.
- Do not upload latent after a fatal preflight.
- Do not commit generated runtime artifacts.
