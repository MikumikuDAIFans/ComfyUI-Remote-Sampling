# Gate Validation Checklist

## Lifecycle Gates

| Gate | Required Evidence | Status Owner |
|---|---|---|
| DEV-GATE-00 Task Routed | Task type, scale mode and lifecycle path recorded in the task book. | planner |
| DEV-GATE-01 Requirements Testable | Final target, scope, out of scope and acceptance criteria are written. | planner |
| DEV-GATE-02 Baseline Trustworthy | Current commit, local ComfyUI, remote ComfyUI and v1 smoke evidence are recorded. | executor |
| DEV-GATE-03 Architecture Executable | Module boundaries, routes, bundle schema, failure policy and privacy boundary are documented. | executor |
| DEV-GATE-04 Plan Constructible | Phase task books, start checklists, testing matrix and goal prompt exist. | planner |
| DEV-GATE-05 Changes Controlled | Each implementation batch has scoped files, validation commands and rollback notes. | executor |
| DEV-GATE-06 Evidence Sufficient | Unit, contract, integration, gray, real and Zero-Short tests are recorded or explicitly waived. | executor |
| DEV-GATE-07 Review Clear | Review lists no unresolved P0/P1 issue. | reviewer |
| DEV-GATE-08 Release Ready | Docs, final smoke, commit, push and remote head verification are complete. | release owner |
| DEV-GATE-09 Maintenance Ready | Regression matrix, known limitations and next issues are recorded. | maintainer |

## Remote Runtime Product Gates

| Gate | Pass Criteria |
|---|---|
| RWR-GATE-01 Baseline Frozen | Existing clean remote sampling path can still run and remote no-image scan passes. |
| RWR-GATE-02 Local Workflow Valid | Source workflow can be treated as the only trusted source or fails locally before remote action. |
| RWR-GATE-03 Analysis Complete | Samplers, model chain, CLIP, VAE, LoRA, custom nodes and unsupported nodes are recorded. |
| RWR-GATE-04 Resource Plan Complete | Every resource has local path, relative path, remote path, size/hash and sync action. |
| RWR-GATE-05 Remote Environment Ready | Custom nodes and dependencies import on remote Linux or fail closed. |
| RWR-GATE-06 Conversion Equivalent | Converted prompt/profile come from current source hash and LoRA list matches exactly. |
| RWR-GATE-07 Privacy Holds | Remote prompt/job/output contain no RGB image input/decode/save nodes or image files. |
| RWR-GATE-08 UI Progress Honest | Workflow-level UI shows long-running stages without requiring parameter panel refresh. |
| RWR-GATE-09 Real Matrix Passes | Clean animal, LoRA, custom-node, missing-resource and stale-bypass scenarios pass. |
| RWR-GATE-10 Release Ready | Review, final validation, commit, push and remote head verification are done. |

No next phase may start while its prerequisite gate has an unresolved P0/P1 failure.
