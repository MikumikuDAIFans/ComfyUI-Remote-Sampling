from __future__ import annotations

import importlib.util
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from .protocol import file_info, json_sha256, write_json
except ImportError:
    _protocol = importlib.util.spec_from_file_location("remote_sampling_protocol", Path(__file__).with_name("protocol.py"))
    if _protocol is None or _protocol.loader is None:
        raise
    _protocol_module = importlib.util.module_from_spec(_protocol)
    _protocol.loader.exec_module(_protocol_module)
    file_info = _protocol_module.file_info
    json_sha256 = _protocol_module.json_sha256
    write_json = _protocol_module.write_json


DEFAULT_PROJECT_ROOT = Path(os.environ.get("REMOTE_SAMPLING_PROJECT_ROOT", r"F:\TieguoDun\Remote_comfyui"))
DEFAULT_BRIDGE_PYTHON = os.environ.get("REMOTE_SAMPLING_BRIDGE_PYTHON", r"C:\Python314\python.exe")
DEFAULT_LOCAL_LORA_ROOT = Path(
    os.environ.get(
        "REMOTE_SAMPLING_LOCAL_LORA_ROOT",
        r"F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\models\loras",
    )
)
CONVERTER_VERSION = "runtime-conversion-v1"
POLICY_VERSION = "fail-closed-v1"


def project_root_from_payload(payload: dict[str, Any]) -> Path:
    raw = payload.get("project_root") or payload.get("options", {}).get("project_root")
    return Path(raw) if raw else DEFAULT_PROJECT_ROOT


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_converter(project_root: Path):
    return load_module(project_root / "tools" / "convert_ksampler_to_remote_sampling.py", "remote_sampling_converter")


def load_auditor(project_root: Path):
    return load_module(project_root / "tools" / "audit_remote_sampling_workflow.py", "remote_sampling_auditor")


def make_run_id() -> str:
    return f"runtime_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fail_report(run_dir: Path, message: str, *, error_type: str = "RuntimeConversionError", details: Any = None) -> dict[str, Any]:
    report = {
        "ok": False,
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "error": {
            "type": error_type,
            "message": message,
            "details": details,
        },
    }
    write_json(run_dir / "audit.json", report)
    write_json(run_dir / "manifest.json", report)
    return report


def remote_sampling_nodes(prompt: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (str(node_id), node)
        for node_id, node in prompt.items()
        if isinstance(node, dict) and node.get("class_type") == "Remote_Sampling_local"
    ]


def rewrite_profiles_to_bundle(
    *,
    converted_prompt: dict[str, Any],
    profile_summary: list[dict[str, Any]],
    bundle_profile_dir: Path,
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for item in profile_summary:
        node_id = str(item.get("node"))
        source_path = Path(str(item.get("profile_path", "")))
        if not source_path.is_file():
            raise FileNotFoundError(f"profile file missing for node {node_id}: {source_path}")
        profile = read_json(source_path)
        profile_name = f"{node_id}_{source_path.name}"
        target_path = bundle_profile_dir / profile_name
        profile.setdefault("runtime_snapshot", {})
        profile["runtime_snapshot"].update(
            {
                "source_profile_path": str(source_path),
                "source_profile_sha256": file_info(source_path)["sha256"],
                "snapshot_created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        write_json(target_path, profile)
        node = converted_prompt.get(node_id)
        if not isinstance(node, dict) or node.get("class_type") != "Remote_Sampling_local":
            raise ValueError(f"converted node {node_id} is not Remote_Sampling_local")
        node.setdefault("inputs", {})["remote_profile"] = str(target_path)
        snapshots.append(
            {
                "node": node_id,
                "original_profile": item.get("remote_profile"),
                "snapshot_profile": str(target_path),
                "snapshot_file": file_info(target_path),
                "lora_count": item.get("lora_count", 0),
                "loras": item.get("loras", []),
                "is_fixed_profile": item.get("is_fixed_profile", False),
            }
        )
        try:
            source_path.unlink()
        except OSError:
            pass
    return snapshots


def convert_runtime_prompt(payload: dict[str, Any]) -> dict[str, Any]:
    project_root = project_root_from_payload(payload)
    run_id = make_run_id()
    run_dir = project_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    source_prompt = payload.get("prompt")
    if not isinstance(source_prompt, dict):
        return fail_report(run_dir, "payload.prompt must be a ComfyUI API prompt object", error_type="InvalidPayload")

    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    workflow = payload.get("workflow")
    source_prompt_path = run_dir / "source_prompt.json"
    source_workflow_path = run_dir / "source_workflow.json"
    converted_prompt_path = run_dir / "converted_prompt.json"
    profile_dir = run_dir / "profiles"
    audit_text_path = run_dir / "audit.txt"

    write_json(source_prompt_path, source_prompt)
    if isinstance(workflow, dict):
        write_json(source_workflow_path, workflow)

    converter = load_converter(project_root)
    auditor = load_auditor(project_root)
    sampler_prefix = options.get("sampler_prefix") or f"runtime_{run_id}"
    timeout_sec = int(options.get("timeout_sec") or 2400)
    project_root_value = str(project_root)
    python_executable = str(options.get("python_executable") or DEFAULT_BRIDGE_PYTHON)
    lora_root = Path(options.get("lora_root") or DEFAULT_LOCAL_LORA_ROOT)

    try:
        converted_prompt, converted_ids, removed_ids, rewired_clip_refs, profile_summary = converter.convert_prompt(
            prompt=source_prompt,
            remote_profile="auto",
            project_root=project_root_value,
            python_executable=python_executable,
            timeout_sec=timeout_sec,
            sampler_prefix=sampler_prefix,
            prune_unreachable=not bool(options.get("keep_unreachable", False)),
            bypass_local_lora_clip=bool(options.get("bypass_local_lora_clip", True)),
            allow_fixed_profile=False,
            output_path=converted_prompt_path,
            lora_root=lora_root,
        )
        if not converted_ids:
            return fail_report(run_dir, "no KSampler nodes found to convert", error_type="NoKSampler")
        profile_snapshots = rewrite_profiles_to_bundle(
            converted_prompt=converted_prompt,
            profile_summary=profile_summary,
            bundle_profile_dir=profile_dir,
        )
        write_json(converted_prompt_path, converted_prompt)
        audit = auditor.audit_workflow(converted_prompt_path)
        audit_text = auditor.format_human(audit)
        write_json(run_dir / "audit.json", audit)
        write_text(audit_text_path, audit_text)
        fatal_errors = list(audit.get("errors", []))
        manifest = {
            "ok": not fatal_errors,
            "run_id": run_id,
            "run_dir": str(run_dir),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "converter_version": CONVERTER_VERSION,
            "policy_version": POLICY_VERSION,
            "source_prompt": str(source_prompt_path),
            "source_prompt_sha256": json_sha256(source_prompt),
            "source_workflow": str(source_workflow_path) if isinstance(workflow, dict) else None,
            "source_workflow_sha256": json_sha256(workflow) if isinstance(workflow, dict) else None,
            "converted_prompt": str(converted_prompt_path),
            "converted_prompt_sha256": json_sha256(converted_prompt),
            "profile_snapshots": profile_snapshots,
            "converted_node_ids": converted_ids,
            "removed_unreachable": removed_ids,
            "rewired_clip_refs": rewired_clip_refs,
            "audit": str(run_dir / "audit.json"),
            "audit_text": str(audit_text_path),
            "warnings": audit.get("warnings", []),
            "errors": fatal_errors,
        }
        write_json(run_dir / "manifest.json", manifest)
        return {
            **manifest,
            "converted_prompt_object": converted_prompt,
            "audit_summary": audit_text,
        }
    except Exception as exc:
        shutil.rmtree(profile_dir, ignore_errors=True)
        return fail_report(run_dir, str(exc), error_type=exc.__class__.__name__)
