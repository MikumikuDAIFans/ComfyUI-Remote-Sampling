from __future__ import annotations

import time
import uuid
import importlib.util
from pathlib import Path
from typing import Any

try:
    from .custom_node_planner import build_custom_nodes_plan
    from .protocol import json_sha256, write_json
    from .resource_planner import build_resources_plan
    from .runtime_conversion import (
        DEFAULT_PROJECT_ROOT,
        CONVERTER_VERSION,
        POLICY_VERSION,
        convert_runtime_prompt,
        project_root_from_payload,
    )
    from .workflow_analyzer import analyze_prompt
except ImportError:
    _package_root = Path(__file__).resolve().parent
    _protocol = importlib.util.spec_from_file_location("remote_sampling_protocol", _package_root / "protocol.py")
    _custom_node_planner = importlib.util.spec_from_file_location(
        "remote_sampling_custom_node_planner",
        _package_root / "custom_node_planner.py",
    )
    _runtime_conversion = importlib.util.spec_from_file_location(
        "remote_sampling_runtime_conversion",
        _package_root / "runtime_conversion.py",
    )
    _resource_planner = importlib.util.spec_from_file_location(
        "remote_sampling_resource_planner",
        _package_root / "resource_planner.py",
    )
    _workflow_analyzer = importlib.util.spec_from_file_location(
        "remote_sampling_workflow_analyzer",
        _package_root / "workflow_analyzer.py",
    )
    if (
        _protocol is None
        or _protocol.loader is None
        or _custom_node_planner is None
        or _custom_node_planner.loader is None
        or _runtime_conversion is None
        or _runtime_conversion.loader is None
        or _resource_planner is None
        or _resource_planner.loader is None
        or _workflow_analyzer is None
        or _workflow_analyzer.loader is None
    ):
        raise
    _protocol_module = importlib.util.module_from_spec(_protocol)
    _protocol.loader.exec_module(_protocol_module)
    _custom_node_planner_module = importlib.util.module_from_spec(_custom_node_planner)
    _custom_node_planner.loader.exec_module(_custom_node_planner_module)
    _runtime_module = importlib.util.module_from_spec(_runtime_conversion)
    _runtime_conversion.loader.exec_module(_runtime_module)
    _resource_planner_module = importlib.util.module_from_spec(_resource_planner)
    _resource_planner.loader.exec_module(_resource_planner_module)
    _workflow_analyzer_module = importlib.util.module_from_spec(_workflow_analyzer)
    _workflow_analyzer.loader.exec_module(_workflow_analyzer_module)
    json_sha256 = _protocol_module.json_sha256
    write_json = _protocol_module.write_json
    build_custom_nodes_plan = _custom_node_planner_module.build_custom_nodes_plan
    build_resources_plan = _resource_planner_module.build_resources_plan
    DEFAULT_PROJECT_ROOT = _runtime_module.DEFAULT_PROJECT_ROOT
    CONVERTER_VERSION = _runtime_module.CONVERTER_VERSION
    POLICY_VERSION = _runtime_module.POLICY_VERSION
    convert_runtime_prompt = _runtime_module.convert_runtime_prompt
    project_root_from_payload = _runtime_module.project_root_from_payload
    analyze_prompt = _workflow_analyzer_module.analyze_prompt


WORKFLOW_RUNTIME_VERSION = "workflow-runtime-v1"
WORKFLOW_RUNTIME_POLICY_VERSION = "workflow-fail-closed-v1"
STATE_MACHINE = [
    "idle",
    "local_preflight",
    "analysis",
    "resource_plan",
    "sync",
    "remote_env",
    "convert",
    "queue",
    "sampling",
    "download",
    "decode",
    "complete",
    "failed",
]
def make_workflow_run_id() -> str:
    return f"workflow_runtime_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def workflow_runtime_status() -> dict[str, Any]:
    return {
        "ok": True,
        "version": WORKFLOW_RUNTIME_VERSION,
        "policy_version": WORKFLOW_RUNTIME_POLICY_VERSION,
        "state_machine": STATE_MACHINE,
        "capabilities": {
            "plan_current_workflow": True,
            "run_current_workflow": False,
            "resource_sync": False,
            "custom_node_sync": "archive_tool_available",
            "runtime_conversion_backend": CONVERTER_VERSION,
            "runtime_conversion_policy": POLICY_VERSION,
            "remote_rgb_image_nodes_forbidden": True,
            "formal_entry": "workflow_level_controller",
        },
    }


def create_workflow_runtime_plan(payload: dict[str, Any]) -> dict[str, Any]:
    project_root = project_root_from_payload(payload) if isinstance(payload, dict) else DEFAULT_PROJECT_ROOT
    run_id = make_workflow_run_id()
    run_dir = project_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    workflow = payload.get("workflow") if isinstance(payload, dict) else None
    if not isinstance(prompt, dict):
        error = {
            "ok": False,
            "run_id": run_id,
            "run_dir": str(run_dir),
            "stage": "failed",
            "error": {
                "type": "InvalidPayload",
                "message": "payload.prompt must be a ComfyUI API prompt object.",
            },
        }
        write_json(run_dir / "manifest.json", error)
        return error

    source_prompt_path = run_dir / "source_prompt.json"
    source_workflow_path = run_dir / "source_workflow.json"
    analysis_path = run_dir / "workflow_analysis.json"
    resources_plan_path = run_dir / "resources_plan.json"
    custom_nodes_plan_path = run_dir / "custom_nodes_plan.json"
    status_path = run_dir / "workflow_status.json"
    manifest_path = run_dir / "manifest.json"

    write_json(source_prompt_path, prompt)
    if isinstance(workflow, dict):
        write_json(source_workflow_path, workflow)
    analysis = analyze_prompt(prompt)
    write_json(analysis_path, analysis)
    resources_plan = build_resources_plan(analysis, project_root=project_root)
    write_json(resources_plan_path, resources_plan)
    custom_nodes_plan = build_custom_nodes_plan(analysis)
    write_json(custom_nodes_plan_path, custom_nodes_plan)
    status = {
        "schema_version": "workflow-runtime-status-v0",
        "run_id": run_id,
        "stage": "analysis",
        "message": "Workflow-level runtime plan generated. Remote resource diff and custom-node environment checks are separate guarded steps.",
        "overall_percent": 30,
        "state_machine": STATE_MACHINE,
        "fatal": bool(analysis.get("fatal") or resources_plan.get("fatal") or custom_nodes_plan.get("fatal")),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_json(status_path, status)
    manifest = {
        "ok": not status["fatal"],
        "run_id": run_id,
        "run_dir": str(run_dir),
        "created_at": status["created_at"],
        "workflow_runtime_version": WORKFLOW_RUNTIME_VERSION,
        "policy_version": WORKFLOW_RUNTIME_POLICY_VERSION,
        "source_prompt": str(source_prompt_path),
        "source_prompt_sha256": json_sha256(prompt),
        "source_workflow": str(source_workflow_path) if isinstance(workflow, dict) else None,
        "source_workflow_sha256": json_sha256(workflow) if isinstance(workflow, dict) else None,
        "workflow_analysis": str(analysis_path),
        "workflow_analysis_sha256": json_sha256(analysis),
        "resources_plan": str(resources_plan_path),
        "resources_plan_sha256": json_sha256(resources_plan),
        "custom_nodes_plan": str(custom_nodes_plan_path),
        "custom_nodes_plan_sha256": json_sha256(custom_nodes_plan),
        "workflow_status": str(status_path),
        "stage": "remote_env",
        "next_required_phase": "Phase 4: Remote Environment Manager",
        "analysis_summary": {
            "node_count": analysis["node_count"],
            "sampler_count": len(analysis["samplers"]),
            "custom_node_class_count": len(analysis["custom_node_classes"]),
            "custom_node_package_count": custom_nodes_plan["summary"]["package_count"],
            "local_custom_node_package_missing_count": custom_nodes_plan["summary"]["local_package_missing"],
            "resource_count": resources_plan["summary"]["total"],
            "local_missing_resource_count": resources_plan["summary"]["local_missing"],
            "fatal": status["fatal"],
        },
        "errors": (analysis.get("issues", []) if analysis.get("fatal") else [])
        + resources_plan.get("errors", [])
        + custom_nodes_plan.get("errors", []),
        "warnings": [
            "Resource plan mirrors local ComfyUI/models relative paths. Remote existence/hash diff is checked by Phase 3 remote integration.",
        ],
    }
    write_json(manifest_path, manifest)
    return {
        **manifest,
        "status": status,
        "analysis": analysis,
        "resources_plan": resources_plan,
        "custom_nodes_plan": custom_nodes_plan,
    }


def _copy_json_value(path_text: str | None) -> dict[str, Any] | None:
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_file():
        return None
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def create_workflow_runtime_conversion(payload: dict[str, Any]) -> dict[str, Any]:
    plan = create_workflow_runtime_plan(payload)
    if not plan.get("ok"):
        return plan

    run_dir = Path(str(plan["run_dir"]))
    runtime_options = dict(payload.get("options", {})) if isinstance(payload.get("options"), dict) else {}
    runtime_options.setdefault("sampler_prefix", f"workflow_{plan['run_id']}")
    runtime_payload = {
        "prompt": payload.get("prompt"),
        "workflow": payload.get("workflow"),
        "project_root": str(project_root_from_payload(payload)),
        "options": runtime_options,
    }
    converted = convert_runtime_prompt(runtime_payload)
    if not converted.get("ok"):
        failure = {
            **plan,
            "ok": False,
            "stage": "failed",
            "conversion": converted,
            "errors": plan.get("errors", []) + [converted.get("error", {})],
        }
        write_json(run_dir / "manifest.json", failure)
        return failure

    converted_prompt = converted.get("converted_prompt_object")
    converted_prompt_path = run_dir / "converted_local_prompt.json"
    remote_execution_plan_path = run_dir / "remote_execution_plan.json"
    conversion_manifest_path = Path(str(converted.get("run_dir", ""))) / "manifest.json"
    conversion_manifest = _copy_json_value(str(conversion_manifest_path))
    if isinstance(converted_prompt, dict):
        write_json(converted_prompt_path, converted_prompt)

    remote_execution_plan = {
        "schema_version": "remote-execution-plan-v1",
        "workflow_run_id": plan["run_id"],
        "runtime_conversion_run_id": converted.get("run_id"),
        "runtime_conversion_run_dir": converted.get("run_dir"),
        "source_prompt_sha256": plan.get("source_prompt_sha256"),
        "workflow_analysis_sha256": plan.get("workflow_analysis_sha256"),
        "resources_plan_sha256": plan.get("resources_plan_sha256"),
        "custom_nodes_plan_sha256": plan.get("custom_nodes_plan_sha256"),
        "converted_prompt": str(converted_prompt_path) if isinstance(converted_prompt, dict) else converted.get("converted_prompt"),
        "converted_prompt_sha256": json_sha256(converted_prompt) if isinstance(converted_prompt, dict) else converted.get("converted_prompt_sha256"),
        "profile_snapshots": converted.get("profile_snapshots", []),
        "converted_node_ids": converted.get("converted_node_ids", []),
        "removed_unreachable": converted.get("removed_unreachable", []),
        "rewired_clip_refs": converted.get("rewired_clip_refs", []),
        "audit": converted.get("audit"),
        "audit_text": converted.get("audit_text"),
        "remote_rgb_image_nodes_forbidden": True,
        "stale_workflow_policy": "converted_from_current_source_prompt_in_this_run",
        "runtime_conversion_manifest": str(conversion_manifest_path) if conversion_manifest_path.is_file() else None,
        "runtime_conversion_manifest_sha256": json_sha256(conversion_manifest) if conversion_manifest else None,
    }
    write_json(remote_execution_plan_path, remote_execution_plan)

    manifest = _copy_json_value(str(run_dir / "manifest.json")) or plan
    manifest.update(
        {
            "ok": True,
            "stage": "convert",
            "next_required_phase": "Phase 6: Sync Engine, Progress UI And Failure Recovery",
            "converted_local_prompt": str(converted_prompt_path),
            "converted_local_prompt_sha256": remote_execution_plan["converted_prompt_sha256"],
            "remote_execution_plan": str(remote_execution_plan_path),
            "remote_execution_plan_sha256": json_sha256(remote_execution_plan),
            "runtime_conversion_run_id": converted.get("run_id"),
            "runtime_conversion_run_dir": converted.get("run_dir"),
            "runtime_conversion_manifest": str(conversion_manifest_path) if conversion_manifest_path.is_file() else None,
            "runtime_conversion_manifest_sha256": remote_execution_plan["runtime_conversion_manifest_sha256"],
            "warnings": list(manifest.get("warnings", [])) + [
                "Workflow-level conversion is generated per run from the current source prompt. Remote queue submission is not executed by this route.",
            ],
        }
    )
    write_json(run_dir / "manifest.json", manifest)
    return {
        **manifest,
        "status": {
            "schema_version": "workflow-runtime-status-v0",
            "run_id": plan["run_id"],
            "stage": "convert",
            "message": "Workflow-level conversion generated without queue submission.",
            "overall_percent": 55,
            "fatal": False,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "analysis": plan.get("analysis"),
        "resources_plan": plan.get("resources_plan"),
        "custom_nodes_plan": plan.get("custom_nodes_plan"),
        "remote_execution_plan_object": remote_execution_plan,
        "converted_prompt_object": converted_prompt,
        "audit_summary": converted.get("audit_summary"),
    }
