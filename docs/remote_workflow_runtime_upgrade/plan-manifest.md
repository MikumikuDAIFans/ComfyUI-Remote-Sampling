# Plan Manifest

## Metadata

- Plan ID: `remote-workflow-runtime-upgrade`
- Version: `v1`
- Created: `2026-07-04`
- Last updated: `2026-07-05 04:08 +08:00`
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

## Change Control

- Any change that weakens the privacy boundary requires explicit user approval.
- Any change that writes outside `/home/user02/remote_ComfyUI` on the remote server requires explicit user approval.
- Any change that breaks the first `LATENT` output of `Remote_Sampling_local` requires explicit user approval.
- Any expansion to support complex custom nodes must first add fail-closed analysis and tests.
- Runtime artifacts under `runs/`, `jobs/`, `transfer/`, generated images, latents, logs, and models must not be committed.

## Current State

- Latest known commit before this plan: `ff1df3d Add runtime workflow conversion runner`
- Latest known GitHub remote head before this plan: `ff1df3df4dd32530299ef6d9264953cde26a0e39`
- Current implementation already supports runtime convert-and-queue for simple KSampler workflows.
- Current implementation does not yet provide full workflow-level resource synchronization or custom node installation management.
- Current execution state: Phase 0 through Phase 7 current supported scope passed with guarded backend `/run`; Phase 8 final checks, commit and push are next.
