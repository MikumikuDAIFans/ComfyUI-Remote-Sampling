# Target 1: Workflow-Level Product Entry

## Goal

Reposition the system from a single node helper to a workflow-level remote runtime plugin.

## Acceptance

- ComfyUI frontend exposes a workflow-level entry for plan/convert/run.
- Backend routes expose status, plan, run, run_status and client_event contracts.
- UI displays run id, stage, percent, recent events and repair hints.
- Legacy node behavior remains compatible.

## Tests

| Type | Required Test |
|---|---|
| Unit | UI state reducer and status aggregation. |
| Contract | Route schemas for status/plan/run/run_status/client_event. |
| Integration | Current canvas creates a run bundle. |
| Gray | Legacy remote sampling node still works for existing workflows. |
| Real | Browser screenshot of workflow runtime panel and running status. |
| Zero-Short | Restart local ComfyUI, reload browser, confirm extension loads. |
