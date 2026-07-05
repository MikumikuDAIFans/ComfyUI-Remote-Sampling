# Risk And Authorization Governance

## Risk Levels

- P0: breaks privacy, corrupts workflow identity, uploads latent after fatal preflight, or blocks release.
- P1: likely breaks real workflow conversion, custom node compatibility, resource sync correctness, or UI observability.
- P2: limited scope bug with workaround and no privacy impact.
- P3: docs, polish, or low-risk maintenance.

## Requires Explicit User Authorization

- Allowing remote RGB image load, decode, preview or save.
- Writing outside `/home/user02/remote_ComfyUI` on the remote server.
- Breaking the first `LATENT` output of `Remote_Sampling_local`.
- Installing unknown code from the network on the remote server.
- Deleting or overwriting remote models or user data.

## Default Fail-Closed Cases

- Missing local model, LoRA or custom node.
- Missing remote resource after sync plan unless sync is explicitly executed and verified.
- Size/hash mismatch.
- Unsupported sampler or unclear model chain.
- Remote Linux import smoke failure.
- Stale source workflow or profile hash mismatch.
- Remote prompt reconstruction contains RGB image nodes.
