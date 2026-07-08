from __future__ import annotations

import importlib.util
import json
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

    def test_recent_workflow_runtime_runs_are_sorted_and_summarized(self):
        runtime = load_module("workflow_runtime_recent_test", "ComfyUI-Remote-Sampling/workflow_runtime.py")
        temp = Path(tempfile.mkdtemp(prefix="rwr-recent-"))
        try:
            runs_dir = temp / "runs"
            first = runs_dir / "workflow_runtime_20260708_010000_aaaa1111"
            second = runs_dir / "workflow_runtime_20260708_020000_bbbb2222"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            (first / "workflow_status.json").write_text(
                json.dumps(
                    {
                        "run_id": first.name,
                        "stage": "complete",
                        "message": "First complete.",
                        "updated_at": "2026-07-08 01:00:00",
                    }
                ),
                encoding="utf-8",
            )
            (first / "manifest.json").write_text(json.dumps({"ok": True, "run_id": first.name}), encoding="utf-8")
            (first / "workflow_runtime_report.txt").write_text("report\n", encoding="utf-8")
            (second / "workflow_status.json").write_text(
                json.dumps(
                    {
                        "run_id": second.name,
                        "stage": "failed",
                        "message": "Second failed.",
                        "fatal": True,
                        "details": {"job_id": "job_2"},
                    }
                ),
                encoding="utf-8",
            )
            (second / "manifest.json").write_text(
                json.dumps({"ok": False, "run_id": second.name, "error": {"type": "ProbeError", "message": "boom"}}),
                encoding="utf-8",
            )
            os.utime(first, (1, 1))
            os.utime(second, (2, 2))

            result = runtime.list_workflow_runtime_runs(temp, limit=2)
            self.assertTrue(result["ok"])
            self.assertEqual([item["run_id"] for item in result["runs"]], [second.name, first.name])
            self.assertEqual(result["runs"][0]["stage"], "failed")
            self.assertEqual(result["runs"][0]["job_id"], "job_2")
            self.assertEqual(result["runs"][0]["error"]["type"], "ProbeError")
            self.assertTrue(result["runs"][1]["workflow_report"].endswith("workflow_runtime_report.txt"))
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    def test_custom_node_remote_env_short_circuits_empty_plan(self):
        runtime = load_module("workflow_runtime_custom_env_skip", "ComfyUI-Remote-Sampling/workflow_runtime.py")
        temp = Path(tempfile.mkdtemp(prefix="rwr-custom-skip-"))
        try:
            run_dir = temp / "runs" / "workflow_runtime_skip"
            run_dir.mkdir(parents=True)
            custom_plan = {
                "schema_version": "custom-nodes-plan-v1",
                "remote_base": "/home/user02/remote_ComfyUI",
                "remote_custom_nodes_root": "/home/user02/remote_ComfyUI/ComfyUI/custom_nodes",
                "classes": [],
                "packages": [],
                "summary": {
                    "custom_class_count": 0,
                    "package_count": 0,
                    "local_package_missing": 0,
                    "needs_remote_check": 0,
                },
                "fatal": False,
            }
            (run_dir / "custom_nodes_plan.json").write_text(json.dumps(custom_plan), encoding="utf-8")
            (run_dir / "manifest.json").write_text(
                json.dumps({"ok": True, "run_id": "workflow_runtime_skip", "run_dir": str(run_dir)}),
                encoding="utf-8",
            )

            def fail_remote_call(*_args, **_kwargs):
                raise AssertionError("empty custom node plan should not call remote tools")

            old_run_project_tool = runtime._run_project_tool
            try:
                runtime._run_project_tool = fail_remote_call
                result = runtime._check_and_sync_custom_nodes(
                    {"ok": True, "run_id": "workflow_runtime_skip", "run_dir": str(run_dir)},
                    {"project_root": str(temp), "options": {}},
                )
            finally:
                runtime._run_project_tool = old_run_project_tool

            self.assertTrue(result["remote_environment_ready"])
            self.assertTrue(result["remote_environment_short_circuit"])
            env_report = json.loads((run_dir / "remote_environment_report.json").read_text(encoding="utf-8"))
            smoke = json.loads((run_dir / "remote_custom_node_import_smoke.json").read_text(encoding="utf-8"))
            self.assertTrue(env_report["skipped"])
            self.assertTrue(smoke["skipped"])
            self.assertFalse((run_dir / "custom_nodes_sync_report.json").exists())
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    def test_remote_custom_node_checker_skips_empty_package_plan(self):
        checker = load_module("remote_custom_node_checker_skip", "tools/check_remote_custom_nodes_plan.py")
        remote = checker.remote_check({"packages": []}, Path("unused_server_exec.py"))
        self.assertTrue(remote["skipped"])
        report = checker.build_report(
            {"remote_base": "/home/user02/remote_ComfyUI", "remote_custom_nodes_root": "/home/user02/remote_ComfyUI/ComfyUI/custom_nodes", "packages": []},
            remote,
        )
        self.assertTrue(report["skipped"])
        self.assertEqual(report["summary"]["package_count"], 0)

    def test_custom_node_sync_writes_failure_report_for_missing_local_package(self):
        sync = load_module("sync_remote_custom_nodes_failure", "tools/sync_remote_custom_nodes.py")
        temp = Path(tempfile.mkdtemp(prefix="rwr-custom-sync-fail-"))
        try:
            plan_path = temp / "custom_nodes_plan.json"
            output_path = temp / "custom_nodes_sync_report.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "package_name": "MissingPkg",
                                "local_path": str(temp / "does_not_exist"),
                                "remote_path": "/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/MissingPkg",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            old_parse_args = sync.parse_args
            try:
                sync.parse_args = lambda: type(
                    "Args",
                    (),
                    {
                        "custom_nodes_plan": plan_path,
                        "packages": None,
                        "project_root": temp,
                        "server_exec": Path("unused.py"),
                        "archive_dir": temp / "archives",
                        "output": output_path,
                        "dry_run": False,
                    },
                )()
                self.assertEqual(sync.main(), 1)
            finally:
                sync.parse_args = old_parse_args
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(report["fatal"])
            self.assertEqual(report["summary"]["failed"], 1)
            self.assertEqual(report["packages"][0]["action"], "failed")
            self.assertIn("fallback_hint", report["packages"][0])
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    def test_import_smoke_skips_empty_custom_class_plan_without_remote_service(self):
        smoke = load_module("remote_custom_node_import_smoke_skip", "tools/remote_custom_node_import_smoke.py")
        temp = Path(tempfile.mkdtemp(prefix="rwr-import-smoke-skip-"))
        try:
            plan_path = temp / "custom_nodes_plan.json"
            output_path = temp / "remote_custom_node_import_smoke.json"
            plan_path.write_text(json.dumps({"classes": [], "packages": []}), encoding="utf-8")
            old_parse_args = smoke.parse_args
            old_load_remote_service = smoke.load_remote_service
            try:
                smoke.parse_args = lambda: type(
                    "Args",
                    (),
                    {
                        "custom_nodes_plan": plan_path,
                        "output": output_path,
                        "server_exec": Path("unused.py"),
                        "timeout": 1,
                    },
                )()
                smoke.load_remote_service = lambda: (_ for _ in ()).throw(AssertionError("remote service should not load"))
                self.assertEqual(smoke.main(), 0)
            finally:
                smoke.parse_args = old_parse_args
                smoke.load_remote_service = old_load_remote_service
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(report["skipped"])
            self.assertFalse(report["fatal"])
            self.assertEqual(report["summary"]["class_count"], 0)
        finally:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
