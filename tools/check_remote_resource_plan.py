#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


DEFAULT_SERVER_EXEC = Path(
    os.environ.get(
        "REMOTE_SAMPLING_SERVER_EXEC",
        r"C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py",
    )
)


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


def extract_json_array(text: str) -> list[dict[str, Any]]:
    start = text.find("[\n")
    end = text.rfind("\n]")
    if start == -1 or end == -1:
        raise ValueError(f"could not find JSON array in server_exec output:\n{text[-2000:]}")
    data = json.loads(text[start : end + 2])
    if not isinstance(data, list):
        raise TypeError("remote result must be a JSON array")
    return data


def remote_check(resources: list[dict[str, Any]], server_exec: Path) -> list[dict[str, Any]]:
    checks = [
        {
            "index": index,
            "kind": item.get("kind"),
            "relative_path": item.get("relative_path"),
            "paths": item.get("remote", {}).get("candidates", []),
        }
        for index, item in enumerate(resources)
    ]
    encoded = base64.b64encode(json.dumps(checks, ensure_ascii=False).encode("utf-8")).decode("ascii")
    remote_python = (
        "import base64,json,os;"
        f"checks=json.loads(base64.b64decode({encoded!r}).decode('utf-8'));"
        "out=[]\n"
        "for c in checks:\n"
        "    found=None; size=None\n"
        "    for p in c['paths']:\n"
        "        if os.path.exists(p):\n"
        "            found=p; size=os.stat(p).st_size; break\n"
        "    out.append({'index':c['index'],'kind':c['kind'],'relative_path':c['relative_path'],'remote_path':found,'exists':found is not None,'size':size,'candidates':c['paths']})\n"
        "print(json.dumps(out, ensure_ascii=False, indent=2))"
    )
    command = "cd /home/user02/remote_ComfyUI && python3 -c " + shlex.quote(remote_python)
    completed = subprocess.run(
        ["python", str(server_exec), "--cmd", command],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return extract_json_array(completed.stdout)


def build_diff(plan: dict[str, Any], remote: list[dict[str, Any]]) -> dict[str, Any]:
    resources = plan.get("resources", [])
    remote_by_index = {item.get("index"): item for item in remote}
    items = []
    for index, resource in enumerate(resources):
        remote_item = remote_by_index.get(index, {})
        local_file = resource.get("local", {}).get("file") or {}
        local_size = local_file.get("size")
        remote_size = remote_item.get("size")
        local_exists = bool(resource.get("local", {}).get("exists"))
        remote_exists = bool(remote_item.get("exists"))
        if not local_exists:
            action = "blocked_local_missing"
        elif not remote_exists:
            action = "upload_required"
        elif local_size is not None and remote_size is not None and int(local_size) != int(remote_size):
            action = "size_mismatch"
        else:
            action = "ready"
        items.append(
            {
                "index": index,
                "kind": resource.get("kind"),
                "relative_path": resource.get("relative_path"),
                "local_path": resource.get("local", {}).get("path"),
                "local_size": local_size,
                "remote_path": remote_item.get("remote_path"),
                "remote_size": remote_size,
                "remote_exists": remote_exists,
                "action": action,
                "upload_command_hint": resource.get("sync", {}).get("upload_command_hint"),
            }
        )
    return {
        "schema_version": "resources-diff-v1",
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "relative_path_policy": plan.get("relative_path_policy"),
        "resources": items,
        "summary": {
            "total": len(items),
            "ready": sum(1 for item in items if item["action"] == "ready"),
            "upload_required": sum(1 for item in items if item["action"] == "upload_required"),
            "size_mismatch": sum(1 for item in items if item["action"] == "size_mismatch"),
            "blocked_local_missing": sum(1 for item in items if item["action"] == "blocked_local_missing"),
        },
        "fatal": any(item["action"] in {"size_mismatch", "blocked_local_missing"} for item in items),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a workflow runtime resources_plan.json against the remote ComfyUI models tree.")
    parser.add_argument("resources_plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-exec", type=Path, default=DEFAULT_SERVER_EXEC)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = read_json(args.resources_plan)
    remote = remote_check(plan.get("resources", []), args.server_exec)
    diff = build_diff(plan, remote)
    output = args.output or args.resources_plan.with_name("resources_diff.json")
    write_json(output, diff)
    print(json.dumps({"ok": not diff["fatal"], "output": str(output), "summary": diff["summary"]}, ensure_ascii=False, indent=2))
    return 1 if diff["fatal"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
