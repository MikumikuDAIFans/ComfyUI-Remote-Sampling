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
REMOTE_PYTHON = os.environ.get("REMOTE_SAMPLING_REMOTE_PYTHON", "/home/user02/remote_ComfyUI/.venv/bin/python")


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


def run_remote(command: str, server_exec: Path, timeout: int) -> str:
    completed = subprocess.run(
        ["python", str(server_exec), "--cmd", command, "--timeout", str(timeout)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout + 30,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return completed.stdout


def dependency_commands(plan: dict[str, Any]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for package in plan.get("packages", []):
        package_name = str(package.get("package_name"))
        remote_path = str(package.get("remote_path"))
        deps = package.get("dependency_files", [])
        names = {str(item.get("name")) for item in deps if item.get("name")}
        if "requirements.txt" in names:
            req = f"{remote_path}/requirements.txt"
            commands.append(
                {
                    "package_name": package_name,
                    "kind": "requirements.txt",
                    "remote_file": req,
                    "command": f"{shlex.quote(REMOTE_PYTHON)} -m pip install -r {shlex.quote(req)}",
                }
            )
        if "pyproject.toml" in names and "requirements.txt" not in names:
            commands.append(
                {
                    "package_name": package_name,
                    "kind": "pyproject.toml",
                    "remote_file": f"{remote_path}/pyproject.toml",
                    "command": f"{shlex.quote(REMOTE_PYTHON)} -m pip install {shlex.quote(remote_path)}",
                }
            )
    return commands


def execute_commands(commands: list[dict[str, Any]], server_exec: Path, timeout: int) -> list[dict[str, Any]]:
    encoded = base64.b64encode(json.dumps(commands, ensure_ascii=False).encode("utf-8")).decode("ascii")
    remote_python = (
        "import base64,json,subprocess;"
        f"commands=json.loads(base64.b64decode({encoded!r}).decode('utf-8'));"
        "out=[]\n"
        "for item in commands:\n"
        "    cp=subprocess.run(item['command'], shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)\n"
        "    result=dict(item)\n"
        "    result['returncode']=cp.returncode\n"
        "    result['output_tail']=cp.stdout[-4000:]\n"
        "    result['ok']=cp.returncode==0\n"
        "    out.append(result)\n"
        "print(json.dumps({'commands': out}, ensure_ascii=False, indent=2))"
    )
    text = run_remote("cd /home/user02/remote_ComfyUI && python3 -c " + shlex.quote(remote_python), server_exec, timeout)
    start = text.find("{\n")
    end = text.rfind("\n}")
    if start == -1 or end == -1:
        raise ValueError(f"could not parse remote install output:\n{text[-2000:]}")
    data = json.loads(text[start : end + 2])
    return list(data.get("commands", []))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or execute remote dependency install commands for custom node packages.")
    parser.add_argument("custom_nodes_plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-exec", type=Path, default=DEFAULT_SERVER_EXEC)
    parser.add_argument("--execute", action="store_true", help="Actually run pip install commands on the remote host.")
    parser.add_argument("--timeout", type=int, default=2400)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = read_json(args.custom_nodes_plan)
    commands = dependency_commands(plan)
    if args.execute and commands:
        results = execute_commands(commands, args.server_exec, args.timeout)
    else:
        results = [{**item, "ok": None, "returncode": None, "output_tail": None} for item in commands]
    report = {
        "schema_version": "remote-custom-node-dependency-install-v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "execute": bool(args.execute),
        "commands": results,
        "summary": {
            "command_count": len(results),
            "executed": bool(args.execute),
            "failed": sum(1 for item in results if item.get("ok") is False),
        },
        "fatal": any(item.get("ok") is False for item in results),
        "notes": [
            "Default mode is dry-run to avoid unapproved network installation of unknown dependencies.",
            "Use --execute only when the operator has approved installing the listed package dependencies.",
        ],
    }
    output = args.output or args.custom_nodes_plan.with_name("remote_custom_node_dependency_install.json")
    write_json(output, report)
    print(json.dumps({"ok": not report["fatal"], "output": str(output), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 1 if report["fatal"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
