# Target 3: Resource And Custom Node Alignment

## Goal

Align required models, LoRA, VAE, CLIP and custom nodes before latent upload.

## Acceptance

- Resource plan records local path, relative path, remote path, size/hash and sync action.
- LoRA Manager directory structure under `models/loras` is mirrored by relative path.
- Custom nodes are packaged from local, uploaded to remote, dependencies planned, and import-smoked.
- Missing or incompatible resources fail before latent upload with actionable hints.
- Network install fallback is documented and gated by trust policy.

## Tests

| Type | Required Test |
|---|---|
| Unit | Path normalization, resource hashing, custom node discovery. |
| Contract | `resources_plan.json`, `resources_diff.json`, `custom_nodes_plan.json`, environment report schemas. |
| Integration | Remote diff/sync/import smoke through company-lab script. |
| Gray | missing, size mismatch, hash mismatch, incompatible custom node. |
| Real | Real LoRA and real custom-node workflow. |
| Zero-Short | Remove a remote package/resource and prove re-plan/re-sync behavior. |
