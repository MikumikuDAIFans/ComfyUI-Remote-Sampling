#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
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
    completed = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return completed.stdout


def upload_archive(project_root: Path, archive: Path, remote_archive: str) -> str:
    uploader = project_root / "tools" / "upload_to_company_server.py"
    if not uploader.is_file():
        raise FileNotFoundError(uploader)
    return run_command(["python", str(uploader), f"{archive}={remote_archive}"], timeout=1800)


def extract_remote(server_exec: Path, remote_archive: str, remote_path: str) -> str:
    remote_parent = str(Path(remote_path).parent).replace("\\", "/")
    remote_python = (
        "import os,shutil,zipfile;"
        f"archive={remote_archive!r};"
        f"target={remote_path!r};"
        f"parent={remote_parent!r};"
        "os.makedirs(parent, exist_ok=True);"
        "tmp=target+'.extracting';"
        "shutil.rmtree(tmp, ignore_errors=True);"
        "os.makedirs(tmp, exist_ok=True);"
        "zipfile.ZipFile(archive).extractall(tmp);"
        "shutil.rmtree(target, ignore_errors=True);"
        "os.replace(tmp, target);"
        "print('extracted '+target)"
    )
    command = "cd /home/user02/remote_ComfyUI && python3 -c " + shlex.quote(remote_python)
    return run_command(["python", str(server_exec), "--cmd", command], timeout=600)


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = read_json(args.custom_nodes_plan)
    archive_dir = args.archive_dir or args.project_root / "transfer" / "custom_nodes"
    selected = set(args.packages) if args.packages else None
    results = []
    for package in packages_to_sync(plan, selected):
        package_name = str(package.get("package_name"))
        remote_path = str(package.get("remote_path"))
        remote_archive = f"/home/user02/remote_ComfyUI/transfer/custom_nodes/{package_name}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
        archive, file_count, bytes_total = make_archive(package, archive_dir)
        upload_log = upload_archive(args.project_root, archive, remote_archive)
        extract_log = extract_remote(args.server_exec, remote_archive, remote_path)
        results.append(
            {
                "package_name": package_name,
                "local_path": package.get("local_path"),
                "remote_path": remote_path,
                "archive": str(archive),
                "remote_archive": remote_archive,
                "file_count": file_count,
                "bytes_total": bytes_total,
                "upload_log_tail": upload_log[-2000:],
                "extract_log_tail": extract_log[-2000:],
                "action": "synced",
            }
        )
    report = {
        "schema_version": "custom-node-sync-report-v1",
        "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "packages": results,
        "summary": {"package_count": len(results), "synced": len(results)},
        "fatal": False,
    }
    output = args.output or args.custom_nodes_plan.with_name("custom_nodes_sync_report.json")
    write_json(output, report)
    print(json.dumps({"ok": True, "output": str(output), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
