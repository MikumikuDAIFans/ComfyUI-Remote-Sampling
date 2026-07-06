from __future__ import annotations

import importlib.util
import os
import shutil
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


class PostReviewHardeningTests(unittest.TestCase):
    def test_remote_sampling_report_parser_extracts_metrics(self):
        runtime = load_module("workflow_runtime_test", "ComfyUI-Remote-Sampling/workflow_runtime.py")
        report = "\n".join(
            [
                "# Remote Sampling Report",
                "job_id: job_123",
                "total_elapsed_sec: 12.5",
                'upload: {"bytes": 10, "percent": 100.0}',
                'sampling: {"step": 4, "steps": 4, "percent": 100.0}',
                'download: {"bytes": 20, "percent": 100.0}',
            ]
        )
        details = runtime._remote_sampling_report_details(report)
        self.assertEqual(details["job_id"], "job_123")
        self.assertEqual(details["sampling"]["step"], 4)
        self.assertTrue(details["raw_report_present"])

    def test_remote_path_sandbox_rejects_escape(self):
        sync = load_module("sync_remote_custom_nodes_test", "tools/sync_remote_custom_nodes.py")
        with self.assertRaises(ValueError):
            sync.ensure_remote_under("/tmp/evil", "/home/user02/remote_ComfyUI/ComfyUI/custom_nodes", label="remote_path")
        clean = sync.ensure_remote_under(
            "/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/pkg",
            "/home/user02/remote_ComfyUI/ComfyUI/custom_nodes",
            label="remote_path",
        )
        self.assertEqual(clean, "/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/pkg")

    def test_custom_node_ambiguous_match_fails_closed(self):
        planner = load_module("custom_node_planner_test", "ComfyUI-Remote-Sampling/custom_node_planner.py")
        temp = Path(tempfile.mkdtemp(prefix="rwr-planner-"))
        try:
            for package in ("PkgA", "PkgB"):
                package_dir = temp / "custom_nodes" / package
                package_dir.mkdir(parents=True)
                (package_dir / "__init__.py").write_text('NODE_CLASS_MAPPINGS={"AmbiguousNode": object}\n', encoding="utf-8")
            plan = planner.build_custom_nodes_plan({"custom_node_classes": ["AmbiguousNode"]}, local_comfy_root=temp)
            self.assertTrue(plan["fatal"])
            self.assertEqual(plan["errors"][0]["type"], "CustomNodePackageAmbiguous")
            self.assertEqual(len(plan["errors"][0]["candidates"]), 2)
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    def test_generic_ssh_args_use_target_and_port(self):
        ssh_exec = load_module("generic_ssh_exec_test", "tools/generic_ssh_exec.py")
        old_env = dict(os.environ)
        try:
            os.environ["REMOTE_SAMPLING_SSH_TARGET"] = "user@example.com"
            os.environ["REMOTE_SAMPLING_SSH_PORT"] = "2222"
            os.environ.pop("REMOTE_SAMPLING_SSH_HOST", None)
            args = ssh_exec.build_ssh_args("echo ok", 120)
            self.assertIn("user@example.com", args)
            self.assertIn("2222", args)
            self.assertEqual(args[-1], "echo ok")
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def test_sync_required_custom_node_packages_filters_ready_packages(self):
        runtime = load_module("workflow_runtime_test_filter", "ComfyUI-Remote-Sampling/workflow_runtime.py")
        report = {
            "packages": [
                {"package_name": "ready_pkg", "action": "ready_for_import_smoke"},
                {"package_name": "missing_pkg", "action": "sync_required"},
                {"package_name": "another_missing", "action": "sync_required"},
            ]
        }
        self.assertEqual(
            runtime._sync_required_custom_node_packages(report),
            ["another_missing", "missing_pkg"],
        )


if __name__ == "__main__":
    unittest.main()
