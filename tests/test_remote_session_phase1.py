from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeStat:
    def __init__(self, size: int):
        self.st_size = size


class FakeSFTP:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.renames: list[tuple[str, str]] = []
        self.removed: list[str] = []
        self.created_dirs: list[str] = []

    def stat(self, remote: str):
        if remote not in self.files:
            raise FileNotFoundError(remote)
        return FakeStat(len(self.files[remote]))

    def mkdir(self, remote: str) -> None:
        self.created_dirs.append(remote)

    def remove(self, remote: str) -> None:
        if remote not in self.files:
            raise FileNotFoundError(remote)
        self.removed.append(remote)
        del self.files[remote]

    def rename(self, src: str, dst: str) -> None:
        self.renames.append((src, dst))
        self.files[dst] = self.files.pop(src)

    def put(self, local: str, remote: str, callback=None) -> None:
        data = Path(local).read_bytes()
        self.files[remote] = data
        if callback is not None:
            callback(len(data), len(data))


class RemoteSessionPhase1Tests(unittest.TestCase):
    def test_remote_path_sandbox_rejects_prefix_escape(self):
        remote_session = load_module("remote_session_test_sandbox", "ComfyUI-Remote-Sampling/remote_session.py")
        root = "/home/user02/remote_ComfyUI"
        self.assertEqual(
            remote_session.ensure_remote_under("/home/user02/remote_ComfyUI/jobs/job1", root),
            "/home/user02/remote_ComfyUI/jobs/job1",
        )
        with self.assertRaises(ValueError):
            remote_session.ensure_remote_under("/home/user02/remote_ComfyUI_evil/jobs/job1", root)

    def test_run_subprocess_with_retry_retries_retryable_server_exec_failure(self):
        remote_session = load_module("remote_session_test_retry", "ComfyUI-Remote-Sampling/remote_session.py")
        calls: list[int] = []

        def runner(*_args, **_kwargs):
            calls.append(1)
            if len(calls) == 1:
                return subprocess.CompletedProcess(_args[0], 1, "TimeoutError: local tunnel port 123 not ready")
            return subprocess.CompletedProcess(_args[0], 0, "ok")

        completed = remote_session.run_subprocess_with_retry(
            ["python", "server_exec.py"],
            timeout=1,
            attempts=3,
            sleep=lambda _seconds: None,
            runner=runner,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(len(calls), 2)

    def test_unable_to_connect_port_is_retryable(self):
        remote_session = load_module("remote_session_test_retry_marker", "ComfyUI-Remote-Sampling/remote_session.py")
        self.assertTrue(
            remote_session.is_retryable_text("[Errno None] Unable to connect to port 13242 on 127.0.0.1")
        )

    def test_upload_file_atomic_finalizes_complete_uploading_file(self):
        remote_session = load_module("remote_session_test_upload", "ComfyUI-Remote-Sampling/remote_session.py")
        sftp = FakeSFTP()
        with tempfile.TemporaryDirectory(prefix="rwr-upload-") as temp_dir:
            local = Path(temp_dir) / "inputs.pt"
            local.write_bytes(b"latent-data")
            sftp.files["/remote/job/inputs.pt.uploading"] = b"latent-data"
            uploaded = remote_session.upload_file_atomic(sftp, local, "/remote/job/inputs.pt")

        self.assertFalse(uploaded)
        self.assertIn(("/remote/job/inputs.pt.uploading", "/remote/job/inputs.pt"), sftp.renames)
        self.assertEqual(sftp.files["/remote/job/inputs.pt"], b"latent-data")

    def test_remote_session_sftp_call_reconnects_after_operation_drop(self):
        remote_session = load_module("remote_session_test_sftp_call", "ComfyUI-Remote-Sampling/remote_session.py")
        session = remote_session.RemoteSession(
            host="127.0.0.1",
            port=22,
            username="user",
            password="pw",
            sleep=lambda _seconds: None,
        )
        first_sftp = object()
        second_sftp = object()
        session.sftp = first_sftp
        reconnects: list[str] = []

        def reconnect():
            reconnects.append("reconnect")
            session.sftp = second_sftp

        session.reconnect = reconnect  # type: ignore[method-assign]
        calls: list[object] = []

        def operation(active_sftp):
            calls.append(active_sftp)
            if len(calls) == 1:
                raise OSError("Server connection dropped")
            return "ok"

        self.assertEqual(session.sftp_call("read remote status", operation, attempts=2), "ok")
        self.assertEqual(calls, [first_sftp, second_sftp])
        self.assertEqual(reconnects, ["reconnect"])

    def test_submit_remote_prompt_polls_status_through_reconnectable_sftp_call(self):
        cli = load_module("remote_sampling_job_cli_phase1", "ComfyUI-Remote-Sampling/tools/remote_sampling_job_cli.py")

        class FakeStdin:
            def close(self):
                pass

        class FakeChannel:
            def __init__(self, *, ready_after_first_poll: bool):
                self.ready_after_first_poll = ready_after_first_poll
                self.polls = 0

            def exit_status_ready(self):
                if not self.ready_after_first_poll:
                    return True
                self.polls += 1
                return self.polls > 1

            def recv_ready(self):
                return False

            def recv_stderr_ready(self):
                return False

            def recv_exit_status(self):
                return 0

            def close(self):
                pass

        class FakeStream:
            def __init__(self, *, channel):
                self.channel = channel

            def read(self):
                return b""

        class FakeClient:
            def __init__(self):
                self.calls = 0

            def exec_command(self, *_args, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    channel = FakeChannel(ready_after_first_poll=False)
                else:
                    channel = FakeChannel(ready_after_first_poll=True)
                return FakeStdin(), FakeStream(channel=channel), FakeStream(channel=channel)

        labels: list[str] = []

        def sftp_call(label, operation):
            labels.append(label)
            if label.startswith("upload "):
                return None
            if label == "read remote sampling status":
                return {
                    "stage": "sampling",
                    "message": "Remote sampling 1/2",
                    "sampling": {"step": 1, "steps": 2, "percent": 50.0},
                }
            if label == "check remote completion":
                return True
            return operation(object())

        with tempfile.TemporaryDirectory(prefix="rwr-job-") as temp_dir:
            job_dir = Path(temp_dir)
            cli.protocol.init_status(job_dir, job_id="job_1")
            cli.submit_remote_prompt(
                FakeClient(),
                object(),
                {"900": {"class_type": "Remote_Sampling_remote", "inputs": {}}},
                "job_1",
                "/remote/jobs/job_1",
                job_dir,
                8197,
                30,
                sftp_call=sftp_call,
            )

        self.assertIn("read remote sampling status", labels)
        self.assertIn("check remote completion", labels)


if __name__ == "__main__":
    unittest.main()
