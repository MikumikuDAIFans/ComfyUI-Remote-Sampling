# Master Goal Index

## Final Target

Reposition `ComfyUI-Remote-Sampling` as a workflow-level remote runtime plugin rather than a single custom sampling node.

The desired user experience:

1. User opens a fresh local ComfyUI workflow.
2. The workflow may contain custom nodes, LoRA, base models, CLIP, VAE and other model resources.
3. User clicks an explicit workflow-level control such as `Enable Remote Workflow Runtime`.
4. The plugin verifies that the local workflow is valid and locally runnable enough to be a trustworthy source.
5. The plugin analyzes the workflow and builds an execution/resource plan.
6. Required models, LoRA and custom nodes are aligned between local and remote.
7. The local workflow is visually and functionally converted so sampler nodes become remote sampler nodes.
8. The remote workflow is rebuilt from the same source facts, not from stale converted workflows.
9. Remote sampling runs only after resource and environment alignment pass.
10. Remote server only handles latent sampling and latent transfer. Local machine keeps RGB image input, decode and final save.

## In Scope

- Workflow-level frontend runtime panel and control flow.
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
| 0 | Baseline Freeze And Architecture Preflight | Freeze current working behavior, constraints and evidence before large changes. |
| 1 | Workflow-Level Runtime Controller | Build the formal UI/backend entry that owns workflow-level remote enablement. |
| 2 | Local Workflow Analyzer And Preflight | Analyze source workflow and prove it is locally valid before conversion. |
| 3 | Resource Inventory And Sync Planner | Generate model/LoRA/custom-node resource plans with relative path mirroring. |
| 4 | Remote Environment Manager | Sync/install custom nodes and dependencies, then prove remote startup compatibility. |
| 5 | Runtime Conversion And Execution Plan | Convert workflow into local/remote execution plans with per-run profile snapshots and audits. |
| 6 | Sync Engine, Progress UI And Failure Recovery | Execute long-running sync/conversion/remote runs with honest progress and resumable evidence. |
| 7 | Real Workflow Validation Matrix | Prove clean, LoRA and custom-node workflows behave correctly or fail closed. |
| 8 | Productization, Docs And Release | Update positioning, usage docs, release gates, commit and push. |

## Completion Definition

The plan is complete only when:

- A user can open a new local workflow and enable remote workflow runtime from a workflow-level UI.
- The system can analyze the workflow and explain exactly what will run locally and remotely.
- Missing models, LoRA, custom nodes or dependencies are detected before remote sampling starts.
- Required LoRA/model files are mirrored to the same relative remote model path.
- Custom nodes are either proven installed/compatible on Linux or block conversion with actionable diagnostics.
- Remote converted prompt and profile snapshots are rebuilt per run.
- UI shows each major stage and progress instead of hiding long synchronization behind a single busy state.
- Clean animal workflow remains clean and does not load old character LoRA.
- Real LoRA workflow loads exactly the intended LoRA.
- At least one custom-node workflow passes or fails closed with clear evidence.
- Remote privacy boundary is verified after real runs.
