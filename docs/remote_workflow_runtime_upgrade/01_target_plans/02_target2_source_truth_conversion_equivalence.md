# Target 2: Source Truth And Conversion Equivalence

## Goal

Every formal run must be generated from the current local workflow and prompt.

## Acceptance

- Source workflow hash and source prompt hash are written to manifest.
- Reusing a `run_id` with a changed prompt/workflow fails with an identity mismatch.
- Clean workflow remote profile LoRA count is zero.
- LoRA workflow remote profile LoRA list exactly matches the local active LoRA list.
- Remote prompt/profile are rebuilt or strictly cache-validated for each run.

## Tests

| Type | Required Test |
|---|---|
| Unit | Hashing, cache key and profile reconstruction. |
| Contract | Manifest contains all required hash fields. |
| Integration | analyzer -> resource planner -> environment -> conversion chain. |
| Gray | Old converted workflow/profile bypass attempt fails. |
| Real | Clean animal and LoRA workflow runs. |
| Zero-Short | Delete old bundles and run from current canvas. |
