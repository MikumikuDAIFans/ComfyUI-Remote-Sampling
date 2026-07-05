# Target 4: Observable Remote Execution

## Goal

Long-running workflow runtime operations must be observable and diagnosable.

## Acceptance

- Each run writes `workflow_status.json`, `workflow_events.jsonl` and `workflow_runtime_report.txt`.
- Frontend polls run status while backend stages execute.
- Queue/sampling/download completion observed from ComfyUI history is persisted through client events.
- Reports contain stage, timings, upload/download metrics, sampling step counts and repair hints.

## Tests

| Type | Required Test |
|---|---|
| Unit | Event writer/reader, metrics parser and progress aggregation. |
| Contract | status/events/report/client_event schema. |
| Integration | Plan-first polling, guarded run, queue history aggregation. |
| Gray | Failure during preflight and after queue writes coherent reports. |
| Real | Screenshot showing live stage progress and completed metrics. |
| Zero-Short | New user can identify failure reason without opening node parameter details. |
