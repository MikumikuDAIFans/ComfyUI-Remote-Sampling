# Change Control Governance

## When To Replan

Replanning is required when any of these facts changes:

- The privacy boundary would move, especially remote RGB input/output handling.
- `Remote_Sampling_local` interface compatibility would change.
- The conversion model expands beyond currently supported sampler/model chains.
- Custom node installation starts executing untrusted network code.
- Remote write scope needs anything outside `/home/user02/remote_ComfyUI`.
- Real validation reveals stale workflow/profile contamination.

## Change Record Requirements

Each major change must record:

- reason
- affected files
- affected phases and gates
- new tests required
- old evidence that remains valid
- old evidence that is invalidated
- rollback or fail-closed behavior

## Cache Policy

Fresh runtime conversion is the default. Cache may only be used when all identity inputs match:

- source workflow hash
- source prompt hash
- analysis hash
- resource plan hash
- remote environment report hash
- converter version
- custom node planner version

Any mismatch must regenerate the bundle or fail before latent upload.
