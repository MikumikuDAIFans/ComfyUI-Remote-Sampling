from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any


REMOTE_BASE = os.environ.get("REMOTE_SAMPLING_REMOTE_BASE", "/home/user02/remote_ComfyUI")
REMOTE_COMFY = f"{REMOTE_BASE}/ComfyUI"
DEFAULT_PROJECT_ROOT = Path(os.environ.get("REMOTE_SAMPLING_PROJECT_ROOT", r"F:\TieguoDun\Remote_comfyui"))
MAX_INLINE_SHA256_BYTES = int(os.environ.get("REMOTE_WORKFLOW_MAX_INLINE_SHA256_BYTES", str(256 * 1024 * 1024)))


def remote_candidates(kind: str, relative_path: str) -> list[str]:
    normalized = relative_path.replace("\\", "/")
    subdirs = {
        "unet": ["diffusion_models", "unet"],
        "clip": ["clip"],
        "vae": ["vae"],
        "lora": ["loras"],
    }.get(kind, [])
    return [f"{REMOTE_COMFY}/models/{subdir}/{normalized}" for subdir in subdirs]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local_file_info(path_text: str | None) -> dict[str, Any] | None:
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_file():
        return None
    stat = path.stat()
    info: dict[str, Any] = {
        "path": str(path),
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "sha256": None,
        "sha256_policy": "deferred_large_file_hash",
    }
    if stat.st_size <= MAX_INLINE_SHA256_BYTES:
        info["sha256"] = sha256_file(path)
        info["sha256_policy"] = "inline_sha256"
    return info


def dedupe_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in resources:
        key = (str(item.get("kind")), str(item.get("relative_path") or item.get("name")))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_resources_plan(
    analysis: dict[str, Any],
    *,
    remote_base: str = REMOTE_BASE,
    project_root: Path = DEFAULT_PROJECT_ROOT,
) -> dict[str, Any]:
    planned: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for resource in dedupe_resources(list(analysis.get("resources", []))):
        kind = str(resource.get("kind"))
        relative_path = str(resource.get("relative_path") or resource.get("name") or "").replace("\\", "/")
        candidates = remote_candidates(kind, relative_path)
        primary_remote = candidates[0] if candidates else None
        exists_local = bool(resource.get("exists"))
        local_info = local_file_info(resource.get("local_path"))
        item = {
            "kind": kind,
            "name": resource.get("name"),
            "relative_path": relative_path,
            "source_node": resource.get("source_node"),
            "local": {
                "exists": exists_local,
                "path": resource.get("local_path"),
                "candidates": resource.get("local_candidates", []),
                "file": local_info,
            },
            "remote": {
                "base": remote_base,
                "primary_path": primary_remote,
                "candidates": candidates,
                "relative_path_policy": "mirror_local_comfy_models_relative_path",
            },
            "sync": {
                "action": "check_remote" if exists_local else "blocked_local_missing",
                "reason": "Local resource exists; remote existence/hash check is required before conversion."
                if exists_local
                else "Local resource is missing; do not attempt remote sync or conversion.",
                "upload_command_hint": f'python {project_root}\\tools\\upload_to_company_server.py "{resource.get("local_path")}={primary_remote}"'
                if exists_local and primary_remote
                else None,
            },
        }
        if not exists_local:
            errors.append(
                {
                    "type": "LocalResourceMissing",
                    "message": f"Missing local {kind}: {resource.get('name')}",
                    "resource": item,
                    "fatal": True,
                }
            )
        planned.append(item)
    return {
        "schema_version": "resources-plan-v1",
        "remote_base": remote_base,
        "remote_comfy": f"{remote_base}/ComfyUI",
        "relative_path_policy": "mirror_local_comfy_models_relative_path",
        "resources": planned,
        "summary": {
            "total": len(planned),
            "local_missing": sum(1 for item in planned if not item["local"]["exists"]),
            "needs_remote_check": sum(1 for item in planned if item["sync"]["action"] == "check_remote"),
        },
        "errors": errors,
        "fatal": bool(errors),
    }
