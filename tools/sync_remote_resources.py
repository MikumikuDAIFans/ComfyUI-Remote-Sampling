#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


DEFAULT_PROJECT_ROOT = Path(os.environ.get("REMOTE_SAMPLING_PROJECT_ROOT", r"F:\TieguoDun\Remote_comfyui"))


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


def run_command(args: list[str], *, timeout: int) -> str:
    completed = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return completed.stdout


def resources_to_sync(diff: dict[str, Any], selected_actions: set[str]) -> list[dict[str, Any]]:
    return [
        item
        for item in diff.get("resources", [])
        if item.get("action") in selected_actions and item.get("local_path") and item.get("remote_path") is None
    ] + [
        item
        for item in diff.get("resources", [])
        if item.get("action") in selected_actions and item.get("local_path") and item.get("remote_path")
    ]


def target_remote_path(item: dict[str, Any], plan: dict[str, Any]) -> str:
    if item.get("remote_path"):
        return str(item["remote_path"])
    index = int(item.get("index"))
    plan_item = plan.get("resources", [])[index]
    remote = plan_item.get("remote", {})
    primary = remote.get("primary_path")
    if not primary:
        raise ValueError(f"resource has no remote primary path: {item}")
    return str(primary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload resources marked upload_required by resources_diff.json.")
    parser.add_argument("resources_plan", type=Path)
    parser.add_argument("resources_diff", type=Path)
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-size-mismatch", action="store_true", help="Also upload size_mismatch resources. Default is fail-closed.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = read_json(args.resources_plan)
    diff = read_json(args.resources_diff)
    selected = {"upload_required"}
    if args.include_size_mismatch:
        selected.add("size_mismatch")
    stream_uploader = args.project_root / "tools" / "upload_to_company_server_stream.py"
    sftp_uploader = args.project_root / "tools" / "upload_to_company_server.py"
    uploader = stream_uploader if stream_uploader.is_file() else sftp_uploader
    if not uploader.is_file():
        raise FileNotFoundError(uploader)

    results = []
    for item in resources_to_sync(diff, selected):
        local_path = Path(str(item["local_path"]))
        if not local_path.is_file():
            raise FileNotFoundError(local_path)
        remote_path = target_remote_path(item, plan)
        output = run_command(["python", str(uploader), f"{local_path}={remote_path}"], timeout=7200)
        results.append(
            {
                "kind": item.get("kind"),
                "relative_path": item.get("relative_path"),
                "local_path": str(local_path),
                "remote_path": remote_path,
                "bytes": local_path.stat().st_size,
                "action": "uploaded",
                "uploader": str(uploader),
                "upload_log_tail": output[-2000:],
            }
        )

    report = {
        "schema_version": "resources-sync-report-v1",
        "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "resources": results,
        "summary": {
            "uploaded": len(results),
            "bytes": sum(int(item["bytes"]) for item in results),
        },
        "fatal": False,
    }
    output_path = args.output or args.resources_diff.with_name("resources_sync_report.json")
    write_json(output_path, report)
    print(json.dumps({"ok": True, "output": str(output_path), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
