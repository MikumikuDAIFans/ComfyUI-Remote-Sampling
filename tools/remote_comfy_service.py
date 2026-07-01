#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path


# Defaults are for the original lab machine. Override them with environment
# variables when using another SSH helper, remote project root, Python venv or
# service port.
SERVER_EXEC = Path(
    os.environ.get(
        "REMOTE_SAMPLING_SERVER_EXEC",
        r"C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py",
    )
)
REMOTE_BASE = os.environ.get("REMOTE_SAMPLING_REMOTE_BASE", "/home/user02/remote_ComfyUI")
REMOTE_COMFY = f"{REMOTE_BASE}/ComfyUI"
REMOTE_PYTHON = os.environ.get("REMOTE_SAMPLING_REMOTE_PYTHON", f"{REMOTE_BASE}/.venv/bin/python")
REMOTE_PORT = int(os.environ.get("REMOTE_SAMPLING_REMOTE_PORT", "8197"))
TMUX_SESSION = os.environ.get("REMOTE_SAMPLING_TMUX_SESSION", f"remote-comfyui-{REMOTE_PORT}")
DATABASE_URL = f"sqlite:///{REMOTE_COMFY}/user/remote_comfy_service_{REMOTE_PORT}.db"


def run_remote(command: str, timeout: int = 120) -> str:
    completed = subprocess.run(
        [sys.executable, str(SERVER_EXEC), "--cmd", command, "--timeout", str(timeout)],
        cwd=str(Path(__file__).resolve().parents[1]),
        text=True,
        capture_output=True,
        timeout=timeout + 30,
    )
    output = completed.stdout
    if completed.stderr:
        output += completed.stderr
    if completed.returncode != 0:
        raise RuntimeError(output)
    return output


def remote_python(source: str, timeout: int = 120) -> str:
    command = "python3 - <<'PY'\n" + source.rstrip() + "\nPY\n"
    return run_remote(command, timeout=timeout)


def status(timeout: int = 120) -> str:
    return remote_python(
        f"""
import json, subprocess, urllib.request
session = {TMUX_SESSION!r}
port = {REMOTE_PORT!r}
info = {{"session": session, "port": port}}
tmux = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True, text=True)
info["tmux_running"] = tmux.returncode == 0
ss = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True)
lines = [line for line in ss.stdout.splitlines() if f":{{port}} " in line]
info["port_listeners"] = lines
try:
    data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{{port}}/object_info", timeout=5).read().decode())
    info["api_ready"] = True
    info["object_info_count"] = len(data)
    info["has_remote_sampling_remote"] = "Remote_Sampling_remote" in data
except Exception as exc:
    info["api_ready"] = False
    info["api_error"] = repr(exc)
print(json.dumps(info, ensure_ascii=False, indent=2))
""",
        timeout=timeout,
    )


def start(timeout: int = 300) -> str:
    return remote_python(
        f"""
import json, subprocess, time, urllib.request
session = {TMUX_SESSION!r}
base = {REMOTE_BASE!r}
remote_python = {REMOTE_PYTHON!r}
remote_comfy = {REMOTE_COMFY!r}
port = {REMOTE_PORT!r}
database_url = {DATABASE_URL!r}

ss = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True)
if any(f":{{port}} " in line for line in ss.stdout.splitlines()):
    print(json.dumps({{"ok": True, "changed": False, "reason": "port already listening", "session": session, "port": port}}, ensure_ascii=False))
    raise SystemExit(0)

tmux = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True, text=True)
if tmux.returncode == 0:
    subprocess.run(["tmux", "kill-session", "-t", session], check=False)

service_cmd = (
    f"cd {{base}} && exec {{remote_python}} {{remote_comfy}}/main.py "
    f"--listen 127.0.0.1 --port {{port}} --disable-auto-launch "
    f"--database-url {{database_url}}"
)
subprocess.run(["tmux", "new-session", "-d", "-s", session, "-c", base, "bash", "-lc", service_cmd], check=True)

deadline = time.time() + {timeout}
last = None
while time.time() < deadline:
    try:
        data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{{port}}/object_info", timeout=5).read().decode())
        print(json.dumps({{
            "ok": True,
            "changed": True,
            "session": session,
            "port": port,
            "object_info_count": len(data),
            "has_remote_sampling_remote": "Remote_Sampling_remote" in data,
        }}, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    except Exception as exc:
        last = repr(exc)
        time.sleep(2)
print(json.dumps({{"ok": False, "changed": True, "session": session, "port": port, "error": last}}, ensure_ascii=False, indent=2))
raise SystemExit(2)
""",
        timeout=timeout + 60,
    )


def stop(timeout: int = 120) -> str:
    return remote_python(
        f"""
import json, subprocess, time
session = {TMUX_SESSION!r}
port = {REMOTE_PORT!r}
changed = False
tmux = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True, text=True)
if tmux.returncode == 0:
    subprocess.run(["tmux", "kill-session", "-t", session], check=False)
    changed = True
time.sleep(2)
ss = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True)
lines = [line for line in ss.stdout.splitlines() if f":{{port}} " in line]
if lines:
    subprocess.run(["pkill", "-f", f"main.py --listen 127.0.0.1 --port {{port}}"], check=False)
    changed = True
    time.sleep(2)
ss2 = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True)
lines2 = [line for line in ss2.stdout.splitlines() if f":{{port}} " in line]
print(json.dumps({{"ok": not bool(lines2), "changed": changed, "session": session, "port": port, "remaining_listeners": lines2}}, ensure_ascii=False, indent=2))
raise SystemExit(0 if not lines2 else 2)
""",
        timeout=timeout,
    )


def logs(lines: int, timeout: int = 120) -> str:
    return run_remote(
        f"tmux capture-pane -pt {TMUX_SESSION} -S -{int(lines)} 2>/dev/null || echo 'tmux session not running: {TMUX_SESSION}'",
        timeout=timeout,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the remote ComfyUI tmux service for remote sampling.")
    parser.add_argument("action", choices=["status", "start", "stop", "logs"])
    parser.add_argument("--lines", type=int, default=80, help="Number of tmux log lines for the logs action.")
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.action == "status":
        print(status(timeout=args.timeout), end="")
    elif args.action == "start":
        print(start(timeout=args.timeout), end="")
    elif args.action == "stop":
        print(stop(timeout=args.timeout), end="")
    elif args.action == "logs":
        print(logs(args.lines, timeout=args.timeout), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
