#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SERVER_EXEC = Path(
    os.environ.get(
        "REMOTE_SAMPLING_SERVER_EXEC",
        r"C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py",
    )
)
REMOTE_SERVICE = PROJECT_ROOT / "tools" / "remote_comfy_service.py"


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
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"could not find JSON object:\n{text[-2000:]}")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise TypeError("expected JSON object")
    return data


def load_remote_service():
    spec = importlib.util.spec_from_file_location("remote_comfy_service", REMOTE_SERVICE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {REMOTE_SERVICE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_server_exec(command: str, server_exec: Path, timeout: int) -> str:
    completed = subprocess.run(
        ["python", str(server_exec), "--cmd", command, "--timeout", str(timeout)],
        cwd=str(PROJECT_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout + 30,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return completed.stdout


def object_info_check(classes: list[str], server_exec: Path, timeout: int) -> dict[str, Any]:
    encoded = base64.b64encode(json.dumps(classes, ensure_ascii=False).encode("utf-8")).decode("ascii")
    remote_python = (
        "import base64,json,urllib.request;"
        f"classes=json.loads(base64.b64decode({encoded!r}).decode('utf-8'));"
        "data=json.loads(urllib.request.urlopen('http://127.0.0.1:8197/object_info', timeout=20).read().decode());"
        "missing=[c for c in classes if c not in data];"
        "print(json.dumps({'object_info_count':len(data),'classes':classes,'missing_classes':missing,'ok':not missing}, ensure_ascii=False, indent=2))"
    )
    command = "cd /home/user02/remote_ComfyUI && python3 -c " + shlex.quote(remote_python)
    return extract_json_object(run_server_exec(command, server_exec, timeout))


def custom_classes(plan: dict[str, Any]) -> list[str]:
    classes: set[str] = set()
    for package in plan.get("packages", []):
        for cls in package.get("classes", []):
            classes.add(str(cls))
    for item in plan.get("classes", []):
        if item.get("class_name"):
            classes.add(str(item["class_name"]))
    return sorted(classes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start remote ComfyUI if needed and check object_info contains planned custom node classes.")
    parser.add_argument("custom_nodes_plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--server-exec", type=Path, default=DEFAULT_SERVER_EXEC)
    parser.add_argument("--timeout", type=int, default=420)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = read_json(args.custom_nodes_plan)
    classes = custom_classes(plan)
    service = load_remote_service()
    started_by_us = False
    service_status_before = extract_json_object(service.status(timeout=120))
    try:
        if classes and not service_status_before.get("api_ready"):
            start_result = extract_json_object(service.start(timeout=args.timeout))
            started_by_us = bool(start_result.get("changed"))
        if classes:
            check = object_info_check(classes, args.server_exec, args.timeout)
        else:
            check = {
                "ok": True,
                "object_info_count": None,
                "classes": [],
                "missing_classes": [],
                "reason": "no custom classes in plan",
            }
    finally:
        if started_by_us:
            service.stop(timeout=180)

    report = {
        "schema_version": "remote-custom-node-import-smoke-v1",
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "started_remote_service": started_by_us,
        "classes": classes,
        "object_info": check,
        "summary": {
            "class_count": len(classes),
            "missing_class_count": len(check.get("missing_classes", [])),
            "object_info_count": check.get("object_info_count"),
        },
        "fatal": not bool(check.get("ok")),
    }
    output = args.output or args.custom_nodes_plan.with_name("remote_custom_node_import_smoke.json")
    write_json(output, report)
    print(json.dumps({"ok": not report["fatal"], "output": str(output), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 1 if report["fatal"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
