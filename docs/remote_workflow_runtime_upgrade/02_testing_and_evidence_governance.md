# Testing And Evidence Governance

## Evidence Root

All evidence for this upgrade should be stored under:

```text
F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\evidence
```

Runtime artifacts may stay in ignored directories such as `runs/`, `jobs/`, `transfer/`, local ComfyUI output and remote job directories, but committed evidence must be summaries, hashes, screenshots when needed, and command outputs without large binary payloads.

## Governance Links

- Gate checklist: `00_preflight_governance/gate-validation-checklist.md`
- Failure template: `00_preflight_governance/failure-report-template.md`
- Completion gate template: `00_preflight_governance/stage-completion-gate-template.md`
- Cleanup template: `00_preflight_governance/evidence-cleanup-report-template.md`
- Phase start checklist: `04_phase_start_checklists/phase-start-checklists.md`
- Minimal feasibility probes: `05_minimal_feasibility_probe/minimal-feasibility-probe-plan.md`

## Required Test Types

| Test Type | Required For | Examples |
|---|---|---|
| Unit | Parsers, path mapping, hash logic, event aggregation, schema builders | `pytest` or focused Python scripts for analyzer/resource planner |
| Contract | Backend routes, JSON schemas, frontend event payloads | `/remote_workflow/runtime/plan`, `workflow_analysis.json`, `resources_plan.json` |
| Integration | Module chains | analyzer -> planner -> sync -> converter -> bridge |
| Gray | New path versus old path | old fixed workflow fail-closed; old runtime route compatibility |
| Real | Actual local/remote ComfyUI and server | clean animal, LoRA workflow, custom-node workflow |
| Zero-Short | Fresh minimal path | new workflow from scratch, no stale converted workflow, no generated profile reuse |

## Phase Test Matrix

| Phase | Unit | Contract | Integration | Gray | Real | Zero-Short |
|---|---|---|---|---|---|---|
| 0 Plan/Baseline | py_compile | status routes | existing guarded smoke | stale/fixed workflow fails | animal no white-haired girl | browser reload loads extension |
| 1 Product Shell | state/progress reducer | controller route schemas | plan/run bundle from UI | legacy entry compatibility | screenshot/live panel evidence | restart ComfyUI and reload |
| 2 Analysis | prompt/workflow fixtures | analysis schema | analyzer to planners | compare existing audit | real LoRA workflow analysis | minimal clean workflow analysis |
| 3 Resource Sync | path/hash mapping | resources/diff/sync schema | remote diff and sync | missing/hash/size mismatch | real LoRA resource sync | new bundle has no stale profile |
| 4 Custom Env | custom-node discovery | env/import schema | remote package/import smoke | install/import failure cases | real custom node workflow | clean remote custom node sync |
| 5 Identity Conversion | converter/cache functions | manifest/audit schema | full plan to conversion | old workflow/profile bypass | animal and LoRA runs | delete bundle and regenerate |
| 6 Progress/Recovery | event/status aggregation | events/report schema | simulated multi-file sync | interrupt/resume/retry | LoRA upload speed/ETA screenshot | UI explains failure |
| 7 Privacy/Fail-Closed | forbidden detector | privacy report schema | pre-upload failure path | forbidden remote image nodes | remote no-image after success | minimal workflow privacy scan |
| 8 Real Matrix | fixture reload | validation report schema | end-to-end UI guarded run | old converted workflow cannot bypass | clean/LoRA/custom-node/failure cases | new workflow from scratch |
| 9 Release/Maintenance | final py_compile | docs/schema match | final smoke | legacy/debug compatibility | final real matrix | fresh install/readme command review |

## Mandatory Real Scenarios

### Scenario A: Clean Animal Workflow

- Source: fresh local workflow with no LoRA.
- Expected:
  - `resources_plan.json` has no LoRA entries.
  - Remote prompt has `LoraLoader` count `0`.
  - Output is an animal scene, not a white-haired girl.
  - Remote job/output contains no PNG/JPG/JPEG/WEBP.

### Scenario B: Real LoRA Workflow

- Source: workflow using known LoRA under `models/loras/...`.
- Expected:
  - LoRA relative paths preserved exactly.
  - Remote LoRA list exactly matches local active LoRA list and strengths.
  - Missing or mismatched LoRA fails before latent upload.

### Scenario C: Custom Node Workflow

- Source: user-selected workflow containing at least one custom node beyond this plugin.
- Expected:
  - Custom node package is detected.
  - Remote install/sync plan is generated.
  - Remote startup/import smoke passes, or conversion fails closed with actionable command hints.

### Scenario D: Missing Resource

- Source: intentionally reference a missing LoRA or model.
- Expected:
  - Local preflight or remote resource planner fails before latent upload.
  - Error includes expected local path, expected remote path, and upload/sync suggestion.

### Scenario E: Incompatible Node

- Source: custom node that cannot be imported on Linux or has unsupported binary dependencies.
- Expected:
  - Remote environment manager marks it fatal.
  - No latent upload.
  - Failure report includes logs and next repair options.

### Scenario F: Stale Workflow/Profile Bypass

- Source: intentionally reuse an old converted workflow or old remote profile that contains a LoRA not present in the current source workflow.
- Expected:
  - Formal workflow-level run refuses stale artifacts or regenerates them from the current source hash.
  - Clean workflow remote LoRA count remains `0`.
  - Manifest records current source hash and cache decision.

### Scenario G: Long Running Sync Progress

- Source: workflow requiring at least one resource or custom node sync action.
- Expected:
  - UI shows current file/package, bytes transferred, speed, ETA or elapsed time.
  - `workflow_events.jsonl` contains ordered stage events.
  - Re-running after success skips already matching resources.

## Evidence Requirements

Each completed phase must produce:

- `phase_summary.md`
- command transcript or summarized commands
- changed file list
- test results
- known failures and resolution
- next phase gate decision

Each real run must record:

- prompt id
- run bundle id
- job id
- source prompt/workflow hash
- resource plan hash
- profile hash
- remote prompt hash
- local output path when image inspection is required
- remote no-image check output

## Failure Report Template

```md
# Failure Report

- Phase:
- Gate:
- Time:
- Command or UI action:
- Expected:
- Actual:
- Error type:
- Error message:
- Privacy boundary affected: yes/no
- Latent uploaded before failure: yes/no
- Files created:
- Root cause:
- Repair options:
- Next action:
```

## Cleanup Rules

- Do not commit model files, latents, generated images, runtime jobs, transfer archives or remote logs with secrets.
- Keep runtime evidence summaries small and text-based.
- Remove temporary tar archives after remote sync unless needed for an active failure investigation.
- Before release, run `git status --short --untracked-files=all` and confirm only intended docs/code are staged.
