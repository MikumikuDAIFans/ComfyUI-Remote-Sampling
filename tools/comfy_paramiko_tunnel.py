#!/usr/bin/env python3
"""Forward a local port to remote ComfyUI through company-lab.

This helper imports the existing company-lab server_exec.py connection facts.
It does not store credentials in this repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import select
import socket
import subprocess
import sys
import threading
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


def copy_stream(src, dst) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


def handle_client(client_sock: socket.socket, ssh_client: paramiko.SSHClient, remote_host: str, remote_port: int) -> None:
    peer = client_sock.getpeername()
    transport = ssh_client.get_transport()
    if transport is None:
        client_sock.close()
        return

    try:
        chan = transport.open_channel(
            "direct-tcpip",
            (remote_host, remote_port),
            peer,
        )
    except Exception:
        client_sock.close()
        return

    t1 = threading.Thread(target=copy_stream, args=(client_sock, chan), daemon=True)
    t2 = threading.Thread(target=copy_stream, args=(chan, client_sock), daemon=True)
    t1.start()
    t2.start()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-port", type=int, default=18188)
    parser.add_argument("--remote-host", default="127.0.0.1")
    parser.add_argument("--remote-port", type=int, default=8188)
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

        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            "127.0.0.1",
            port=ssh_port,
            username=server_exec.SERVER_USER,
            password=server_exec.SERVER_PASSWORD,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
            look_for_keys=False,
            allow_agent=False,
        )

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", args.local_port))
            listener.listen(64)
            print(
                f"forwarding http://127.0.0.1:{args.local_port} "
                f"-> {server_exec.SERVER_HOST}:{args.remote_host}:{args.remote_port}",
                flush=True,
            )
            while True:
                readable, _, _ = select.select([listener], [], [], 1.0)
                if listener not in readable:
                    if jump_tunnel.poll() is not None:
                        return jump_tunnel.returncode or 1
                    transport = ssh_client.get_transport()
                    if transport is None or not transport.is_active():
                        return 1
                    continue
                client_sock, _addr = listener.accept()
                threading.Thread(
                    target=handle_client,
                    args=(client_sock, ssh_client, args.remote_host, args.remote_port),
                    daemon=True,
                ).start()
    finally:
        try:
            jump_tunnel.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
