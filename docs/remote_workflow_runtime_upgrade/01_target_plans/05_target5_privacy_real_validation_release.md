# Target 5: Privacy, Real Validation And Release

## Goal

Ship the workflow-level runtime as a publicly maintainable plugin with verified privacy.

## Acceptance

- Remote prompt reconstruction contains no RGB image load/decode/preview/save nodes.
- Remote job directories and remote `ComfyUI/output` contain no PNG/JPG/JPEG/WEBP for runtime jobs.
- Real validation matrix covers clean animal, LoRA, custom-node, missing-resource, incompatible-node and stale-bypass cases.
- README, usage, conversion rules and troubleshooting describe the new product shape.
- Final review, commit, push and GitHub remote head verification are complete.

## Tests

| Type | Required Test |
|---|---|
| Unit | Forbidden remote node detector and no-image scanner helpers. |
| Contract | Privacy report and release manifest schema. |
| Integration | End-to-end local UI -> remote sampling -> local decode/save. |
| Gray | Forbidden image node injection and stale workflow/profile bypass. |
| Real | Final clean animal, LoRA and custom-node validations. |
| Zero-Short | Fresh workflow from scratch and README command review. |
