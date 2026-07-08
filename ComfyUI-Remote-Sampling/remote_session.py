from __future__ import annotations

import posixpath
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import paramiko


RETRYABLE_REMOTE_ERRORS = (EOFError, OSError, paramiko.SSHException)
RETRYABLE_TEXT_MARKERS = (
    "Error reading SSH protocol banner",
    "local tunnel port",
    "timed out",
    "Connection reset",
    "远程主机强迫关闭",
    "Connection refused",
    "Unable to connect to port",
    "Server connection dropped",
    "No existing session",
    "SSHException",
)


def is_retryable_text(text: str) -> bool:
    lower = text.lower()
    return any(marker.lower() in lower for marker in RETRYABLE_TEXT_MARKERS)


def sleep_backoff(attempt: int, sleep: Callable[[float], None] = time.sleep) -> None:
    sleep(min(2 * attempt, 8))


def run_subprocess_with_retry(
    args: list[str],
    *,
    timeout: int,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, attempts + 1):
        completed = runner(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        last = completed
        if completed.returncode == 0:
            return completed
        if attempt >= attempts or not is_retryable_text(completed.stdout or ""):
            return completed
        sleep_backoff(attempt, sleep)
    assert last is not None
    return last


def ensure_remote_under(remote_path: str, root: str, *, label: str = "remote_path") -> str:
    normalized_root = posixpath.normpath("/" + root.lstrip("/"))
    normalized_path = posixpath.normpath("/" + remote_path.lstrip("/"))
    if normalized_path != normalized_root and not normalized_path.startswith(normalized_root + "/"):
        raise ValueError(f"{label} escapes allowed remote root: {remote_path!r} not under {root!r}")
    return normalized_path


def mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = [p for p in remote_dir.split("/") if p]
    current = "/" if remote_dir.startswith("/") else "."
    for part in parts:
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def sftp_file_size(sftp: paramiko.SFTPClient, remote: str) -> int | None:
    try:
        return int(sftp.stat(remote).st_size)
    except FileNotFoundError:
        return None


def sftp_remove_if_exists(sftp: paramiko.SFTPClient, remote: str) -> None:
    try:
        sftp.remove(remote)
    except FileNotFoundError:
        pass


def finalize_uploaded_file(sftp: paramiko.SFTPClient, local: Path, remote: str) -> bool:
    expected = local.stat().st_size
    if sftp_file_size(sftp, remote) == expected:
        return True
    tmp = remote + ".uploading"
    if sftp_file_size(sftp, tmp) == expected:
        sftp_remove_if_exists(sftp, remote)
        sftp.rename(tmp, remote)
        return True
    return False


def upload_file_atomic(
    sftp: paramiko.SFTPClient,
    local: Path,
    remote: str,
    *,
    callback: Callable[[int, int], None] | None = None,
) -> bool:
    mkdir_p(sftp, posixpath.dirname(remote))
    if finalize_uploaded_file(sftp, local, remote):
        total = local.stat().st_size
        if callback is not None:
            callback(total, total)
        return False
    tmp = remote + ".uploading"
    sftp_remove_if_exists(sftp, tmp)
    if callback is not None:
        sftp.put(str(local), tmp, callback=callback)
    else:
        sftp.put(str(local), tmp)
    sftp_remove_if_exists(sftp, remote)
    sftp.rename(tmp, remote)
    return True


def upload_text_atomic(sftp: paramiko.SFTPClient, remote: str, text: str) -> None:
    mkdir_p(sftp, posixpath.dirname(remote))
    tmp = remote + ".uploading"
    with sftp.file(tmp, "w") as handle:
        handle.write(text)
    sftp_remove_if_exists(sftp, remote)
    sftp.rename(tmp, remote)


def download_file_atomic(
    sftp: paramiko.SFTPClient,
    remote: str,
    local: Path,
    *,
    callback: Callable[[int, int], None] | None = None,
) -> int:
    local.parent.mkdir(parents=True, exist_ok=True)
    tmp = local.with_name(local.name + ".downloading")
    if tmp.exists():
        tmp.unlink()
    if callback is not None:
        sftp.get(remote, str(tmp), callback=callback)
    else:
        sftp.get(remote, str(tmp))
    final_size = tmp.stat().st_size if tmp.exists() else 0
    local.unlink(missing_ok=True)
    tmp.replace(local)
    return final_size


class RemoteSession:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        attempts: int = 4,
        connect_timeout: int = 30,
        banner_timeout: int = 45,
        auth_timeout: int = 30,
        keepalive_sec: int = 15,
        sleep: Callable[[float], None] = time.sleep,
        on_retry: Callable[[str, int, int, BaseException], None] | None = None,
        ssh_client_factory: Callable[[], paramiko.SSHClient] = paramiko.SSHClient,
        sftp_from_transport: Callable[..., paramiko.SFTPClient] = paramiko.SFTPClient.from_transport,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.attempts = attempts
        self.connect_timeout = connect_timeout
        self.banner_timeout = banner_timeout
        self.auth_timeout = auth_timeout
        self.keepalive_sec = keepalive_sec
        self.sleep = sleep
        self.on_retry = on_retry
        self.ssh_client_factory = ssh_client_factory
        self.sftp_from_transport = sftp_from_transport
        self.client: paramiko.SSHClient | None = None
        self.sftp: paramiko.SFTPClient | None = None

    def close(self) -> None:
        if self.sftp is not None:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None

    def reconnect(self) -> None:
        self.close()
        last_error: BaseException | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                fresh = self.ssh_client_factory()
                fresh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                fresh.connect(
                    self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.connect_timeout,
                    banner_timeout=self.banner_timeout,
                    auth_timeout=self.auth_timeout,
                    look_for_keys=False,
                    allow_agent=False,
                )
                transport = fresh.get_transport()
                if transport is None:
                    raise RuntimeError("SSH transport was not established")
                transport.set_keepalive(self.keepalive_sec)
                self.client = fresh
                self.sftp = self.sftp_from_transport(
                    transport,
                    window_size=128 * 1024 * 1024,
                    max_packet_size=16 * 1024 * 1024,
                )
                return
            except RETRYABLE_REMOTE_ERRORS as exc:
                last_error = exc
                if self.on_retry is not None:
                    self.on_retry("connect", attempt, self.attempts, exc)
                if attempt < self.attempts:
                    sleep_backoff(attempt, self.sleep)
        raise RuntimeError(f"failed to establish SSH/SFTP session after retries: {last_error}") from last_error

    def require_client(self) -> paramiko.SSHClient:
        if self.client is None:
            self.reconnect()
        assert self.client is not None
        return self.client

    def require_sftp(self) -> paramiko.SFTPClient:
        if self.sftp is None:
            self.reconnect()
        assert self.sftp is not None
        return self.sftp

    def sftp_call(
        self,
        label: str,
        operation: Callable[[paramiko.SFTPClient], Any],
        *,
        attempts: int | None = None,
    ) -> Any:
        total_attempts = attempts or self.attempts
        last_error: BaseException | None = None
        for attempt in range(1, total_attempts + 1):
            try:
                return operation(self.require_sftp())
            except RETRYABLE_REMOTE_ERRORS as exc:
                last_error = exc
                if self.on_retry is not None:
                    self.on_retry(label, attempt, total_attempts, exc)
                self.reconnect()
                if attempt < total_attempts:
                    sleep_backoff(attempt, self.sleep)
        raise RuntimeError(f"SFTP {label} failed after {total_attempts} attempts: {last_error}") from last_error
