#!/usr/bin/env python3
"""Stream files to the company DGX server over SSH stdin.

This avoids Paramiko SFTP's per-write acknowledgement overhead on high-latency
jump-host links. Connection facts are imported from the existing company-lab
skill script; no credentials are stored in this repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import posixpath
import shlex
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
CHUNK_SIZE = 4 * 1024 * 1024


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


def run_text(client: paramiko.SSHClient, command: str) -> str:
    _stdin, stdout, stderr = client.exec_command(command)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if code:
        raise RuntimeError(f"remote command failed ({code}): {command}\n{err}")
    return out


def remote_size(client: paramiko.SSHClient, remote: str) -> int | None:
    quoted = shlex.quote(remote)
    out = run_text(client, f"python3 - <<'PY'\nfrom pathlib import Path\np = Path({remote!r})\nprint(p.stat().st_size if p.exists() else '')\nPY")
    text = out.strip()
    return int(text) if text else None


def ensure_remote_dir(client: paramiko.SSHClient, remote_dir: str) -> None:
    run_text(client, f"mkdir -p -- {shlex.quote(remote_dir)}")


def stream_append(client: paramiko.SSHClient, local: Path, remote: str, offset: int, size: int) -> None:
    tmp_remote = remote + ".uploading"
    command = f"umask 077; cat >> {shlex.quote(tmp_remote)}"
    channel = client.get_transport().open_session()  # type: ignore[union-attr]
    channel.exec_command(command)

    last_print = 0.0
    sent = offset

    def progress(force: bool = False) -> None:
        nonlocal last_print
        now = time.time()
        if force or now - last_print >= 5:
            pct = (sent / size * 100) if size else 100.0
            print(f"{local.name}: {sent}/{size} bytes ({pct:.1f}%)", flush=True)
            last_print = now

    with local.open("rb") as src:
        src.seek(offset)
        progress(force=True)
        while True:
            chunk = src.read(CHUNK_SIZE)
            if not chunk:
                break
            channel.sendall(chunk)
            sent += len(chunk)
            progress()

    channel.shutdown_write()
    code = channel.recv_exit_status()
    stderr = b""
    while channel.recv_stderr_ready():
        stderr += channel.recv_stderr(65536)
    if code:
        raise RuntimeError(f"remote stream write failed ({code}): {stderr.decode('utf-8', errors='replace')}")
    progress(force=True)


def upload_file(client: paramiko.SSHClient, local: Path, remote: str) -> None:
    size = local.stat().st_size
    ensure_remote_dir(client, posixpath.dirname(remote))

    final_size = remote_size(client, remote)
    if final_size == size:
        print(f"skip {remote}: already complete ({size} bytes)", flush=True)
        return
    if final_size is not None and final_size != size:
        raise RuntimeError(f"remote file exists with unexpected size: {remote} ({final_size} != {size})")

    tmp_remote = remote + ".uploading"
    offset = remote_size(client, tmp_remote) or 0
    if offset > size:
        raise RuntimeError(f"temporary file is larger than local file: {tmp_remote} ({offset} > {size})")

    action = "resume" if offset else "upload"
    print(f"{action} {local} -> {remote} ({offset}/{size} bytes)", flush=True)
    stream_append(client, local, remote, offset, size)

    completed_size = remote_size(client, tmp_remote)
    if completed_size != size:
        raise RuntimeError(f"upload incomplete: {tmp_remote} ({completed_size} != {size})")
    run_text(client, f"mv -f -- {shlex.quote(tmp_remote)} {shlex.quote(remote)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pair", nargs="+", help="Upload pair formatted as local_path=remote_abs_path.")
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
        transport = client.get_transport()
        if transport is not None:
            transport.set_keepalive(30)
        try:
            for pair in args.pair:
                if "=" not in pair:
                    raise ValueError(f"expected local=remote pair, got {pair!r}")
                local_s, remote = pair.split("=", 1)
                local = Path(local_s)
                if not local.is_file():
                    raise FileNotFoundError(local)
                upload_file(client, local, remote)
        finally:
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
