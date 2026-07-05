# Master Goal Index

## Final Target

Reposition `ComfyUI-Remote-Sampling` as a workflow-level remote runtime plugin rather than a single custom sampling node.

## Planning Mode

This upgrade is governed as a Full Mode lifecycle/construction plan. The canonical progress ledger is `01_remote_workflow_runtime_upgrade_task_book.md`; the supporting governance files define target acceptance, phase start gates, evidence policy, MVP probes, failure handling and release gates.

The desired v2 user experience:

1. User opens a fresh local ComfyUI workflow.
2. The workflow may contain custom nodes, LoRA, base models, CLIP, VAE and other model resources.
3. User clicks an explicit workflow-level control such as `Enable Remote Workflow Runtime` or `Run With Remote Runtime`.
4. The plugin verifies that the local workflow is valid and locally runnable enough to be a trustworthy source.
5. The plugin analyzes the workflow and builds an execution/resource plan.
6. Required models, LoRA and custom nodes are aligned between local and remote.
7. The local workflow is visually and functionally converted so sampler nodes become remote sampler nodes, without requiring the user to manually maintain a separate latent-only remote workflow.
8. The remote workflow is rebuilt from the same source facts, not from stale converted workflows.
9. Remote sampling runs only after resource and environment alignment pass for the current source workflow hash.
10. Remote server only handles latent sampling and latent transfer. Local machine keeps RGB image input, decode and final save.

## In Scope

- Workflow-level frontend runtime panel and control flow, including live or near-live stage progress.
- Local workflow validity preflight before conversion.
- Workflow analyzer for samplers, model chain, CLIP, VAE, LoRA, custom nodes and unsupported nodes.
- Resource resolver for model/LoRA/custom-node alignment.
- Relative-path mirroring for model directories, especially LoRA managed by LoRA Manager.
- Remote resource preflight before latent upload.
- Custom node sync strategy:
  - first package and upload local custom node folder,
  - install remote dependencies,
  - run remote startup/import smoke,
  - fallback to ComfyUI Manager/git install where possible,
  - fail closed if Linux compatibility cannot be proven.
- Runtime conversion that creates run bundles with source workflow, source prompt, converted prompt, remote execution plan, profile snapshots, audit and manifest.
- Clear workflow-level UI progress for long-running sync/conversion/remote execution.
- Fresh conversion identity guard and strict cache policy.
- Failure recovery, retry/resume, audit reports, and maintenance regression matrix.
- Full test matrix covering unit, contract, integration, gray, real and Zero-Short validation.

## Out Of Scope For The First Implementation Wave

- Fully general conversion of every ComfyUI custom node.
- Blindly executing unknown custom nodes remotely without compatibility proof.
- Remote VAE decode, `PreviewImage`, `SaveImage`, or any remote RGB image output for runtime jobs.
- Automatic downloading of large public models from arbitrary URLs without a trusted source policy.
- Solving latent privacy or prompt semantic privacy beyond the current latent-only boundary.

## Non-Negotiable Safety Boundaries

- Remote must not read local RGB input images.
- Remote must not save RGB output images.
- Remote job directories and remote `ComfyUI/output` must not contain PNG/JPG/JPEG/WEBP for runtime jobs.
- Local and remote model/LoRA relative paths must align.
- Resource mismatch must fail before latent upload.
- Unsupported or unverified custom nodes must fail closed.
- Stale converted workflows must not be used as formal execution sources.
- `Remote_Sampling_local` first output remains `LATENT`.

## Phase Map

| Phase | Name | Goal |
|---|---|---|
| 0 | Plan Approval And Baseline Re-Freeze | Freeze the current implementation and v1 evidence as a trustworthy baseline before v2 execution. |
| 1 | Workflow-Level Product Shell | Make workflow-level UI/backend the primary product entry, with status, reports and run bundles. |
| 2 | Source Workflow Validity And Analysis | Prove the local workflow is the trustworthy source and extract all dependency facts. |
| 3 | Resource Sync And Path Mirror | Align models, LoRA, VAE, CLIP and other resources by relative path before sampling. |
| 4 | Custom Node Environment Manager | Sync/install custom nodes and prove Linux import/startup compatibility or fail closed. |
| 5 | Fresh Conversion And Identity Guard | Rebuild converted prompts/profiles per run or use only strict hash-matched cache. |
| 6 | Orchestration, Progress And Recovery | Provide observable, retryable, diagnosable sync/conversion/sampling execution. |
| 7 | Privacy And Fail-Closed Hardening | Turn privacy and pre-upload failure rules into tested system constraints. |
| 8 | Real Workflow Validation Matrix | Prove clean, LoRA, custom-node and failure workflows behave correctly with evidence. |
| 9 | Productization, Release And Maintenance | Ship documentation, review, release readiness and maintenance regression matrix. |

## Completion Definition

The plan is complete only when:

- A user can open a new local workflow and enable remote workflow runtime from a workflow-level UI.
- The system can analyze the workflow and explain exactly what will run locally and remotely.
- Missing models, LoRA, custom nodes or dependencies are detected before remote sampling starts.
- Required LoRA/model files are mirrored to the same relative remote model path.
- Custom nodes are either proven installed/compatible on Linux or block conversion with actionable diagnostics.
- Remote converted prompt and profile snapshots are rebuilt per run.
- UI shows each major stage and progress instead of hiding long synchronization behind a single busy state.
- UI does not require reopening parameter details to see updated workflow-level state.
- Clean animal workflow remains clean and does not load old character LoRA.
- Real LoRA workflow loads exactly the intended LoRA.
- At least one custom-node workflow passes or fails closed with clear evidence.
- Remote privacy boundary is verified after real runs.
- The final repository state is reviewed, committed, pushed, and ready for follow-up maintenance.
