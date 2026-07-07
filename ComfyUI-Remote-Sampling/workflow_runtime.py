from __future__ import annotations

import time
import uuid
import importlib.util
import subprocess
import threading
from pathlib import Path
from typing import Any

try:
    from .custom_node_planner import build_custom_nodes_plan
    from .protocol import json_sha256, write_json
    from .resource_planner import build_resources_plan
    from .runtime_conversion import (
        DEFAULT_BRIDGE_PYTHON,
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
    DEFAULT_BRIDGE_PYTHON = _runtime_module.DEFAULT_BRIDGE_PYTHON
    CONVERTER_VERSION = _runtime_module.CONVERTER_VERSION
    POLICY_VERSION = _runtime_module.POLICY_VERSION
    convert_runtime_prompt = _runtime_module.convert_runtime_prompt
    project_root_from_payload = _runtime_module.project_root_from_payload
    analyze_prompt = _workflow_analyzer_module.analyze_prompt


WORKFLOW_RUNTIME_VERSION = "workflow-runtime-v1"
WORKFLOW_RUNTIME_POLICY_VERSION = "workflow-fail-closed-v1"
FORBIDDEN_REMOTE_IMAGE_NODES = {
    "LoadImage",
    "VAEEncode",
    "VAELoader",
    "VAEDecode",
    "PreviewImage",
    "SaveImage",
}
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
_BACKEND_WATCHER_LOCK = threading.Lock()
_BACKEND_WATCHERS: dict[str, threading.Thread] = {}


def make_workflow_run_id() -> str:
    return f"workflow_runtime_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _workflow_paths(run_dir: Path) -> dict[str, Path]:
    return {
        "status": run_dir / "workflow_status.json",
        "events": run_dir / "workflow_events.jsonl",
        "report": run_dir / "workflow_runtime_report.txt",
        "manifest": run_dir / "manifest.json",
    }


def _append_workflow_event(
    run_dir: Path,
    stage: str,
    event: str,
    message: str,
    *,
    overall_percent: float | int | None = None,
    details: Any = None,
) -> dict[str, Any]:
    import json

    record = {
        "ts": _now_text(),
        "stage": stage,
        "event": event,
        "message": message,
    }
    if overall_percent is not None:
        record["overall_percent"] = float(overall_percent)
    if details is not None:
        record["details"] = details
    events_path = _workflow_paths(run_dir)["events"]
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def _write_workflow_status(
    run_dir: Path,
    run_id: str,
    stage: str,
    message: str,
    *,
    overall_percent: float | int,
    fatal: bool = False,
    details: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = {
        "schema_version": "workflow-runtime-status-v1",
        "run_id": run_id,
        "stage": stage,
        "message": message,
        "overall_percent": float(overall_percent),
        "fatal": bool(fatal),
        "updated_at": _now_text(),
        "state_machine": STATE_MACHINE,
    }
    if details is not None:
        status["details"] = details
    if extra:
        status.update(extra)
    write_json(_workflow_paths(run_dir)["status"], status)
    _append_workflow_event(
        run_dir,
        stage,
        "status",
        message,
        overall_percent=overall_percent,
        details=details,
    )
    return status


def _read_workflow_events(run_dir: Path, tail: int = 40) -> list[dict[str, Any]]:
    import json

    events_path = _workflow_paths(run_dir)["events"]
    if not events_path.is_file():
        return []
    lines = events_path.read_text(encoding="utf-8").splitlines()
    if tail > 0:
        lines = lines[-tail:]
    events: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            item = {"ts": None, "stage": "unknown", "event": "decode_error", "message": line}
        if isinstance(item, dict):
            events.append(item)
    return events


def _write_workflow_report(run_dir: Path, manifest: dict[str, Any], status: dict[str, Any] | None = None) -> Path:
    events = _read_workflow_events(run_dir, tail=200)
    lines = [
        "# Remote Workflow Runtime Report",
        "",
        f"run_id: {manifest.get('run_id')}",
        f"stage: {manifest.get('stage')}",
        f"ok: {manifest.get('ok')}",
        f"updated_at: {_now_text()}",
        "",
        "## Status",
        f"stage: {(status or {}).get('stage', manifest.get('stage'))}",
        f"message: {(status or {}).get('message', '')}",
        f"overall_percent: {(status or {}).get('overall_percent', '')}",
        "",
        "## Hash Chain",
    ]
    for key in (
        "source_prompt_sha256",
        "source_workflow_sha256",
        "workflow_analysis_sha256",
        "resources_plan_sha256",
        "resources_diff_sha256",
        "resources_sync_report_sha256",
        "custom_nodes_plan_sha256",
        "remote_environment_report_sha256",
        "custom_nodes_sync_report_sha256",
        "remote_custom_node_dependency_install_sha256",
        "remote_custom_node_import_smoke_sha256",
        "converted_local_prompt_sha256",
        "remote_execution_plan_sha256",
        "runtime_conversion_manifest_sha256",
    ):
        if manifest.get(key):
            lines.append(f"{key}: {manifest.get(key)}")
    if manifest.get("error"):
        lines.extend(["", "## Error", str(manifest.get("error"))])
    lines.extend(["", "## Recent Events"])
    for event in events[-30:]:
        lines.append(
            f"- {event.get('ts')} [{event.get('stage')}/{event.get('event')}] "
            f"{event.get('message')} ({event.get('overall_percent', '')}%)"
        )
    report_path = _workflow_paths(run_dir)["report"]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _update_manifest_observability(run_dir: Path, manifest: dict[str, Any], status: dict[str, Any] | None = None) -> dict[str, Any]:
    paths = _workflow_paths(run_dir)
    report_path = _write_workflow_report(run_dir, manifest, status)
    events = _read_workflow_events(run_dir, tail=10000)
    if status is None and paths["status"].is_file():
        status = _read_json_file(paths["status"])
    manifest.update(
        {
            "workflow_status": str(paths["status"]) if paths["status"].is_file() else None,
            "workflow_status_sha256": json_sha256(status) if status else None,
            "workflow_events": str(paths["events"]) if paths["events"].is_file() else None,
            "workflow_events_sha256": json_sha256({"events": events}) if events else None,
            "workflow_report": str(report_path),
            "workflow_report_sha256": json_sha256({"text": report_path.read_text(encoding="utf-8")}),
        }
    )
    write_json(paths["manifest"], manifest)
    return manifest


def workflow_runtime_status() -> dict[str, Any]:
    return {
        "ok": True,
        "version": WORKFLOW_RUNTIME_VERSION,
        "policy_version": WORKFLOW_RUNTIME_POLICY_VERSION,
        "state_machine": STATE_MACHINE,
        "capabilities": {
            "plan_current_workflow": True,
            "run_current_workflow": "deprecated_hidden_compatibility_entry",
            "check_and_sync": "guarded_prepare_without_queue",
            "convert_canvas": "guarded_prepare_then_frontend_canvas_rewrite",
            "native_queue_after_convert": True,
            "resource_sync": "upload_required_resources_before_canvas_conversion",
            "custom_node_sync": "archive_tool_available",
            "runtime_conversion_backend": CONVERTER_VERSION,
            "runtime_conversion_policy": POLICY_VERSION,
            "remote_rgb_image_nodes_forbidden": True,
            "formal_entry": "workflow_level_controller",
            "workflow_status_events": True,
            "workflow_run_status_route": True,
            "workflow_backend_queue_watcher": True,
            "workflow_runtime_config": {
                "project_root": "payload.project_root or payload.options.project_root",
                "python_executable": "payload.options.python_executable",
                "local_comfy_api": "payload.local_comfy_api",
                "timeout_sec": "payload.timeout_sec or payload.options.timeout_sec",
            },
        },
    }


SAMPLER_PARITY_RISK_NAMES = {
    "seeds_2",
    "seeds_3",
    "er_sde",
    "gradient_estimation",
    "gradient_estimation_cfg_pp",
    "sa_solver",
    "sa_solver_pece",
}


def sampler_parity_warnings(analysis: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for sampler in analysis.get("samplers", []):
        if not isinstance(sampler, dict):
            continue
        sampler_name = str(sampler.get("sampler_name") or "")
        scheduler = str(sampler.get("scheduler") or "")
        if sampler_name in SAMPLER_PARITY_RISK_NAMES:
            node_id = sampler.get("node_id", "?")
            warnings.append(
                "Sampler parity warning: node "
                f"{node_id} uses {sampler_name}/{scheduler}. This sampler can be more sensitive to "
                "ComfyUI version, platform, and implementation differences. For local/remote equivalence "
                "validation, first test the same workflow with euler/normal; keep this sampler only after "
                "the visual result is accepted."
            )
    return warnings


def create_workflow_runtime_plan(payload: dict[str, Any]) -> dict[str, Any]:
    project_root = project_root_from_payload(payload) if isinstance(payload, dict) else DEFAULT_PROJECT_ROOT
    run_id = make_workflow_run_id()
    run_dir = project_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_workflow_status(
        run_dir,
        run_id,
        "local_preflight",
        "Workflow runtime plan started.",
        overall_percent=4,
    )

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
        status = _write_workflow_status(
            run_dir,
            run_id,
            "failed",
            "payload.prompt must be a ComfyUI API prompt object.",
            overall_percent=100,
            fatal=True,
            details=error["error"],
        )
        _update_manifest_observability(run_dir, error, status)
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
    _write_workflow_status(
        run_dir,
        run_id,
        "analysis",
        "Analyzing source workflow and extracting resource/custom-node dependencies.",
        overall_percent=12,
    )
    analysis = analyze_prompt(prompt)
    write_json(analysis_path, analysis)
    _write_workflow_status(
        run_dir,
        run_id,
        "resource_plan",
        "Building resource and custom-node plans from workflow analysis.",
        overall_percent=24,
        details={
            "sampler_count": len(analysis.get("samplers", [])),
            "custom_node_class_count": len(analysis.get("custom_node_classes", [])),
        },
    )
    resources_plan = build_resources_plan(analysis, project_root=project_root)
    write_json(resources_plan_path, resources_plan)
    custom_nodes_plan = build_custom_nodes_plan(analysis)
    write_json(custom_nodes_plan_path, custom_nodes_plan)
    status = _write_workflow_status(
        run_dir,
        run_id,
        "analysis",
        "Workflow-level runtime plan generated. Remote resource diff and custom-node environment checks are separate guarded steps.",
        overall_percent=30,
        fatal=bool(analysis.get("fatal") or resources_plan.get("fatal") or custom_nodes_plan.get("fatal")),
        details={
            "resource_count": resources_plan["summary"]["total"],
            "custom_node_package_count": custom_nodes_plan["summary"]["package_count"],
        },
    )
    warnings = [
        "Resource plan mirrors local ComfyUI/models relative paths. Remote existence/hash diff is checked by Phase 3 remote integration.",
    ]
    warnings.extend(sampler_parity_warnings(analysis))
    manifest = {
        "ok": not status["fatal"],
        "run_id": run_id,
        "run_dir": str(run_dir),
        "created_at": status["updated_at"],
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
        "warnings": warnings,
    }
    _update_manifest_observability(run_dir, manifest, status)
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


def _read_json_file(path: Path) -> dict[str, Any]:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"expected JSON object: {path}")
    return data


def _prompt_class_list(prompt: dict[str, Any]) -> list[str]:
    return [node.get("class_type", "") for node in prompt.values() if isinstance(node, dict)]


def _remote_prompt_privacy_summary(prompt: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(prompt, dict):
        return {
            "class_list": [],
            "forbidden_image_nodes": [],
            "forbidden_image_node_count": 0,
            "remote_rgb_image_nodes_forbidden": True,
        }
    classes = _prompt_class_list(prompt)
    forbidden = sorted(set(classes) & FORBIDDEN_REMOTE_IMAGE_NODES)
    return {
        "class_list": classes,
        "forbidden_image_nodes": forbidden,
        "forbidden_image_node_count": len(forbidden),
        "remote_rgb_image_nodes_forbidden": True,
    }


def _remote_profile_privacy_summary(profile_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    classes: list[str] = []
    profiles: list[dict[str, Any]] = []
    for snapshot in profile_snapshots:
        path = Path(str(snapshot.get("snapshot_profile", "")))
        profile = _read_json_file(path) if path.is_file() else {}
        profile_classes: list[str] = []
        unet = profile.get("unet") if isinstance(profile.get("unet"), dict) else {}
        clip = profile.get("clip") if isinstance(profile.get("clip"), dict) else {}
        if unet.get("class_type"):
            profile_classes.append(str(unet["class_type"]))
        if clip.get("class_type"):
            profile_classes.append(str(clip["class_type"]))
        for lora in profile.get("loras", []):
            if isinstance(lora, dict):
                profile_classes.append(str(lora.get("class_type", "LoraLoader")))
        profile_classes.append("Remote_Sampling_remote")
        forbidden = sorted(set(profile_classes) & FORBIDDEN_REMOTE_IMAGE_NODES)
        classes.extend(profile_classes)
        profiles.append(
            {
                "node": snapshot.get("node"),
                "snapshot_profile": str(path) if path else None,
                "class_list": profile_classes,
                "forbidden_image_nodes": forbidden,
                "forbidden_image_node_count": len(forbidden),
            }
        )
    forbidden_all = sorted(set(classes) & FORBIDDEN_REMOTE_IMAGE_NODES)
    return {
        "class_list": classes,
        "forbidden_image_nodes": forbidden_all,
        "forbidden_image_node_count": len(forbidden_all),
        "profiles": profiles,
        "remote_rgb_image_nodes_forbidden": True,
        "privacy_scope": "remote_profile_prompt_reconstruction",
    }


def _run_dir_for(project_root: Path, run_id: str) -> Path:
    base = (project_root / "runs").resolve()
    run_dir = (base / run_id).resolve()
    if base != run_dir and base not in run_dir.parents:
        raise ValueError("run_id resolved outside project runs directory")
    return run_dir


def read_workflow_runtime_run_status(project_root: str | Path | None, run_id: str, *, tail: int = 40) -> dict[str, Any]:
    root = Path(project_root) if project_root else DEFAULT_PROJECT_ROOT
    run_dir = _run_dir_for(root, run_id)
    if not run_dir.is_dir():
        return {
            "ok": False,
            "run_id": run_id,
            "error": {"type": "RunNotFound", "message": f"workflow runtime run not found: {run_id}"},
        }
    paths = _workflow_paths(run_dir)
    read_errors: list[dict[str, str]] = []
    try:
        status = _read_json_file(paths["status"]) if paths["status"].is_file() else None
    except Exception as exc:
        status = None
        read_errors.append({"path": str(paths["status"]), "type": type(exc).__name__, "message": str(exc)})
    try:
        manifest = _read_json_file(paths["manifest"]) if paths["manifest"].is_file() else None
    except Exception as exc:
        manifest = None
        read_errors.append({"path": str(paths["manifest"]), "type": type(exc).__name__, "message": str(exc)})
    report = paths["report"].read_text(encoding="utf-8") if paths["report"].is_file() else None
    return {
        "ok": True,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": status,
        "events": _read_workflow_events(run_dir, tail=tail),
        "manifest": manifest,
        "report": report,
        "read_errors": read_errors,
    }


def record_workflow_runtime_client_event(payload: dict[str, Any]) -> dict[str, Any]:
    project_root = project_root_from_payload(payload) if isinstance(payload, dict) else DEFAULT_PROJECT_ROOT
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        return {
            "ok": False,
            "error": {"type": "InvalidPayload", "message": "payload.run_id is required."},
        }
    run_dir = _run_dir_for(project_root, run_id)
    if not run_dir.is_dir():
        return {
            "ok": False,
            "run_id": run_id,
            "error": {"type": "RunNotFound", "message": f"workflow runtime run not found: {run_id}"},
        }
    stage = str(payload.get("stage") or "sampling")
    if stage not in STATE_MACHINE:
        stage = "sampling"
    message = str(payload.get("message") or "Workflow runtime client event.")
    percent = payload.get("overall_percent", 80)
    try:
        percent_value = max(0.0, min(100.0, float(percent)))
    except (TypeError, ValueError):
        percent_value = 80.0
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    fatal = bool(payload.get("fatal", False))
    status = _write_workflow_status(
        run_dir,
        run_id,
        stage,
        message,
        overall_percent=percent_value,
        fatal=fatal,
        details=details,
        extra={
            "client_observed": True,
            "prompt_id": payload.get("prompt_id"),
            "job_id": details.get("job_id"),
        },
    )
    manifest = _copy_json_value(str(run_dir / "manifest.json")) or {
        "ok": not fatal,
        "run_id": run_id,
        "run_dir": str(run_dir),
    }
    manifest.update(
        {
            "stage": stage,
            "ok": bool(manifest.get("ok", True)) and not fatal,
            "client_observed_prompt_id": payload.get("prompt_id"),
            "client_observed_stage": stage,
            "client_observed_details": details,
        }
    )
    manifest = _update_manifest_observability(run_dir, manifest, status)
    return {
        "ok": True,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": status,
        "manifest": manifest,
        "events": _read_workflow_events(run_dir, tail=40),
    }


def _local_comfy_api_base(payload: dict[str, Any]) -> str:
    import os

    text = str(
        payload.get("local_comfy_api")
        or payload.get("comfy_api_base")
        or os.environ.get("REMOTE_WORKFLOW_LOCAL_API")
        or "http://127.0.0.1:8188"
    ).strip()
    return text.rstrip("/") or "http://127.0.0.1:8188"


def _post_local_comfy_json(api_base: str, endpoint: str, payload: dict[str, Any], timeout_sec: float = 30.0) -> dict[str, Any]:
    import json
    import urllib.request

    request = urllib.request.Request(
        f"{api_base}{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _get_local_comfy_json(api_base: str, endpoint: str, timeout_sec: float = 15.0) -> dict[str, Any]:
    import json
    import urllib.request

    with urllib.request.urlopen(f"{api_base}{endpoint}", timeout=timeout_sec) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _find_remote_sampling_report(value: Any) -> str | None:
    if isinstance(value, str):
        if "Remote Sampling Report" in value or "remote_sampling_report" in value:
            return value
        return None
    if isinstance(value, list):
        for item in value:
            found = _find_remote_sampling_report(item)
            if found:
                return found
    if isinstance(value, dict):
        for item in value.values():
            found = _find_remote_sampling_report(item)
            if found:
                return found
    return None


def _report_line_value(report: str | None, key: str) -> str | None:
    if not report:
        return None
    prefix = f"{key}:"
    for line in report.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _report_json_value(report: str | None, key: str) -> Any:
    import json

    value = _report_line_value(report, key)
    if not value or not value.startswith("{"):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"decode_error": value}


def _remote_sampling_report_details(report: str | None) -> dict[str, Any]:
    return {
        "job_id": _report_line_value(report, "job_id"),
        "total_elapsed_sec": _report_line_value(report, "total_elapsed_sec"),
        "upload": _report_json_value(report, "upload"),
        "sampling": _report_json_value(report, "sampling"),
        "download": _report_json_value(report, "download"),
        "raw_report_present": bool(report),
    }


def _history_item_for_prompt(api_base: str, prompt_id: str) -> dict[str, Any] | None:
    history = _get_local_comfy_json(api_base, f"/history/{prompt_id}")
    item = history.get(prompt_id)
    return item if isinstance(item, dict) else None


def _history_has_execution_error(item: dict[str, Any] | None) -> bool:
    if not item:
        return False
    status = item.get("status") if isinstance(item.get("status"), dict) else {}
    for message in status.get("messages", []) or []:
        if isinstance(message, (list, tuple)) and message and message[0] == "execution_error":
            return True
    return False


def _sync_required_custom_node_packages(report: dict[str, Any]) -> list[str]:
    packages: list[str] = []
    for package in report.get("packages", []) or []:
        if not isinstance(package, dict):
            continue
        if package.get("action") != "sync_required":
            continue
        name = str(package.get("package_name") or "").strip()
        if name:
            packages.append(name)
    return sorted(set(packages), key=str.casefold)


def _safe_report_stem(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_", ".") else "_" for char in value) or "package"


def _backend_queue_worker(project_root: str | Path | None, run_id: str, api_base: str, timeout_sec: int) -> None:
    project_path = Path(project_root) if project_root else DEFAULT_PROJECT_ROOT
    run_dir = _run_dir_for(project_path, run_id)
    prompt_id: str | None = None
    try:
        converted_prompt_path = run_dir / "converted_local_prompt.json"
        if not converted_prompt_path.is_file():
            raise FileNotFoundError(f"converted prompt not found: {converted_prompt_path}")
        converted_prompt = _read_json_file(converted_prompt_path)
        manifest = _copy_json_value(str(run_dir / "manifest.json")) or {"ok": True, "run_id": run_id, "run_dir": str(run_dir)}

        status = _write_workflow_status(
            run_dir,
            run_id,
            "queue",
            "Backend watcher is submitting converted prompt to local ComfyUI.",
            overall_percent=74,
            extra={
                "backend_watcher": {
                    "enabled": True,
                    "api_base": api_base,
                    "timeout_sec": timeout_sec,
                    "owner": "workflow_runtime_backend",
                }
            },
        )
        manifest.update(
            {
                "stage": "queue",
                "queue_policy": "backend_submits_and_watches_converted_prompt",
                "backend_watcher": status.get("backend_watcher"),
            }
        )
        _update_manifest_observability(run_dir, manifest, status)

        queued = _post_local_comfy_json(
            api_base,
            "/prompt",
            {"prompt": converted_prompt, "client_id": f"remote-workflow-runtime-backend-{run_id}"},
            timeout_sec=30,
        )
        prompt_id = str(queued.get("prompt_id") or "")
        if not prompt_id:
            raise RuntimeError(f"local ComfyUI /prompt response did not include prompt_id: {queued}")

        status = _write_workflow_status(
            run_dir,
            run_id,
            "sampling",
            "Backend watcher queued prompt; waiting for ComfyUI history terminal state.",
            overall_percent=78,
            details={"prompt_id": prompt_id},
            extra={
                "prompt_id": prompt_id,
                "backend_watcher": {
                    "enabled": True,
                    "api_base": api_base,
                    "timeout_sec": timeout_sec,
                    "owner": "workflow_runtime_backend",
                },
            },
        )
        manifest.update({"stage": "sampling", "prompt_id": prompt_id})
        _update_manifest_observability(run_dir, manifest, status)

        started = time.monotonic()
        last_progress_event = 0.0
        while time.monotonic() - started < timeout_sec:
            item = _history_item_for_prompt(api_base, prompt_id)
            if item:
                if _history_has_execution_error(item):
                    status_obj = item.get("status") if isinstance(item.get("status"), dict) else {}
                    messages = status_obj.get("messages", [])
                    status = _write_workflow_status(
                        run_dir,
                        run_id,
                        "failed",
                        "Converted prompt execution failed.",
                        overall_percent=100,
                        fatal=True,
                        details={"prompt_id": prompt_id, "messages": messages},
                    )
                    manifest.update(
                        {
                            "ok": False,
                            "stage": "failed",
                            "prompt_id": prompt_id,
                            "backend_observed_terminal": True,
                            "error": {"type": "PromptExecutionFailed", "messages": messages},
                        }
                    )
                    _update_manifest_observability(run_dir, manifest, status)
                    return
                item_status = item.get("status") if isinstance(item.get("status"), dict) else {}
                if item_status.get("completed"):
                    report = _find_remote_sampling_report(item)
                    details = {
                        "prompt_id": prompt_id,
                        "remote_sampling_report": _remote_sampling_report_details(report),
                    }
                    status = _write_workflow_status(
                        run_dir,
                        run_id,
                        "complete",
                        "Guarded remote workflow run completed.",
                        overall_percent=100,
                        details=details,
                        extra={
                            "prompt_id": prompt_id,
                            "backend_observed_terminal": True,
                            "backend_elapsed_sec": round(time.monotonic() - started, 3),
                        },
                    )
                    manifest.update(
                        {
                            "ok": True,
                            "stage": "complete",
                            "prompt_id": prompt_id,
                            "backend_observed_terminal": True,
                            "backend_elapsed_sec": status.get("backend_elapsed_sec"),
                            "remote_sampling_report": details["remote_sampling_report"],
                        }
                    )
                    _update_manifest_observability(run_dir, manifest, status)
                    return
            elapsed = time.monotonic() - started
            if elapsed - last_progress_event >= 15.0 or last_progress_event == 0.0:
                status = _write_workflow_status(
                    run_dir,
                    run_id,
                    "sampling",
                    "Backend watcher is polling ComfyUI history.",
                    overall_percent=84,
                    details={"prompt_id": prompt_id, "elapsed_sec": round(elapsed, 3)},
                    extra={"prompt_id": prompt_id},
                )
                manifest.update({"stage": "sampling", "prompt_id": prompt_id})
                _update_manifest_observability(run_dir, manifest, status)
                last_progress_event = elapsed
            time.sleep(1.0)

        raise TimeoutError(f"timed out after {timeout_sec}s waiting for prompt {prompt_id}")
    except Exception as error:
        status = _write_workflow_status(
            run_dir,
            run_id,
            "failed",
            f"Backend watcher failed: {error}",
            overall_percent=100,
            fatal=True,
            details={"prompt_id": prompt_id, "error_type": type(error).__name__, "error": str(error)},
        )
        manifest = _copy_json_value(str(run_dir / "manifest.json")) or {"run_id": run_id, "run_dir": str(run_dir)}
        manifest.update(
            {
                "ok": False,
                "stage": "failed",
                "prompt_id": prompt_id,
                "backend_observed_terminal": False,
                "error": {"type": type(error).__name__, "message": str(error)},
            }
        )
        _update_manifest_observability(run_dir, manifest, status)
    finally:
        with _BACKEND_WATCHER_LOCK:
            _BACKEND_WATCHERS.pop(run_id, None)


def start_workflow_runtime_backend_queue(payload: dict[str, Any]) -> dict[str, Any]:
    project_root = project_root_from_payload(payload) if isinstance(payload, dict) else DEFAULT_PROJECT_ROOT
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        return {
            "ok": False,
            "stage": "failed",
            "error": {"type": "InvalidPayload", "message": "run_id is required."},
        }
    run_dir = _run_dir_for(project_root, run_id)
    paths = _workflow_paths(run_dir)
    if not run_dir.is_dir():
        return {
            "ok": False,
            "run_id": run_id,
            "stage": "failed",
            "error": {"type": "RunNotFound", "message": f"workflow runtime run not found: {run_id}"},
        }
    if paths["status"].is_file():
        current = _read_json_file(paths["status"])
        if current.get("stage") in {"complete", "failed"}:
            return {"ok": True, "run_id": run_id, "already_terminal": True, "status": current}

    api_base = _local_comfy_api_base(payload)
    timeout_sec = int(payload.get("timeout_sec") or payload.get("timeout") or 2400)
    timeout_sec = max(30, min(timeout_sec, 86400))
    with _BACKEND_WATCHER_LOCK:
        existing = _BACKEND_WATCHERS.get(run_id)
        if existing and existing.is_alive():
            status = _read_json_file(paths["status"]) if paths["status"].is_file() else None
            return {"ok": True, "run_id": run_id, "watcher_started": False, "already_running": True, "status": status}
        thread = threading.Thread(
            target=_backend_queue_worker,
            args=(project_root, run_id, api_base, timeout_sec),
            name=f"remote-workflow-runtime-{run_id}",
            daemon=True,
        )
        _BACKEND_WATCHERS[run_id] = thread
    status = _write_workflow_status(
        run_dir,
        run_id,
        "queue",
        "Backend watcher thread started.",
        overall_percent=73,
        extra={
            "backend_watcher": {
                "enabled": True,
                "api_base": api_base,
                "timeout_sec": timeout_sec,
                "thread": thread.name,
            }
        },
    )
    manifest = _copy_json_value(str(paths["manifest"])) or {"run_id": run_id, "run_dir": str(run_dir)}
    manifest.update(
        {
            "stage": "queue",
            "queue_policy": "backend_submits_and_watches_converted_prompt",
            "backend_watcher": status.get("backend_watcher"),
        }
    )
    _update_manifest_observability(run_dir, manifest, status)
    thread.start()
    return {"ok": True, "run_id": run_id, "watcher_started": True, "status": status}


def _load_plan_for_run(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    project_root = project_root_from_payload(payload)
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        plan = create_workflow_runtime_plan(payload)
        return plan, payload

    run_dir = _run_dir_for(project_root, run_id)
    manifest = _read_json_file(run_dir / "manifest.json")
    source_prompt_path = Path(str(manifest.get("source_prompt", run_dir / "source_prompt.json")))
    source_workflow_path = Path(str(manifest.get("source_workflow", run_dir / "source_workflow.json")))
    next_payload = dict(payload)
    prompt = next_payload.get("prompt")
    if isinstance(prompt, dict):
        prompt_hash = json_sha256(prompt)
        expected_hash = manifest.get("source_prompt_sha256")
        if expected_hash and prompt_hash != expected_hash:
            failure = _fail_with_plan(
                manifest,
                "local_preflight",
                "SourcePromptHashMismatch",
                "Existing workflow runtime plan does not match the supplied prompt. Re-run Plan Current Workflow or omit run_id.",
                details={
                    "run_id": run_id,
                    "expected_source_prompt_sha256": expected_hash,
                    "actual_source_prompt_sha256": prompt_hash,
                },
            )
            return failure, next_payload
    else:
        next_payload["prompt"] = _read_json_file(source_prompt_path)

    workflow = next_payload.get("workflow")
    if isinstance(workflow, dict):
        workflow_hash = json_sha256(workflow)
        expected_workflow_hash = manifest.get("source_workflow_sha256")
        if expected_workflow_hash and workflow_hash != expected_workflow_hash:
            failure = _fail_with_plan(
                manifest,
                "local_preflight",
                "SourceWorkflowHashMismatch",
                "Existing workflow runtime plan does not match the supplied frontend workflow. Re-run Plan Current Workflow or omit run_id.",
                details={
                    "run_id": run_id,
                    "expected_source_workflow_sha256": expected_workflow_hash,
                    "actual_source_workflow_sha256": workflow_hash,
                },
            )
            return failure, next_payload
    elif source_workflow_path.is_file():
        next_payload["workflow"] = _read_json_file(source_workflow_path)
    _write_workflow_status(
        run_dir,
        run_id,
        "local_preflight",
        "Loaded existing workflow runtime plan for guarded preparation.",
        overall_percent=32,
    )
    return manifest, next_payload


def _run_project_tool(project_root: Path, args: list[str], *, timeout: int = 7200, allow_failure: bool = False) -> str:
    completed = subprocess.run(
        [str(DEFAULT_BRIDGE_PYTHON), *args],
        cwd=str(project_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if completed.returncode != 0 and not allow_failure:
        raise RuntimeError(completed.stdout)
    return completed.stdout


def _fail_with_plan(plan: dict[str, Any], stage: str, error_type: str, message: str, *, details: Any = None) -> dict[str, Any]:
    run_dir = Path(str(plan["run_dir"]))
    error = {
        "type": error_type,
        "message": message,
        "details": details,
        "fatal": True,
    }
    failure = {
        **plan,
        "ok": False,
        "stage": stage,
        "error": error,
        "errors": list(plan.get("errors", [])) + [error],
    }
    write_json(run_dir / "manifest.json", failure)
    status = _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        stage,
        message,
        overall_percent=100 if stage == "failed" else 50,
        fatal=True,
        details=error,
    )
    _update_manifest_observability(run_dir, failure, status)
    return failure


def _convert_from_plan(plan: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(str(plan["run_dir"]))
    _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "convert",
        "Generating fresh converted prompt and remote execution plan from the current source workflow.",
        overall_percent=74,
    )
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
        status = _write_workflow_status(
            run_dir,
            str(plan["run_id"]),
            "convert",
            "Workflow-level runtime conversion failed.",
            overall_percent=100,
            fatal=True,
            details=converted.get("error", {}),
        )
        _update_manifest_observability(run_dir, failure, status)
        return failure

    converted_prompt = converted.get("converted_prompt_object")
    converted_prompt_path = run_dir / "converted_local_prompt.json"
    remote_execution_plan_path = run_dir / "remote_execution_plan.json"
    conversion_manifest_path = Path(str(converted.get("run_dir", ""))) / "manifest.json"
    conversion_manifest = _copy_json_value(str(conversion_manifest_path))
    profile_snapshots = converted.get("profile_snapshots", [])
    profile_snapshots = profile_snapshots if isinstance(profile_snapshots, list) else []
    privacy = _remote_profile_privacy_summary(profile_snapshots)
    if privacy["forbidden_image_nodes"]:
        return _fail_with_plan(
            plan,
            "convert",
            "RemotePromptForbiddenImageNodes",
            "Remote sampling profile would build a prompt containing image I/O or VAE image nodes.",
            details=privacy,
        )
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
        "resources_diff_sha256": plan.get("resources_diff_sha256"),
        "resources_sync_report_sha256": plan.get("resources_sync_report_sha256"),
        "custom_nodes_plan_sha256": plan.get("custom_nodes_plan_sha256"),
        "remote_environment_report_sha256": plan.get("remote_environment_report_sha256"),
        "custom_nodes_sync_report_sha256": plan.get("custom_nodes_sync_report_sha256"),
        "remote_custom_node_dependency_install_sha256": plan.get("remote_custom_node_dependency_install_sha256"),
        "remote_custom_node_import_smoke_sha256": plan.get("remote_custom_node_import_smoke_sha256"),
        "converted_prompt": str(converted_prompt_path) if isinstance(converted_prompt, dict) else converted.get("converted_prompt"),
        "converted_prompt_sha256": json_sha256(converted_prompt) if isinstance(converted_prompt, dict) else converted.get("converted_prompt_sha256"),
        "profile_snapshots": profile_snapshots,
        "converted_node_ids": converted.get("converted_node_ids", []),
        "removed_unreachable": converted.get("removed_unreachable", []),
        "rewired_clip_refs": converted.get("rewired_clip_refs", []),
        "audit": converted.get("audit"),
        "audit_text": converted.get("audit_text"),
        "remote_prompt_privacy": privacy,
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
            "remote_prompt_privacy": privacy,
            "remote_prompt_forbidden_image_node_count": privacy["forbidden_image_node_count"],
            "runtime_conversion_run_id": converted.get("run_id"),
            "runtime_conversion_run_dir": converted.get("run_dir"),
            "runtime_conversion_manifest": str(conversion_manifest_path) if conversion_manifest_path.is_file() else None,
            "runtime_conversion_manifest_sha256": remote_execution_plan["runtime_conversion_manifest_sha256"],
            "warnings": list(manifest.get("warnings", [])) + [
                "Workflow-level conversion is generated per run from the current source prompt. Remote queue submission is not executed by this route.",
            ],
        }
    )
    status = _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "convert",
        "Workflow-level conversion generated without queue submission.",
        overall_percent=82,
        details={
            "converted_node_ids": remote_execution_plan.get("converted_node_ids", []),
            "profile_snapshot_count": len(remote_execution_plan.get("profile_snapshots", [])),
        },
    )
    _update_manifest_observability(run_dir, manifest, status)
    return {
        **manifest,
        "status": status,
        "analysis": plan.get("analysis"),
        "resources_plan": plan.get("resources_plan"),
        "custom_nodes_plan": plan.get("custom_nodes_plan"),
        "remote_execution_plan_object": remote_execution_plan,
        "converted_prompt_object": converted_prompt,
        "audit_summary": converted.get("audit_summary"),
    }


def create_workflow_runtime_conversion(payload: dict[str, Any]) -> dict[str, Any]:
    plan = create_workflow_runtime_plan(payload)
    if not plan.get("ok"):
        return plan
    return _convert_from_plan(plan, payload)


def _check_and_sync_resources(plan: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    project_root = project_root_from_payload(payload)
    run_dir = Path(str(plan["run_dir"]))
    resources_plan_path = run_dir / "resources_plan.json"
    resources_diff_path = run_dir / "resources_diff.json"
    sync_report_path = run_dir / "resources_sync_report.json"
    _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "resource_plan",
        "Checking remote model and LoRA resources before latent upload.",
        overall_percent=36,
    )
    check_stdout = _run_project_tool(
        project_root,
        [
            str(project_root / "tools" / "check_remote_resource_plan.py"),
            str(resources_plan_path),
            "--output",
            str(resources_diff_path),
        ],
        timeout=300,
        allow_failure=True,
    )
    if not resources_diff_path.is_file():
        return _fail_with_plan(
            plan,
            "resource_plan",
            "RemoteCheckDidNotWriteReport",
            "Remote resource checker did not write resources_diff.json.",
            details={"stdout_tail": check_stdout[-4000:]},
        )
    diff = _read_json_file(resources_diff_path)
    _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "resource_plan",
        "Remote resource diff completed.",
        overall_percent=42,
        details=diff.get("summary", {}),
    )
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    auto_sync = options.get("auto_sync_resources", True)
    if diff.get("fatal"):
        return _fail_with_plan(plan, "resource_plan", "ResourcePreflightFailed", "Remote resource diff is fatal.", details=diff)
    if int(diff.get("summary", {}).get("upload_required", 0)) > 0:
        if not auto_sync:
            return _fail_with_plan(plan, "sync", "ResourceSyncRequired", "Remote resources are missing and auto_sync_resources is disabled.", details=diff)
        _write_workflow_status(
            run_dir,
            str(plan["run_id"]),
            "sync",
            "Uploading missing remote resources.",
            overall_percent=45,
            details=diff.get("summary", {}),
        )
        recheck_stdout = _run_project_tool(
            project_root,
            [
                str(project_root / "tools" / "sync_remote_resources.py"),
                str(resources_plan_path),
                str(resources_diff_path),
                "--output",
                str(sync_report_path),
            ],
            timeout=7200,
        )
        sync_report = _read_json_file(sync_report_path)
        _write_workflow_status(
            run_dir,
            str(plan["run_id"]),
            "sync",
            "Resource upload finished. Rechecking remote resource diff.",
            overall_percent=50,
            details=sync_report.get("summary", {}),
        )
        _run_project_tool(
            project_root,
            [
                str(project_root / "tools" / "check_remote_resource_plan.py"),
                str(resources_plan_path),
                "--output",
                str(resources_diff_path),
            ],
            timeout=300,
            allow_failure=True,
        )
        if not resources_diff_path.is_file():
            return _fail_with_plan(
                plan,
                "sync",
                "RemoteCheckDidNotWriteReport",
                "Remote resource checker did not write resources_diff.json after sync.",
                details={"stdout_tail": recheck_stdout[-4000:]},
            )
        diff = _read_json_file(resources_diff_path)
        if diff.get("fatal") or int(diff.get("summary", {}).get("upload_required", 0)) > 0:
            return _fail_with_plan(plan, "sync", "ResourceSyncFailed", "Resources are still not ready after sync.", details={"diff": diff, "sync_report": sync_report})

    manifest = _copy_json_value(str(run_dir / "manifest.json")) or plan
    manifest.update(
        {
            "resources_diff": str(resources_diff_path),
            "resources_diff_sha256": json_sha256(diff),
            "resources_sync_report": str(sync_report_path) if sync_report_path.is_file() else None,
            "resources_sync_report_sha256": json_sha256(_read_json_file(sync_report_path)) if sync_report_path.is_file() else None,
            "resources_ready": True,
        }
    )
    status = _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "sync",
        "Remote resources are ready.",
        overall_percent=52,
        details=diff.get("summary", {}),
    )
    _update_manifest_observability(run_dir, manifest, status)
    return manifest


def _check_and_sync_custom_nodes(plan: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    project_root = project_root_from_payload(payload)
    run_dir = Path(str(plan["run_dir"]))
    custom_nodes_plan_path = run_dir / "custom_nodes_plan.json"
    env_report_path = run_dir / "remote_environment_report.json"
    sync_report_path = run_dir / "custom_nodes_sync_report.json"
    dependency_report_path = run_dir / "remote_custom_node_dependency_install.json"
    import_smoke_path = run_dir / "remote_custom_node_import_smoke.json"
    _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "remote_env",
        "Checking remote custom-node packages.",
        overall_percent=54,
    )
    check_stdout = _run_project_tool(
        project_root,
        [
            str(project_root / "tools" / "check_remote_custom_nodes_plan.py"),
            str(custom_nodes_plan_path),
            "--output",
            str(env_report_path),
        ],
        timeout=300,
        allow_failure=True,
    )
    if not env_report_path.is_file():
        return _fail_with_plan(
            plan,
            "remote_env",
            "RemoteCheckDidNotWriteReport",
            "Remote custom node checker did not write remote_environment_report.json.",
            details={"stdout_tail": check_stdout[-4000:]},
        )
    report = _read_json_file(env_report_path)
    _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "remote_env",
        "Remote custom-node environment diff completed.",
        overall_percent=56,
        details=report.get("summary", {}),
    )
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    auto_sync = options.get("auto_sync_custom_nodes", True)
    if report.get("fatal"):
        return _fail_with_plan(plan, "remote_env", "RemoteEnvironmentFailed", "Remote custom node environment check is fatal.", details=report)
    if int(report.get("summary", {}).get("sync_required", 0)) > 0:
        if not auto_sync:
            return _fail_with_plan(plan, "remote_env", "CustomNodeSyncRequired", "Remote custom nodes are missing and auto_sync_custom_nodes is disabled.", details=report)
        required_packages = _sync_required_custom_node_packages(report)
        if not required_packages:
            return _fail_with_plan(
                plan,
                "remote_env",
                "CustomNodeSyncRequiredButNoPackages",
                "Remote custom-node report says sync is required, but no package action was marked sync_required.",
                details=report,
            )
        _write_workflow_status(
            run_dir,
            str(plan["run_id"]),
            "remote_env",
            "Syncing missing remote custom-node packages.",
            overall_percent=58,
            details={**report.get("summary", {}), "sync_required_packages": required_packages},
        )
        package_reports: list[dict[str, Any]] = []
        recheck_stdout_parts: list[str] = []
        for index, package_name in enumerate(required_packages, start=1):
            package_report_path = run_dir / f"custom_nodes_sync_report.{_safe_report_stem(package_name)}.json"
            _write_workflow_status(
                run_dir,
                str(plan["run_id"]),
                "remote_env",
                f"Syncing custom-node package {index}/{len(required_packages)}: {package_name}",
                overall_percent=58 + (index - 1) / max(1, len(required_packages)) * 2,
                details={
                    **report.get("summary", {}),
                    "sync_required_packages": required_packages,
                    "current_package": package_name,
                    "package_index": index,
                    "package_count": len(required_packages),
                },
            )
            package_stdout = _run_project_tool(
                project_root,
                [
                    str(project_root / "tools" / "sync_remote_custom_nodes.py"),
                    str(custom_nodes_plan_path),
                    "--package",
                    package_name,
                    "--output",
                    str(package_report_path),
                ],
                timeout=7200,
            )
            recheck_stdout_parts.append(package_stdout)
            if not package_report_path.is_file():
                return _fail_with_plan(
                    plan,
                    "remote_env",
                    "CustomNodeSyncDidNotWriteReport",
                    f"Custom-node sync did not write report for package {package_name}.",
                    details={"stdout_tail": package_stdout[-4000:], "package_name": package_name},
                )
            package_reports.append(_read_json_file(package_report_path))
        sync_report = {
            "schema_version": "custom-node-sync-report-v1",
            "synced_at": _now_text(),
            "packages": [item for report_item in package_reports for item in report_item.get("packages", [])],
            "summary": {
                "package_count": sum(int(report_item.get("summary", {}).get("package_count", 0)) for report_item in package_reports),
                "synced": sum(int(report_item.get("summary", {}).get("synced", 0)) for report_item in package_reports),
                "dry_run": False,
                "requested_packages": required_packages,
            },
            "fatal": any(bool(report_item.get("fatal")) for report_item in package_reports),
            "per_package_reports": [str(run_dir / f"custom_nodes_sync_report.{_safe_report_stem(name)}.json") for name in required_packages],
        }
        write_json(sync_report_path, sync_report)
        _write_workflow_status(
            run_dir,
            str(plan["run_id"]),
            "remote_env",
            "Custom-node package sync finished. Rechecking remote environment.",
            overall_percent=60,
            details=sync_report.get("summary", {}),
        )
        _run_project_tool(
            project_root,
            [
                str(project_root / "tools" / "check_remote_custom_nodes_plan.py"),
                str(custom_nodes_plan_path),
                "--output",
                str(env_report_path),
            ],
            timeout=300,
            allow_failure=True,
        )
        if not env_report_path.is_file():
            return _fail_with_plan(
                plan,
                "remote_env",
                "RemoteCheckDidNotWriteReport",
                "Remote custom node checker did not write remote_environment_report.json after sync.",
                details={"stdout_tail": "\n".join(recheck_stdout_parts)[-4000:]},
            )
        report = _read_json_file(env_report_path)
    if report.get("fatal") or int(report.get("summary", {}).get("sync_required", 0)) > 0:
            return _fail_with_plan(plan, "remote_env", "CustomNodeSyncFailed", "Custom nodes are still not ready after sync.", details={"report": report, "sync_report": sync_report})

    _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "remote_env",
        "Preparing remote custom-node dependency plan.",
        overall_percent=62,
    )
    dependency_args = [
        str(project_root / "tools" / "install_remote_custom_node_dependencies.py"),
        str(custom_nodes_plan_path),
        "--output",
        str(dependency_report_path),
    ]
    if bool(options.get("allow_remote_dependency_install", False)):
        dependency_args.append("--execute")
    dependency_stdout = _run_project_tool(
        project_root,
        dependency_args,
        timeout=2700,
        allow_failure=True,
    )
    if not dependency_report_path.is_file():
        return _fail_with_plan(
            plan,
            "remote_env",
            "RemoteDependencyInstallDidNotWriteReport",
            "Remote custom node dependency installer did not write report.",
            details={"stdout_tail": dependency_stdout[-4000:]},
        )
    dependency_report = _read_json_file(dependency_report_path)
    if dependency_report.get("fatal"):
        return _fail_with_plan(
            plan,
            "remote_env",
            "RemoteDependencyInstallFailed",
            "Remote custom node dependency installation failed.",
            details=dependency_report,
        )

    _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "remote_env",
        "Running remote ComfyUI custom-node import smoke.",
        overall_percent=66,
        details=dependency_report.get("summary", {}),
    )
    smoke_stdout = _run_project_tool(
        project_root,
        [
            str(project_root / "tools" / "remote_custom_node_import_smoke.py"),
            str(custom_nodes_plan_path),
            "--output",
            str(import_smoke_path),
        ],
        timeout=900,
        allow_failure=True,
    )
    if not import_smoke_path.is_file():
        return _fail_with_plan(
            plan,
            "remote_env",
            "RemoteImportSmokeDidNotWriteReport",
            "Remote custom node import smoke did not write report.",
            details={"stdout_tail": smoke_stdout[-4000:]},
        )
    import_smoke = _read_json_file(import_smoke_path)
    if import_smoke.get("fatal"):
        return _fail_with_plan(
            plan,
            "remote_env",
            "RemoteImportSmokeFailed",
            "Remote ComfyUI object_info is missing required custom node classes.",
            details=import_smoke,
        )

    manifest = _copy_json_value(str(run_dir / "manifest.json")) or plan
    manifest.update(
        {
            "remote_environment_report": str(env_report_path),
            "remote_environment_report_sha256": json_sha256(report),
            "custom_nodes_sync_report": str(sync_report_path) if sync_report_path.is_file() else None,
            "custom_nodes_sync_report_sha256": json_sha256(_read_json_file(sync_report_path)) if sync_report_path.is_file() else None,
            "remote_custom_node_dependency_install": str(dependency_report_path),
            "remote_custom_node_dependency_install_sha256": json_sha256(dependency_report),
            "remote_custom_node_import_smoke": str(import_smoke_path),
            "remote_custom_node_import_smoke_sha256": json_sha256(import_smoke),
            "remote_environment_ready": True,
        }
    )
    status = _write_workflow_status(
        run_dir,
        str(plan["run_id"]),
        "remote_env",
        "Remote custom-node environment is ready.",
        overall_percent=70,
        details={
            "environment": report.get("summary", {}),
            "dependency": dependency_report.get("summary", {}),
            "import_smoke": import_smoke.get("summary", {}),
        },
    )
    _update_manifest_observability(run_dir, manifest, status)
    return manifest


def create_workflow_runtime_guarded_run(payload: dict[str, Any]) -> dict[str, Any]:
    plan, payload = _load_plan_for_run(payload)
    if not plan.get("ok"):
        return plan
    with_resources = _check_and_sync_resources(plan, payload)
    if not with_resources.get("ok", False):
        return with_resources
    with_env = _check_and_sync_custom_nodes(with_resources, payload)
    if not with_env.get("ok", False):
        return with_env
    converted = _convert_from_plan(with_env, payload)
    if not converted.get("ok"):
        return converted
    run_dir = Path(str(converted["run_dir"]))
    status = _write_workflow_status(
        run_dir,
        str(converted["run_id"]),
        "queue",
        "Guarded workflow runtime is ready to queue. Backend watcher should submit converted_prompt_object to ComfyUI.",
        overall_percent=72,
        extra={
            "guards": {
                "resources_ready": True,
                "remote_environment_ready": True,
                "converted_from_current_source": True,
            },
        },
    )
    manifest = _copy_json_value(str(run_dir / "manifest.json")) or converted
    manifest.update(
        {
            "stage": "queue",
            "workflow_status": str(run_dir / "workflow_status.json"),
            "workflow_status_sha256": json_sha256(status),
            "queue_policy": "backend_submits_and_watches_converted_prompt",
        }
    )
    _update_manifest_observability(run_dir, manifest, status)
    return {
        **converted,
        **manifest,
        "status": status,
    }
