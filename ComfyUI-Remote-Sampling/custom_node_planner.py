from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Any


REMOTE_BASE = os.environ.get("REMOTE_SAMPLING_REMOTE_BASE", "/home/user02/remote_ComfyUI")
REMOTE_COMFY = f"{REMOTE_BASE}/ComfyUI"
DEFAULT_LOCAL_COMFY_ROOT = Path(
    os.environ.get(
        "REMOTE_SAMPLING_LOCAL_COMFY_ROOT",
        r"F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI",
    )
)
SCAN_EXTENSIONS = {".py", ".js", ".json", ".toml", ".yaml", ".yml"}
MAX_SCAN_BYTES = int(os.environ.get("REMOTE_WORKFLOW_CUSTOM_NODE_SCAN_MAX_BYTES", str(5 * 1024 * 1024)))
SELF_PACKAGE_NAME = "ComfyUI-Remote-Sampling"


def custom_nodes_root(local_comfy_root: Path = DEFAULT_LOCAL_COMFY_ROOT) -> Path:
    return local_comfy_root / "custom_nodes"


def package_dirs(local_comfy_root: Path = DEFAULT_LOCAL_COMFY_ROOT) -> list[Path]:
    root = custom_nodes_root(local_comfy_root)
    if not root.is_dir():
        return []
    return [
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name.casefold())
        if path.is_dir() and not path.name.startswith("__")
    ]


def iter_scan_files(package_dir: Path):
    for path in package_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
        except OSError:
            continue
        yield path


def text_contains(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def git_remote_url(package_dir: Path) -> str | None:
    config_path = package_dir / ".git" / "config"
    if not config_path.is_file():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
    except configparser.Error:
        return None
    section = 'remote "origin"'
    if parser.has_option(section, "url"):
        return parser.get(section, "url")
    return None


def dependency_files(package_dir: Path) -> list[dict[str, Any]]:
    names = ["requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py", "package.json"]
    result: list[dict[str, Any]] = []
    for name in names:
        path = package_dir / name
        if path.is_file():
            result.append({"name": name, "path": str(path), "size": path.stat().st_size})
    return result


def discover_package_for_class(class_name: str, local_comfy_root: Path = DEFAULT_LOCAL_COMFY_ROOT) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for package_dir in package_dirs(local_comfy_root):
        if package_dir.name == SELF_PACKAGE_NAME and not class_name.startswith("Remote_Sampling_"):
            continue
        matched_files: list[str] = []
        score = 0
        for file_path in iter_scan_files(package_dir):
            if not text_contains(file_path, class_name):
                continue
            relative = file_path.relative_to(package_dir).as_posix()
            matched_files.append(relative)
            if file_path.name == "__init__.py":
                score += 5
            if file_path.suffix.lower() == ".py":
                score += 3
            if "node" in relative.lower():
                score += 1
            if len(matched_files) >= 12:
                break
        if matched_files:
            matches.append({"package_dir": package_dir, "matched_files": matched_files, "score": score})
    if not matches:
        return None
    matches.sort(key=lambda item: (-int(item["score"]), len(str(item["package_dir"])), str(item["package_dir"]).casefold()))
    best = matches[0]
    package_dir = best["package_dir"]
    return {
        "package_name": package_dir.name,
        "local_path": str(package_dir),
        "matched_files": best["matched_files"],
        "git_remote": git_remote_url(package_dir),
        "dependency_files": dependency_files(package_dir),
    }


def build_custom_nodes_plan(
    analysis: dict[str, Any],
    *,
    local_comfy_root: Path = DEFAULT_LOCAL_COMFY_ROOT,
    remote_base: str = REMOTE_BASE,
) -> dict[str, Any]:
    custom_classes = list(analysis.get("custom_node_classes", []))
    packages: dict[str, dict[str, Any]] = {}
    class_items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for class_name in sorted({str(item) for item in custom_classes}):
        package = discover_package_for_class(class_name, local_comfy_root)
        if package is None:
            item = {
                "class_name": class_name,
                "local_package": None,
                "remote_package": None,
                "sync": {
                    "action": "blocked_local_package_missing",
                    "reason": "The class was present in the workflow, but no local custom node package could be discovered.",
                    "repair_hint": f"Install or locate the custom node that registers class {class_name!r} in local ComfyUI/custom_nodes.",
                },
            }
            errors.append(
                {
                    "type": "CustomNodePackageNotFound",
                    "message": f"Cannot discover local custom node package for {class_name}",
                    "class_name": class_name,
                    "fatal": True,
                }
            )
        else:
            package_name = str(package["package_name"])
            remote_path = f"{remote_base}/ComfyUI/custom_nodes/{package_name}"
            local_path = package["local_path"]
            item = {
                "class_name": class_name,
                "local_package": package,
                "remote_package": {
                    "path": remote_path,
                    "package_name": package_name,
                },
                "sync": {
                    "action": "check_remote_then_sync_if_missing",
                    "reason": "Local package was discovered; remote package existence and class registration must be checked before conversion.",
                    "upload_strategy": "archive_local_package_then_extract_under_remote_custom_nodes",
                    "manual_sync_hint": f'Compress "{local_path}" and extract it to "{remote_path}" on the remote ComfyUI host.',
                },
            }
            if package_name not in packages:
                packages[package_name] = {
                    "package_name": package_name,
                    "local_path": local_path,
                    "remote_path": remote_path,
                    "git_remote": package.get("git_remote"),
                    "dependency_files": package.get("dependency_files", []),
                    "classes": [],
                }
            packages[package_name]["classes"].append(class_name)
        class_items.append(item)

    return {
        "schema_version": "custom-nodes-plan-v1",
        "local_comfy_root": str(local_comfy_root),
        "local_custom_nodes_root": str(custom_nodes_root(local_comfy_root)),
        "remote_base": remote_base,
        "remote_custom_nodes_root": f"{remote_base}/ComfyUI/custom_nodes",
        "classes": class_items,
        "packages": sorted(packages.values(), key=lambda item: item["package_name"].casefold()),
        "summary": {
            "custom_class_count": len(class_items),
            "package_count": len(packages),
            "local_package_missing": sum(1 for item in class_items if item["local_package"] is None),
            "needs_remote_check": sum(1 for item in class_items if item["local_package"] is not None),
        },
        "errors": errors,
        "fatal": bool(errors),
    }
