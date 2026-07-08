#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Callable


DEFAULT_PROJECT_ROOT = Path(os.environ.get("REMOTE_SAMPLING_PROJECT_ROOT", r"F:\TieguoDun\Remote_comfyui"))
DEFAULT_REMOTE_BASE = os.environ.get("REMOTE_SAMPLING_REMOTE_BASE", "/home/user02/remote_ComfyUI")
DEFAULT_SERVER_EXEC = Path(
    os.environ.get(
        "REMOTE_SAMPLING_SERVER_EXEC",
        r"C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py",
    )
)
REMOTE_SESSION_PATH = Path(__file__).resolve().parents[1] / "ComfyUI-Remote-Sampling" / "remote_session.py"


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


def run_command(
    args: list[str],
    *,
    timeout: int,
    attempts: int = 3,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    completed = remote_session.run_subprocess_with_retry(
        args,
        timeout=timeout,
        attempts=attempts,
        runner=runner,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return completed.stdout


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_sha256sum(text: str) -> str:
    for line in text.splitlines():
        first = line.strip().split(maxsplit=1)[0] if line.strip() else ""
        if len(first) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in first):
            return first.lower()
    raise ValueError(f"could not find sha256sum output in command result:\n{text[-1000:]}")


def remote_sha256sum(server_exec: Path, remote_path: str, *, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> str:
    command = "cd /home/user02/remote_ComfyUI && sha256sum -- " + shlex.quote(remote_path)
    output = run_command(
        ["python", str(server_exec), "--cmd", command],
        timeout=7200,
        attempts=3,
        runner=runner,
    )
    return extract_sha256sum(output)


def local_expected_sha256(item: dict[str, Any], plan: dict[str, Any], local_path: Path) -> tuple[str | None, str]:
    index = item.get("index")
    plan_item: dict[str, Any] = {}
    if index is not None:
        try:
            plan_item = plan.get("resources", [])[int(index)]
        except (IndexError, TypeError, ValueError):
            plan_item = {}
    file_info = plan_item.get("local", {}).get("file") if isinstance(plan_item.get("local"), dict) else None
    if isinstance(file_info, dict) and file_info.get("sha256"):
        return str(file_info["sha256"]).lower(), str(file_info.get("sha256_policy") or "inline_sha256")
    return None, "not_available"


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


def target_remote_path(item: dict[str, Any], plan: dict[str, Any], *, remote_base: str = DEFAULT_REMOTE_BASE) -> str:
    if item.get("remote_path"):
        return remote_session.ensure_remote_under(str(item["remote_path"]), remote_base, label="remote_path")
    index = int(item.get("index"))
    plan_item = plan.get("resources", [])[index]
    remote = plan_item.get("remote", {})
    primary = remote.get("primary_path")
    if not primary:
        raise ValueError(f"resource has no remote primary path: {item}")
    return remote_session.ensure_remote_under(str(primary), remote_base, label="remote.primary_path")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload resources marked upload_required by resources_diff.json.")
    parser.add_argument("resources_plan", type=Path)
    parser.add_argument("resources_diff", type=Path)
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-size-mismatch", action="store_true", help="Also upload size_mismatch resources. Default is fail-closed.")
    parser.add_argument("--remote-base", default=DEFAULT_REMOTE_BASE, help="Allowed remote root for resource uploads.")
    parser.add_argument("--server-exec", type=Path, default=DEFAULT_SERVER_EXEC)
    parser.add_argument(
        "--hash-strategy",
        choices=("size_only", "sha256_on_demand", "sha256_required"),
        default="size_only",
        help="Post-upload verification policy. size_only records sizes only; sha256_on_demand verifies when local SHA256 is already available; sha256_required computes and verifies SHA256.",
    )
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

    results: list[dict[str, Any]] = []
    fatal_errors: list[dict[str, Any]] = []
    for item in resources_to_sync(diff, selected):
        local_path = Path(str(item["local_path"]))
        if not local_path.is_file():
            raise FileNotFoundError(local_path)
        remote_path = target_remote_path(item, plan, remote_base=args.remote_base)
        started = time.time()
        result = {
            "kind": item.get("kind"),
            "relative_path": item.get("relative_path"),
            "local_path": str(local_path),
            "remote_path": remote_path,
            "bytes": local_path.stat().st_size,
            "hash_strategy": args.hash_strategy,
            "status": "uploading",
            "action": "uploading",
            "uploader": str(uploader),
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            output = run_command(["python", str(uploader), f"{local_path}={remote_path}"], timeout=7200, attempts=3)
            expected_sha256, sha256_policy = local_expected_sha256(item, plan, local_path)
            local_sha256_source = sha256_policy
            if args.hash_strategy == "sha256_required" and not expected_sha256:
                expected_sha256 = sha256_file(local_path)
                local_sha256_source = "computed_by_sync"
            remote_sha256 = None
            sha256_verified = None
            if args.hash_strategy == "sha256_required" or (
                args.hash_strategy == "sha256_on_demand" and expected_sha256
            ):
                remote_sha256 = remote_sha256sum(args.server_exec, remote_path)
                sha256_verified = expected_sha256 == remote_sha256
                if not sha256_verified:
                    raise RuntimeError(
                        f"remote SHA256 mismatch for {remote_path}: local {expected_sha256}, remote {remote_sha256}"
                    )
            result.update(
                {
                    "status": "uploaded",
                    "action": "uploaded",
                    "elapsed_sec": round(time.time() - started, 3),
                    "local_sha256": expected_sha256,
                    "local_sha256_source": local_sha256_source,
                    "remote_sha256": remote_sha256,
                    "sha256_verified": sha256_verified,
                    "upload_log_tail": output[-2000:],
                }
            )
        except Exception as exc:
            result.update(
                {
                    "status": "failed",
                    "action": "failed",
                    "elapsed_sec": round(time.time() - started, 3),
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc)[-4000:],
                    },
                    "resume_hint": f"Re-run Check & Sync or this command after the SSH/tunnel issue is fixed. Target: {remote_path}",
                }
            )
            fatal_errors.append(result)
        results.append(
            result
        )

    report = {
        "schema_version": "resources-sync-report-v1",
        "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "remote_base": args.remote_base,
        "resources": results,
        "summary": {
            "uploaded": sum(1 for item in results if item["status"] == "uploaded"),
            "failed": sum(1 for item in results if item["status"] == "failed"),
            "sha256_verified": sum(1 for item in results if item.get("sha256_verified") is True),
            "bytes": sum(int(item["bytes"]) for item in results if item["status"] == "uploaded"),
        },
        "fatal": bool(fatal_errors),
    }
    output_path = args.output or args.resources_diff.with_name("resources_sync_report.json")
    write_json(output_path, report)
    print(json.dumps({"ok": not report["fatal"], "output": str(output_path), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 1 if report["fatal"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
