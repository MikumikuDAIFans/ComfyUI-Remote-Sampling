# Plan Manifest

## Metadata

- Plan ID: `remote-workflow-runtime-upgrade`
- Version: `v2`
- Created: `2026-07-04`
- Last updated: `2026-07-05 13:10 +08:00`
- Project root: `F:\TieguoDun\Remote_comfyui`
- Current branch: `main`
- Canonical progress file: `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\01_remote_workflow_runtime_upgrade_task_book.md`
- Execution readiness: `executing`

## File Index

| File | Purpose | Gate |
|---|---|---|
| `README.md` | Human entry point for this plan system | informational |
| `plan-manifest.md` | Plan inventory, gates, status, and change control | required |
| `00_master_goal_index.md` | Frozen target, boundaries, phases, and completion definition | required |
| `01_remote_workflow_runtime_upgrade_task_book.md` | Canonical long-running execution task book | required |
| `02_testing_and_evidence_governance.md` | Test matrix, evidence requirements, failure reports, cleanup rules | required |
| `03_goal_prompt.md` | Copy-ready `/goal` prompt for implementation | required after approval |
| `00_preflight_governance/` | Gate checklist, change control, risk authorization, failure and completion templates | required |
| `01_target_plans/` | Five acceptance-oriented target plans for the workflow-level product | required |
| `02_long_task_books/00_phase_execution_matrix.md` | Compact Phase 0-9 task book index linked to the canonical progress ledger | required |
| `04_phase_start_checklists/phase-start-checklists.md` | Phase start gates and failure handling rules | required |
| `05_minimal_feasibility_probe/minimal-feasibility-probe-plan.md` | High-risk assumption probes before release claims | required |
| `06_pre_start_readiness_review.md` | Construction readiness review and known boundaries | required |

## Gate Index

| Gate ID | Name | Pass Criteria |
|---|---|---|
| RWR-GATE-00 | Plan Approved | User has reviewed and approved this plan for execution. |
| RWR-GATE-01 | Baseline Frozen | Current working runtime, tests, remote state, and known limitations are documented. |
| RWR-GATE-02 | Local Workflow Is Valid | Source workflow can run locally or reaches a clear local preflight failure before remote conversion. |
| RWR-GATE-03 | Workflow Analysis Is Complete | Samplers, model chain, LoRA chain, VAE, custom nodes, and unsupported nodes are recorded in a manifest. |
| RWR-GATE-04 | Resource Plan Is Complete | Every required model, LoRA, custom node, and dependency has local source, remote target, hash/size, and sync policy. |
| RWR-GATE-05 | Remote Environment Is Ready | Remote custom nodes and dependencies install or fail with actionable diagnostics before latent upload. |
| RWR-GATE-06 | Runtime Conversion Is Equivalent | Converted workflow/profile/remote prompt match source workflow resources and do not reuse stale workflow artifacts. |
| RWR-GATE-07 | Privacy Boundary Holds | Remote jobs and remote `ComfyUI/output` contain no PNG/JPG/JPEG/WEBP for runtime jobs. |
| RWR-GATE-08 | UI Progress Is Honest | Workflow-level UI shows local check, analysis, resource sync, environment setup, conversion, upload, sampling, download, decode states. |
| RWR-GATE-09 | Real Workflow Validation Passes | Clean workflow, LoRA workflow, and custom-node workflow pass or fail closed with evidence. |
| RWR-GATE-10 | Release Ready | Docs, tests, review, commit, push, and remote head verification are complete. |
| RWR-GATE-11 | Maintenance Ready | Regression matrix, known limitations, issue backlog, and next release path are documented. |

## Change Control

- Any change that weakens the privacy boundary requires explicit user approval.
- Any change that writes outside `/home/user02/remote_ComfyUI` on the remote server requires explicit user approval.
- Any change that breaks the first `LATENT` output of `Remote_Sampling_local` requires explicit user approval.
- Any expansion to support complex custom nodes must first add fail-closed analysis and tests.
- Runtime artifacts under `runs/`, `jobs/`, `transfer/`, generated images, latents, logs, and models must not be committed.

## Current State

- Latest known commit before v2 plan: `ee35be7`
- Latest known GitHub remote head before v2 plan: `ee35be7f71093e3e1868c52e5a8f80573433a8df`
- Current implementation already supports guarded workflow-level planning, conversion, resource/custom-node checks, remote import smoke, and queued remote sampling for the currently supported KSampler scope.
- Current implementation still needs v2 product hardening: true workflow-level live progress, stronger resume/retry UX, formal custom-node fallback policy, broader fail-closed matrix, release/readme polish, and fresh validation evidence.
- Current execution state: v2 long-task system is executing under the active thread goal. v1 evidence remains baseline evidence, not v2 completion.
- Construction planning state: normalized into a Full Mode lifecycle/construction plan on `2026-07-05`; the canonical task book remains the progress ledger.
- Latest gate movement: Phase 9 final guarded smoke passed; release gate is `pass-with-boundary` for the current supported workflow scope. Final commit and remote head are verified by Git command output.
