#!/usr/bin/env python3
"""Download files from the company DGX server through company-lab.

Connection facts are imported from the existing company-lab skill script.
No credentials are stored in this repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import paramiko


# SSH/tunnel helper for the original lab environment. Set
# REMOTE_SAMPLING_SERVER_EXEC to point at a compatible helper in another setup.
SERVER_EXEC = Path(
    os.environ.get(
        "REMOTE_SAMPLING_SERVER_EXEC",
        r"C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py",
    )
)


def load_server_exec():
    spec = importlib.util.spec_from_file_location("company_lab_server_exec", SERVER_EXEC)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SERVER_EXEC}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait_local_port(port: int, timeout: float = 12.0) -> None:
    import socket

    deadline = time.time() + timeout
    last_error: OSError | None = None
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.25)
    raise TimeoutError(f"local tunnel port {port} not ready: {last_error}")


def download_file(sftp: paramiko.SFTPClient, remote: str, local: Path) -> None:
    attrs = sftp.stat(remote)
    local.parent.mkdir(parents=True, exist_ok=True)
    tmp_local = local.with_name(local.name + ".downloading")
    if tmp_local.exists():
        tmp_local.unlink()

    last_print = 0.0

    def progress(done: int, total: int) -> None:
        nonlocal last_print
        now = time.time()
        if now - last_print >= 5 or done == total:
            pct = (done / total * 100) if total else 100.0
            print(f"{local.name}: {done}/{total} bytes ({pct:.1f}%)", flush=True)
            last_print = now

    print(f"download {remote} -> {local} ({attrs.st_size} bytes)", flush=True)
    sftp.get(remote, str(tmp_local), callback=progress)
    tmp_local.replace(local)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pair", nargs="+", help="Download pair formatted as remote_abs_path=local_path.")
    args = parser.parse_args()

    server_exec = load_server_exec()
    ssh_port = server_exec.free_port()
    jump_tunnel: subprocess.Popen[str] = server_exec.open_tunnel(ssh_port)

    try:
        time.sleep(0.8)
        if jump_tunnel.poll() is not None:
            _out, err = jump_tunnel.communicate(timeout=2)
            print(err, file=sys.stderr, end="")
            return jump_tunnel.returncode or 1
        wait_local_port(ssh_port)

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            "127.0.0.1",
            port=ssh_port,
            username=server_exec.SERVER_USER,
            password=os.environ.get("DGX_SERVER_PASSWORD") or server_exec.SERVER_PASSWORD,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
            look_for_keys=False,
            allow_agent=False,
        )
        sftp = client.open_sftp()
        try:
            for pair in args.pair:
                if "=" not in pair:
                    raise ValueError(f"expected remote=local pair, got {pair!r}")
                remote, local_s = pair.split("=", 1)
                download_file(sftp, remote, Path(local_s))
        finally:
            sftp.close()
            client.close()
        return 0
    finally:
        if jump_tunnel.poll() is None:
            jump_tunnel.terminate()
            try:
                jump_tunnel.wait(timeout=4)
            except subprocess.TimeoutExpired:
                jump_tunnel.kill()


if __name__ == "__main__":
    raise SystemExit(main())
