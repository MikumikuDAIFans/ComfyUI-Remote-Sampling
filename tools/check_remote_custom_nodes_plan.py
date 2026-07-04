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


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{\n")
    end = text.rfind("\n}")
    if start == -1 or end == -1:
        raise ValueError(f"could not find JSON object in server_exec output:\n{text[-2000:]}")
    data = json.loads(text[start : end + 2])
    if not isinstance(data, dict):
        raise TypeError("remote result must be a JSON object")
    return data


def remote_check(plan: dict[str, Any], server_exec: Path) -> dict[str, Any]:
    packages = [
        {
            "package_name": item.get("package_name"),
            "remote_path": item.get("remote_path"),
            "classes": item.get("classes", []),
            "dependency_files": [dep.get("name") for dep in item.get("dependency_files", [])],
        }
        for item in plan.get("packages", [])
    ]
    encoded = base64.b64encode(json.dumps(packages, ensure_ascii=False).encode("utf-8")).decode("ascii")
    remote_python = (
        "import base64,json,os;"
        f"packages=json.loads(base64.b64decode({encoded!r}).decode('utf-8'));"
        "out={'packages':[]}\n"
        "for p in packages:\n"
        "    path=p.get('remote_path') or ''\n"
        "    exists=os.path.isdir(path)\n"
        "    init_exists=os.path.isfile(os.path.join(path,'__init__.py')) if exists else False\n"
        "    deps=[]\n"
        "    for name in p.get('dependency_files') or []:\n"
        "        dep_path=os.path.join(path,name)\n"
        "        deps.append({'name':name,'exists':os.path.isfile(dep_path),'path':dep_path})\n"
        "    out['packages'].append({'package_name':p.get('package_name'),'remote_path':path,'exists':exists,'init_exists':init_exists,'classes':p.get('classes',[]),'dependency_files':deps})\n"
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
    return extract_json_object(completed.stdout)


def build_report(plan: dict[str, Any], remote: dict[str, Any]) -> dict[str, Any]:
    package_by_name = {item.get("package_name"): item for item in remote.get("packages", [])}
    packages = []
    for package in plan.get("packages", []):
        remote_item = package_by_name.get(package.get("package_name"), {})
        exists = bool(remote_item.get("exists"))
        init_exists = bool(remote_item.get("init_exists"))
        if not exists:
            action = "sync_required"
        elif not init_exists:
            action = "remote_package_incomplete"
        else:
            action = "ready_for_import_smoke"
        packages.append(
            {
                "package_name": package.get("package_name"),
                "classes": package.get("classes", []),
                "local_path": package.get("local_path"),
                "remote_path": package.get("remote_path"),
                "git_remote": package.get("git_remote"),
                "remote_exists": exists,
                "remote_init_exists": init_exists,
                "dependency_files": remote_item.get("dependency_files", []),
                "action": action,
                "manual_sync_hint": f'Compress "{package.get("local_path")}" and extract it to "{package.get("remote_path")}".',
            }
        )
    return {
        "schema_version": "remote-environment-report-v1",
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "remote_base": plan.get("remote_base"),
        "remote_custom_nodes_root": plan.get("remote_custom_nodes_root"),
        "packages": packages,
        "summary": {
            "package_count": len(packages),
            "ready_for_import_smoke": sum(1 for item in packages if item["action"] == "ready_for_import_smoke"),
            "sync_required": sum(1 for item in packages if item["action"] == "sync_required"),
            "remote_package_incomplete": sum(1 for item in packages if item["action"] == "remote_package_incomplete"),
        },
        "fatal": any(item["action"] == "remote_package_incomplete" for item in packages),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check custom_nodes_plan.json against the remote ComfyUI custom_nodes tree.")
    parser.add_argument("custom_nodes_plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-exec", type=Path, default=DEFAULT_SERVER_EXEC)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = read_json(args.custom_nodes_plan)
    remote = remote_check(plan, args.server_exec)
    report = build_report(plan, remote)
    output = args.output or args.custom_nodes_plan.with_name("remote_environment_report.json")
    write_json(output, report)
    print(json.dumps({"ok": not report["fatal"], "output": str(output), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 1 if report["fatal"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
