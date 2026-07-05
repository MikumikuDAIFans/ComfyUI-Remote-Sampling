# Phase Start Checklists

Each phase must satisfy its checklist before implementation work continues.

## Shared Checklist

- Read `plan-manifest.md`, `00_master_goal_index.md`, task book, testing governance and this checklist.
- Record `git status --short --untracked-files=all`.
- Create or verify the phase evidence directory.
- Confirm no unresolved P0/P1 from the previous phase.
- Confirm remote write scope remains `/home/user02/remote_ComfyUI`.
- Confirm runtime artifacts and secrets will not be staged.

## Phase-Specific Checks

| Phase | Additional Start Gate |
|---|---|
| 0 | Local/remote ComfyUI paths and GitHub remote are known. |
| 1 | Frontend extension loading mechanism is understood and restart path is available. |
| 2 | Source workflow and prompt examples are available. |
| 3 | Local model roots and remote model roots are configured. |
| 4 | User approves any network dependency install beyond local package upload. |
| 5 | Converter scope and unsupported-node fail policy are frozen. |
| 6 | UI progress expectations and persisted event schema are frozen. |
| 7 | Forbidden remote image node list is frozen for this wave. |
| 8 | Real clean, LoRA and custom-node workflows are selected. |
| 9 | All required real validation evidence exists or has approved waiver. |

## Failure Handling

If a start gate fails, write a failure report using `../00_preflight_governance/failure-report-template.md` and stop that phase.
