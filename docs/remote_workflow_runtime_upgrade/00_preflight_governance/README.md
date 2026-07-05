# Preflight Governance

This directory turns the workflow runtime upgrade into a gated construction system.

## Canonical Rule

The existing files in `docs/remote_workflow_runtime_upgrade` remain canonical. This directory adds the missing governance layer required before continuing long-running implementation:

- gate validation checklist
- change control
- risk and authorization policy
- failure report template
- stage completion gate template
- evidence cleanup policy

Runtime evidence stays under `evidence/`. Runtime artifacts under `runs/`, `jobs/`, `transfer/`, models, latents, images and logs must not be committed.
