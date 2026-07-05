# Custom Node Validation Matrix

- Time: `2026-07-05 12:40 +08:00`
- Phase: `Phase 8 Real Workflow Validation Matrix`
- Scope: real custom-node workflow and incompatible custom-node fail-closed probe.

## Scenario C: Real Custom Node Workflow

Run bundle:

```text
F:\TieguoDun\Remote_comfyui\runs\workflow_runtime_20260705_040251_7f49bf25
```

Detected custom classes:

```text
Lora Loader (LoraManager)
WeiLinPromptUIWithoutLora
```

Detected packages:

```text
comfyui-lora-manager
WeiLin-Comfyui-Tools
```

Remote target paths:

```text
/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/comfyui-lora-manager
/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/WeiLin-Comfyui-Tools
```

Remote environment report:

```json
{
  "fatal": false,
  "summary": {
    "package_count": 2,
    "ready_for_import_smoke": 2,
    "sync_required": 0,
    "remote_package_incomplete": 0
  }
}
```

Dependency install report:

```json
{
  "fatal": false,
  "summary": {
    "command_count": 2,
    "executed": false,
    "failed": 0
  }
}
```

Remote import smoke:

```json
{
  "fatal": false,
  "summary": {
    "class_count": 2,
    "missing_class_count": 0,
    "object_info_count": 819
  }
}
```

Manifest hash coverage:

```text
custom_nodes_plan_sha256: present
remote_environment_report_sha256: present
remote_custom_node_dependency_install_sha256: present
remote_custom_node_import_smoke_sha256: present
```

Gate result:

- custom node package discovery: `pass`
- remote package readiness: `pass`
- dependency plan generated without implicit install: `pass`
- remote object_info import smoke: `pass`

## Scenario E: Incompatible Custom Node

Synthetic plan:

```text
docs\remote_workflow_runtime_upgrade\evidence\phase8_real_validation\synthetic_incompatible_custom_node_plan_20260705.json
```

The synthetic plan points at an existing remote package:

```text
/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/ComfyUI-Remote-Sampling
```

But it requires a class that is not registered:

```text
CodexDefinitelyMissingNodeClassForImportSmoke
```

Remote package check:

```json
{
  "fatal": false,
  "summary": {
    "package_count": 1,
    "ready_for_import_smoke": 1,
    "sync_required": 0,
    "remote_package_incomplete": 0
  }
}
```

Remote import smoke:

```json
{
  "fatal": true,
  "object_info": {
    "missing_classes": [
      "CodexDefinitelyMissingNodeClassForImportSmoke"
    ],
    "ok": false
  },
  "summary": {
    "class_count": 1,
    "missing_class_count": 1,
    "object_info_count": 819
  }
}
```

Remote cleanup check after import smoke:

```text
ss -ltnp | grep ":8197 " -> no output
ps ... "ComfyUI/main.py|remote_submit_prompt" -> no output
find locks -maxdepth 2 -> locks
```

Gate result:

- package directory existing is not enough to pass: `pass`
- missing class in remote `object_info` is fatal: `pass`
- incompatible custom-node workflow would fail before latent upload: `pass`
- remote service cleanup after smoke: `pass`
