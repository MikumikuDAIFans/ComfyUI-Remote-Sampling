# Minimal Feasibility Probe Plan

## Purpose

Before claiming the upgraded workflow-level runtime can meet the final vision, these assumptions must be proven or explicitly bounded.

## High-Risk Assumptions

| Assumption | Probe | Pass Criteria | Failure Response |
|---|---|---|---|
| Fresh workflow identity prevents stale LoRA contamination. | Reuse an old clean run id with a different LoRA prompt. | `SourcePromptHashMismatch` or regeneration before latent upload. | Block release and fix identity guard. |
| Clean workflow does not inherit old remote profile LoRA. | Run clean animal workflow and inspect remote profile. | LoRA count 0 and output has no white-haired girl feature. | Block Phase 8. |
| Custom nodes can be proven on remote Linux. | Sync/import-smoke at least one real custom-node workflow. | `object_info` contains required classes or fail-closed report exists. | Add Manager/git/manual fallback or mark unsupported. |
| Resource path mirroring is reliable. | Plan real LoRA and compare local/remote relative paths. | Exact relative path match and hash/size match. | Fix path policy before real runs. |
| Workflow-level UI can remain live. | Run guarded workflow while polling status/events. | UI updates without reopening node parameters. | Fix frontend polling or backend event route. |
| Remote privacy is enforceable. | Reconstruct remote prompt and scan remote job/output. | No forbidden nodes and no image files. | Block release. |

## Probe Limits

- Low-step real runs are preferred until release validation.
- Large model transfer must record expected size and skip if already hash-matched.
- Remote commands must use the company-lab script and stay under `/home/user02/remote_ComfyUI`.
