from __future__ import annotations

import importlib.util
import json
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


class SyncRemoteResourcesPhase1Tests(unittest.TestCase):
    def test_target_remote_path_rejects_escape(self):
        sync = load_module("sync_remote_resources_escape", "tools/sync_remote_resources.py")
        item = {"remote_path": "/home/user02/remote_ComfyUI_evil/models/x.safetensors"}
        with self.assertRaises(ValueError):
            sync.target_remote_path(item, {"resources": []}, remote_base="/home/user02/remote_ComfyUI")

    def test_run_command_retries_retryable_uploader_failure(self):
        sync = load_module("sync_remote_resources_retry", "tools/sync_remote_resources.py")
        calls: list[int] = []

        def runner(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                return subprocess.CompletedProcess(args[0], 1, "TimeoutError: local tunnel port 123 not ready")
            return subprocess.CompletedProcess(args[0], 0, "uploaded")

        output = sync.run_command(["python", "uploader.py"], timeout=1, attempts=2, runner=runner)
        self.assertEqual(output, "uploaded")
        self.assertEqual(len(calls), 2)

    def test_main_writes_failed_resource_report(self):
        sync = load_module("sync_remote_resources_failed_report", "tools/sync_remote_resources.py")
        with tempfile.TemporaryDirectory(prefix="rwr-sync-") as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            tools_dir = project_root / "tools"
            tools_dir.mkdir(parents=True)
            uploader = tools_dir / "upload_to_company_server_stream.py"
            uploader.write_text("raise SystemExit(2)\n", encoding="utf-8")
            local_file = root / "model.safetensors"
            local_file.write_bytes(b"model")
            plan = {
                "resources": [
                    {
                        "kind": "lora",
                        "relative_path": "loras/model.safetensors",
                        "remote": {"primary_path": "/home/user02/remote_ComfyUI/ComfyUI/models/loras/model.safetensors"},
                    }
                ]
            }
            diff = {
                "resources": [
                    {
                        "index": 0,
                        "kind": "lora",
                        "relative_path": "loras/model.safetensors",
                        "local_path": str(local_file),
                        "remote_path": None,
                        "action": "upload_required",
                    }
                ]
            }
            plan_path = root / "resources_plan.json"
            diff_path = root / "resources_diff.json"
            output_path = root / "resources_sync_report.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            diff_path.write_text(json.dumps(diff), encoding="utf-8")

            old_parse_args = sync.parse_args
            try:
                sync.parse_args = lambda: type(
                    "Args",
                    (),
                    {
                        "resources_plan": plan_path,
                        "resources_diff": diff_path,
                        "project_root": project_root,
                        "output": output_path,
                        "include_size_mismatch": False,
                        "remote_base": "/home/user02/remote_ComfyUI",
                        "server_exec": Path("server_exec.py"),
                        "hash_strategy": "size_only",
                    },
                )()
                self.assertEqual(sync.main(), 1)
            finally:
                sync.parse_args = old_parse_args

            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(report["fatal"])
            self.assertEqual(report["summary"]["failed"], 1)
            self.assertEqual(report["resources"][0]["status"], "failed")
            self.assertIn("resume_hint", report["resources"][0])

    def test_stream_uploader_removes_mismatched_final_file_instead_of_appending(self):
        uploader = load_module("upload_to_company_server_stream_test", "tools/upload_to_company_server_stream.py")
        with tempfile.TemporaryDirectory(prefix="rwr-stream-") as temp_dir:
            local = Path(temp_dir) / "archive.zip"
            local.write_bytes(b"new-archive")
            commands: list[str] = []
            sizes = {"/remote/archive.zip": 3}

            def fake_remote_size(_client, remote):
                return sizes.get(remote)

            def fake_run_text(_client, command):
                commands.append(command)
                if command.startswith("rm -f -- "):
                    sizes.pop("/remote/archive.zip", None)
                if command.startswith("mv -f -- "):
                    sizes["/remote/archive.zip"] = len(local.read_bytes())
                return ""

            def fake_stream_append(_client, _local, remote, offset, size):
                self.assertEqual(offset, 0)
                sizes[remote + ".uploading"] = size

            old_remote_size = uploader.remote_size
            old_run_text = uploader.run_text
            old_stream_append = uploader.stream_append
            try:
                uploader.remote_size = fake_remote_size
                uploader.run_text = fake_run_text
                uploader.stream_append = fake_stream_append
                uploader.upload_file(object(), local, "/remote/archive.zip")
            finally:
                uploader.remote_size = old_remote_size
                uploader.run_text = old_run_text
                uploader.stream_append = old_stream_append

            joined = "\n".join(commands)
            self.assertIn("rm -f --", joined)
            self.assertNotIn("mv -f -- /remote/archive.zip /remote/archive.zip.uploading", joined)

    def test_extract_sha256sum_from_server_exec_output(self):
        sync = load_module("sync_remote_resources_sha_extract", "tools/sync_remote_resources.py")
        digest = "a" * 64
        text = f"TUNNEL local=1\n===== cmd-1 =====\n{digest}  /remote/file\n__exit_status=0\n"
        self.assertEqual(sync.extract_sha256sum(text), digest)

    def test_main_verifies_sha256_when_required(self):
        sync = load_module("sync_remote_resources_sha_required", "tools/sync_remote_resources.py")
        with tempfile.TemporaryDirectory(prefix="rwr-sync-sha-") as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            tools_dir = project_root / "tools"
            tools_dir.mkdir(parents=True)
            uploader = tools_dir / "upload_to_company_server_stream.py"
            uploader.write_text("print('uploaded')\n", encoding="utf-8")
            local_file = root / "model.safetensors"
            local_file.write_bytes(b"model")
            local_digest = sync.sha256_file(local_file)
            plan = {
                "resources": [
                    {
                        "kind": "lora",
                        "relative_path": "loras/model.safetensors",
                        "local": {"file": {"sha256": local_digest, "sha256_policy": "inline_sha256"}},
                        "remote": {"primary_path": "/home/user02/remote_ComfyUI/ComfyUI/models/loras/model.safetensors"},
                    }
                ]
            }
            diff = {
                "resources": [
                    {
                        "index": 0,
                        "kind": "lora",
                        "relative_path": "loras/model.safetensors",
                        "local_path": str(local_file),
                        "remote_path": None,
                        "action": "upload_required",
                    }
                ]
            }
            plan_path = root / "resources_plan.json"
            diff_path = root / "resources_diff.json"
            output_path = root / "resources_sync_report.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            diff_path.write_text(json.dumps(diff), encoding="utf-8")

            old_parse_args = sync.parse_args
            old_remote_sha256sum = sync.remote_sha256sum
            try:
                sync.parse_args = lambda: type(
                    "Args",
                    (),
                    {
                        "resources_plan": plan_path,
                        "resources_diff": diff_path,
                        "project_root": project_root,
                        "output": output_path,
                        "include_size_mismatch": False,
                        "remote_base": "/home/user02/remote_ComfyUI",
                        "server_exec": Path("server_exec.py"),
                        "hash_strategy": "sha256_required",
                    },
                )()
                sync.remote_sha256sum = lambda _server_exec, _remote_path: local_digest
                self.assertEqual(sync.main(), 0)
            finally:
                sync.parse_args = old_parse_args
                sync.remote_sha256sum = old_remote_sha256sum

            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(report["fatal"])
            self.assertEqual(report["summary"]["sha256_verified"], 1)
            self.assertTrue(report["resources"][0]["sha256_verified"])

    def test_workflow_runtime_passes_resource_hash_strategy_to_sync_tool(self):
        runtime = load_module("workflow_runtime_hash_strategy", "ComfyUI-Remote-Sampling/workflow_runtime.py")
        with tempfile.TemporaryDirectory(prefix="rwr-runtime-sync-") as temp_dir:
            project_root = Path(temp_dir)
            run_dir = project_root / "runs" / "workflow_runtime_test"
            run_dir.mkdir(parents=True)
            (run_dir / "resources_plan.json").write_text(json.dumps({"resources": []}), encoding="utf-8")
            captured: list[list[str]] = []
            check_count = {"value": 0}

            def fake_run_project_tool(_project_root, args, **_kwargs):
                captured.append([str(item) for item in args])
                if "check_remote_resource_plan.py" in str(args[0]):
                    check_count["value"] += 1
                    if check_count["value"] == 1:
                        (run_dir / "resources_diff.json").write_text(
                            json.dumps({"summary": {"upload_required": 1}, "resources": [], "fatal": False}),
                            encoding="utf-8",
                        )
                    else:
                        (run_dir / "resources_diff.json").write_text(
                            json.dumps({"summary": {"upload_required": 0}, "resources": [], "fatal": False}),
                            encoding="utf-8",
                        )
                if "sync_remote_resources.py" in str(args[0]):
                    (run_dir / "resources_sync_report.json").write_text(
                        json.dumps({"summary": {"uploaded": 1}, "resources": [], "fatal": False}),
                        encoding="utf-8",
                    )
                return "ok"

            old_run_project_tool = runtime._run_project_tool
            try:
                runtime._run_project_tool = fake_run_project_tool
                result = runtime._check_and_sync_resources(
                    {"ok": True, "run_id": "workflow_runtime_test", "run_dir": str(run_dir)},
                    {
                        "project_root": str(project_root),
                        "options": {
                            "auto_sync_resources": True,
                            "resource_hash_strategy": "sha256_required",
                        },
                    },
                )
            finally:
                runtime._run_project_tool = old_run_project_tool

            self.assertTrue(result["resources_ready"])
            sync_calls = [args for args in captured if "sync_remote_resources.py" in args[0]]
            self.assertEqual(len(sync_calls), 1)
            self.assertIn("--hash-strategy", sync_calls[0])
            self.assertIn("sha256_required", sync_calls[0])


if __name__ == "__main__":
    unittest.main()
