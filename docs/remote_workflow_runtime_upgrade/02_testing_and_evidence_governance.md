# Testing And Evidence Governance

## Evidence Root

All evidence for this upgrade should be stored under:

```text
F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\evidence
```

Runtime artifacts may stay in ignored directories such as `runs/`, `jobs/`, `transfer/`, local ComfyUI output and remote job directories, but committed evidence must be summaries, hashes, screenshots when needed, and command outputs without large binary payloads.

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
| 0 Baseline | py_compile | runtime status route | existing runtime smoke | fixed workflow fails | animal no white-haired girl | browser reload loads extension |
| 1 Controller | state reducer | controller route schemas | plan bundle from UI | old entry compatibility | screenshot of new UI | restart ComfyUI and reload |
| 2 Analyzer | prompt/workflow fixtures | analysis schema | analyzer to planner | compare existing audit | real LoRA workflow analysis | minimal clean workflow analysis |
| 3 Resource Planner | path/hash mapping | resources schema | remote path diff | missing/hash mismatch cases | Aella/xcn plan | new bundle has no stale profile |
| 4 Remote Env | custom-node discovery | env report schema | remote install smoke | install failure cases | real custom node workflow | clean remote custom node sync |
| 5 Conversion | converter functions | manifest/audit schema | full plan to conversion | compare old/new outputs | animal and LoRA runs | delete bundle and regenerate |
| 6 Progress | event/status aggregation | events schema | simulated multi-file sync | interrupt/resume | LoRA upload speed/ETA | UI explains failure |
| 7 Real Matrix | fixture reload | validation report schema | end-to-end UI run | old workflow cannot bypass | clean/LoRA/custom-node | new workflow from scratch |
| 8 Release | py_compile | docs/schema match | final smoke | old entry compatibility | final real runs | fresh install/readme review |

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
