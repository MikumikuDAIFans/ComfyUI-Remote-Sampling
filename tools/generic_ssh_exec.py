#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys


def ssh_target() -> str:
    target = os.environ.get("REMOTE_SAMPLING_SSH_TARGET", "").strip()
    if target:
        return target
    host = os.environ.get("REMOTE_SAMPLING_SSH_HOST", "").strip()
    user = os.environ.get("REMOTE_SAMPLING_SSH_USER", "").strip()
    if not host:
        raise RuntimeError("Set REMOTE_SAMPLING_SSH_TARGET or REMOTE_SAMPLING_SSH_HOST.")
    return f"{user}@{host}" if user else host


def build_ssh_args(command: str, timeout: int) -> list[str]:
    args = ["ssh"]
    port = os.environ.get("REMOTE_SAMPLING_SSH_PORT", "").strip()
    key = os.environ.get("REMOTE_SAMPLING_SSH_KEY", "").strip()
    options = os.environ.get("REMOTE_SAMPLING_SSH_OPTIONS", "").strip()
    if port:
        args.extend(["-p", port])
    if key:
        args.extend(["-i", key])
    args.extend(["-o", "BatchMode=yes", "-o", f"ConnectTimeout={min(timeout, 30)}"])
    if options:
        args.extend(options.split())
    args.extend([ssh_target(), command])
    return args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generic SSH command executor compatible with REMOTE_SAMPLING_SERVER_EXEC.")
    parser.add_argument("--cmd", required=True, help="Remote shell command to execute.")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    completed = subprocess.run(
        build_ssh_args(args.cmd, args.timeout),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=args.timeout,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    return completed.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
