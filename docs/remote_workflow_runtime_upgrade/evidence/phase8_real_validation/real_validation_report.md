# Phase 8 Real Validation Report

- Phase: `Phase 8 Real Workflow Validation Matrix`
- Updated: `2026-07-05 13:35 +08:00`
- Result: `pass-with-boundary`
- Boundary: this report validates the current supported workflow scope. Fully general ComfyUI graph conversion remains out of scope and must fail closed when unsupported.

## Scenario Matrix

| Scenario | Result | Evidence |
|---|---|---|
| A. Clean animal workflow | pass | `../phase7_real_validation/phase_summary.md` records `guarded_clean_animal20_20260705_035631`; remote LoRA count `0`; visual check says red panda, no white-haired girl. |
| B. Real LoRA workflow | pass | `../phase7_real_validation/phase_summary.md` records `phase7_lora_smoke_20260705_004202`; remote LoRA list exactly Aella + xcn. |
| C. Custom-node workflow | pass | `custom-node-validation-matrix-20260705.md` records LoraManager and WeiLin custom classes, remote package readiness and import smoke success. |
| D. Missing resource | pass | `../phase7_privacy_fail_closed/missing-resource-fail-closed-20260705.md` records HTTP 400 `LocalResourceMissing` before resources diff, conversion or job creation. |
| E. Incompatible custom node | pass | `custom-node-validation-matrix-20260705.md` records synthetic missing class detected by remote `object_info`, fatal import smoke and no latent upload path. |
| F. Stale workflow/profile bypass | pass | `../phase7_privacy_fail_closed/stale-workflow-profile-bypass-20260705.md` records `SourcePromptHashMismatch` and no converted prompt/job. |
| G. Remote privacy | pass | Phase 6/7 evidence records successful jobs with remote job/output no PNG/JPG/JPEG/WEBP; Phase 7 privacy gate verifies reconstructed remote prompt forbidden image node count is `0` for clean profile. |

## Hash And Bundle Coverage

Successful guarded runs and prepare bundles recorded these hash classes where applicable:

- `source_prompt_sha256`
- `source_workflow_sha256`
- `workflow_analysis_sha256`
- `resources_plan_sha256`
- `resources_diff_sha256`
- `remote_environment_report_sha256`
- `remote_custom_node_dependency_install_sha256`
- `remote_custom_node_import_smoke_sha256`
- `remote_execution_plan_sha256`
- profile hash fields
- status/events/report hashes

The custom-node validation matrix specifically confirms:

```text
custom_nodes_plan_sha256: present
remote_environment_report_sha256: present
remote_custom_node_dependency_install_sha256: present
remote_custom_node_import_smoke_sha256: present
```

## Privacy Boundary

The current validated privacy boundary is:

- Local keeps RGB input, VAE encode/decode, preview/final save and WebUI editing.
- Remote receives latent and conditioning/model resources for sampling only.
- Remote generated profile reconstruction must not include `LoadImage`, `VAEEncode`, `VAELoader`, `VAEDecode`, `PreviewImage` or `SaveImage`.
- Remote job directories and remote `ComfyUI/output` must not contain runtime PNG/JPG/JPEG/WEBP files.

## Current Pass Criteria

The Phase 8 matrix is sufficient to continue to Phase 9 release readiness because:

- Clean workflow no longer inherits old role LoRA.
- LoRA workflow preserves the current active LoRA list exactly.
- Custom-node readiness is verified through remote package checks and `object_info` import smoke.
- Missing and incompatible cases fail closed before latent upload.
- Stale run/profile reuse is rejected by source hash identity guards.
- Remote image output is still forbidden and scanned after successful runs.

## Remaining Release Risks

- Complex workflow support remains intentionally bounded. Unsupported graph shapes must keep failing closed.
- Custom-node dependency installation is not allowed to silently execute unknown network code; any real install fallback needs explicit trust policy and evidence.
- Very large resource sync still needs resumability/product hardening beyond the current validated cases.
- A final Phase 9 release gate must still run current `py_compile`, JS syntax check, `git diff --check`, local route load, final smoke or justified waiver, review, commit, push and remote head verification.
