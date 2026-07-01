#!/usr/bin/env python3
"""Upload local files to the company DGX server through company-lab.

Connection facts are imported from the existing company-lab skill script.
No credentials are stored in this repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import posixpath
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


def mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = [p for p in remote_dir.split("/") if p]
    current = "/" if remote_dir.startswith("/") else "."
    for part in parts:
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def remote_size(sftp: paramiko.SFTPClient, remote: str) -> int | None:
    try:
        return sftp.stat(remote).st_size
    except FileNotFoundError:
        return None


def upload_file(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    size = local.stat().st_size
    mkdir_p(sftp, posixpath.dirname(remote))
    last_print = 0.0

    final_size = remote_size(sftp, remote)
    if final_size == size:
        print(f"skip {remote}: already complete ({size} bytes)", flush=True)
        return
    if final_size is not None and final_size != size:
        raise RuntimeError(f"remote file exists with unexpected size: {remote} ({final_size} != {size})")

    tmp_remote = remote + ".uploading"
    offset = remote_size(sftp, tmp_remote) or 0
    if offset > size:
        raise RuntimeError(f"temporary file is larger than local file: {tmp_remote} ({offset} > {size})")

    def progress(sent: int) -> None:
        nonlocal last_print
        now = time.time()
        if now - last_print >= 5 or sent == size:
            pct = (sent / size * 100) if size else 100.0
            print(f"{local.name}: {sent}/{size} bytes ({pct:.1f}%)", flush=True)
            last_print = now

    action = "resume" if offset else "upload"
    print(f"{action} {local} -> {remote} ({offset}/{size} bytes)", flush=True)
    with local.open("rb") as src, sftp.file(tmp_remote, "ab") as dst:
        dst.set_pipelined(True)
        src.seek(offset)
        sent = offset
        progress(sent)
        while True:
            chunk = src.read(CHUNK_SIZE)
            if not chunk:
                break
            dst.write(chunk)
            sent += len(chunk)
            progress(sent)
        dst.flush()

    completed_size = remote_size(sftp, tmp_remote)
    if completed_size != size:
        raise RuntimeError(f"upload incomplete: {tmp_remote} ({completed_size} != {size})")
    sftp.rename(tmp_remote, remote)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "pair",
        nargs="+",
        help="Upload pair formatted as local_path=remote_abs_path.",
    )
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
        if transport is None:
            raise RuntimeError("SSH transport was not established")
        transport.set_keepalive(30)
        sftp = paramiko.SFTPClient.from_transport(
            transport,
            window_size=128 * 1024 * 1024,
            max_packet_size=16 * 1024 * 1024,
        )
        try:
            for pair in args.pair:
                if "=" not in pair:
                    raise ValueError(f"expected local=remote pair, got {pair!r}")
                local_s, remote = pair.split("=", 1)
                local = Path(local_s)
                if not local.is_file():
                    raise FileNotFoundError(local)
                upload_file(sftp, local, remote)
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
