#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import posixpath
import shlex
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any


DEFAULT_PROJECT_ROOT = Path(os.environ.get("REMOTE_SAMPLING_PROJECT_ROOT", r"F:\TieguoDun\Remote_comfyui"))
DEFAULT_SERVER_EXEC = Path(
    os.environ.get(
        "REMOTE_SAMPLING_SERVER_EXEC",
        r"C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py",
    )
)
REMOTE_BASE = os.environ.get("REMOTE_SAMPLING_REMOTE_BASE", "/home/user02/remote_ComfyUI")
REMOTE_CUSTOM_NODES_ROOT = os.environ.get(
    "REMOTE_SAMPLING_REMOTE_CUSTOM_NODES_ROOT",
    f"{REMOTE_BASE}/ComfyUI/custom_nodes",
)
REMOTE_TRANSFER_ROOT = os.environ.get("REMOTE_SAMPLING_REMOTE_TRANSFER_ROOT", f"{REMOTE_BASE}/transfer/custom_nodes")
REMOTE_SESSION_PATH = Path(__file__).resolve().parents[1] / "ComfyUI-Remote-Sampling" / "remote_session.py"
EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp"}


def load_remote_session():
    spec = importlib.util.spec_from_file_location("remote_sampling_remote_session", REMOTE_SESSION_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {REMOTE_SESSION_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


remote_session = load_remote_session()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"expected JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def should_skip(path: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return False


def make_archive(package: dict[str, Any], output_dir: Path) -> tuple[Path, int, int]:
    local_path = Path(str(package.get("local_path") or ""))
    if not local_path.is_dir():
        raise FileNotFoundError(f"local custom node package directory not found: {local_path}")
    package_name = str(package.get("package_name") or local_path.name)
    archive = output_dir / f"{package_name}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    output_dir.mkdir(parents=True, exist_ok=True)
    file_count = 0
    bytes_total = 0
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in local_path.rglob("*"):
            relative = path.relative_to(local_path)
            if should_skip(relative):
                continue
            if path.is_dir():
                continue
            zf.write(path, relative.as_posix())
            file_count += 1
            bytes_total += path.stat().st_size
    return archive, file_count, bytes_total


def run_command(args: list[str], *, timeout: int) -> str:
    completed = remote_session.run_subprocess_with_retry(args, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return completed.stdout


def upload_archive(project_root: Path, archive: Path, remote_archive: str) -> str:
    stream_uploader = project_root / "tools" / "upload_to_company_server_stream.py"
    sftp_uploader = project_root / "tools" / "upload_to_company_server.py"
    uploader = stream_uploader if stream_uploader.is_file() else sftp_uploader
    if not uploader.is_file():
        raise FileNotFoundError(uploader)
    return run_command(["python", str(uploader), f"{archive}={remote_archive}"], timeout=1800)


def normalize_remote_path(path: str) -> str:
    text = str(path or "").replace("\\", "/").strip()
    if not text.startswith("/"):
        raise ValueError(f"remote path must be absolute: {path}")
    return posixpath.normpath(text)


def ensure_remote_under(path: str, root: str, *, label: str) -> str:
    clean_path = normalize_remote_path(path)
    clean_root = normalize_remote_path(root)
    if clean_path != clean_root and not clean_path.startswith(clean_root.rstrip("/") + "/"):
        raise ValueError(f"{label} escapes remote root: {clean_path} not under {clean_root}")
    return clean_path


def extract_remote(server_exec: Path, remote_archive: str, remote_path: str) -> tuple[str, str | None]:
    remote_parent = posixpath.dirname(remote_path)
    remote_python = f"""
import json
import os
import shutil
import time
import zipfile

archive = {remote_archive!r}
target = {remote_path!r}
parent = {remote_parent!r}
backup = None

os.makedirs(parent, exist_ok=True)
tmp = target + ".extracting"
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(tmp, exist_ok=True)

try:
    zipfile.ZipFile(archive).extractall(tmp)
    if os.path.exists(target):
        backup = target + ".backup." + time.strftime("%Y%m%d_%H%M%S")
        os.replace(target, backup)
    os.replace(tmp, target)
    print(json.dumps({{"ok": True, "target": target, "backup_path": backup}}, ensure_ascii=False))
except Exception:
    shutil.rmtree(tmp, ignore_errors=True)
    if backup and os.path.exists(backup) and not os.path.exists(target):
        os.replace(backup, target)
    raise
""".strip()
    command = "cd /home/user02/remote_ComfyUI && python3 -c " + shlex.quote(remote_python)
    output = run_command(["python", str(server_exec), "--cmd", command], timeout=600)
    backup_path = None
    for line in output.splitlines():
        if line.strip().startswith("{"):
            try:
                data = json.loads(line)
                backup_path = data.get("backup_path")
            except json.JSONDecodeError:
                pass
    return output, backup_path


def packages_to_sync(plan: dict[str, Any], selected: set[str] | None) -> list[dict[str, Any]]:
    packages = list(plan.get("packages", []))
    if selected:
        packages = [item for item in packages if str(item.get("package_name")) in selected]
    return packages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive and sync local custom node packages to the remote ComfyUI custom_nodes tree.")
    parser.add_argument("custom_nodes_plan", type=Path)
    parser.add_argument("--package", action="append", dest="packages", help="Package name to sync. Can be used multiple times.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--server-exec", type=Path, default=DEFAULT_SERVER_EXEC)
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Validate and report intended sync actions without uploading or replacing remote files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = read_json(args.custom_nodes_plan)
    archive_dir = args.archive_dir or args.project_root / "transfer" / "custom_nodes"
    selected = set(args.packages) if args.packages else None
    results = []
    for package in packages_to_sync(plan, selected):
        package_name = str(package.get("package_name"))
        try:
            remote_path = ensure_remote_under(str(package.get("remote_path")), REMOTE_CUSTOM_NODES_ROOT, label=f"{package_name}.remote_path")
            remote_archive = ensure_remote_under(
                f"{REMOTE_TRANSFER_ROOT}/{package_name}_{time.strftime('%Y%m%d_%H%M%S')}.zip",
                REMOTE_TRANSFER_ROOT,
                label=f"{package_name}.remote_archive",
            )
            archive, file_count, bytes_total = make_archive(package, archive_dir)
            if args.dry_run:
                upload_log = ""
                extract_log = ""
                backup_path = None
                action = "dry_run"
            else:
                upload_log = upload_archive(args.project_root, archive, remote_archive)
                extract_log, backup_path = extract_remote(args.server_exec, remote_archive, remote_path)
                action = "synced"
            results.append(
                {
                    "package_name": package_name,
                    "local_path": package.get("local_path"),
                    "remote_path": remote_path,
                    "validated_remote_path": remote_path,
                    "archive": str(archive),
                    "remote_archive": remote_archive,
                    "backup_path": backup_path,
                    "file_count": file_count,
                    "bytes_total": bytes_total,
                    "upload_log_tail": upload_log[-2000:],
                    "extract_log_tail": extract_log[-2000:],
                    "action": action,
                    "ok": True,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "package_name": package_name,
                    "local_path": package.get("local_path"),
                    "remote_path": package.get("remote_path"),
                    "action": "failed",
                    "ok": False,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                    "fallback_hint": (
                        "Fix the local package path or remote target, then rerun Check & Sync. "
                        "If archive sync keeps failing, install the package on the remote ComfyUI host with ComfyUI Manager "
                        "or clone/copy it manually to the same remote custom_nodes relative path."
                    ),
                }
            )
    fatal = any(item.get("ok") is False for item in results)
    report = {
        "schema_version": "custom-node-sync-report-v1",
        "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "packages": results,
        "summary": {
            "package_count": len(results),
            "synced": 0 if args.dry_run else sum(1 for item in results if item.get("action") == "synced"),
            "failed": sum(1 for item in results if item.get("action") == "failed"),
            "dry_run": bool(args.dry_run),
        },
        "fatal": fatal,
        "dry_run": bool(args.dry_run),
        "remote_custom_nodes_root": REMOTE_CUSTOM_NODES_ROOT,
        "remote_transfer_root": REMOTE_TRANSFER_ROOT,
    }
    output = args.output or args.custom_nodes_plan.with_name("custom_nodes_sync_report.json")
    write_json(output, report)
    print(json.dumps({"ok": not fatal, "output": str(output), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
