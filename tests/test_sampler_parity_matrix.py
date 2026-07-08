from __future__ import annotations

import importlib.util
import json
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


class SamplerParityMatrixTests(unittest.TestCase):
    def test_case_policy_marks_recommended_and_risk(self):
        matrix = load_module("sampler_parity_policy", "tools/run_sampler_parity_matrix.py")
        self.assertEqual(matrix.case_policy("euler", "normal")["classification"], "recommended")
        self.assertEqual(matrix.case_policy("seeds_2", "simple")["classification"], "risk_warning")
        self.assertEqual(matrix.case_policy("dpmpp_2m", "normal")["classification"], "unverified")

    def test_build_prompt_uses_requested_sampler(self):
        matrix = load_module("sampler_parity_prompt", "tools/run_sampler_parity_matrix.py")
        prompt = matrix.build_prompt(
            sampler_name="euler",
            scheduler="normal",
            seed=123,
            steps=4,
            cfg=5.2,
            prefix="parity/test",
        )
        sampler = prompt["500"]["inputs"]
        self.assertEqual(sampler["sampler_name"], "euler")
        self.assertEqual(sampler["scheduler"], "normal")
        self.assertEqual(sampler["seed"], 123)
        self.assertEqual(prompt["4"]["inputs"]["filename_prefix"], "parity/test")

    def test_dry_run_writes_json_and_markdown(self):
        matrix = load_module("sampler_parity_dry_run", "tools/run_sampler_parity_matrix.py")
        with tempfile.TemporaryDirectory(prefix="rwr-parity-") as temp_dir:
            output = Path(temp_dir) / "matrix.json"
            markdown = Path(temp_dir) / "matrix.md"
            old_parse_args = matrix.parse_args
            try:
                matrix.parse_args = lambda: type(
                    "Args",
                    (),
                    {
                        "project_root": Path(temp_dir),
                        "local_comfy_root": Path(temp_dir) / "ComfyUI",
                        "api": "http://127.0.0.1:8188",
                        "output": output,
                        "markdown_output": markdown,
                        "case": ["euler/normal", "seeds_2/simple"],
                        "seed": 1,
                        "steps": 1,
                        "cfg": 1.0,
                        "timeout_sec": 10,
                        "remote_only": False,
                        "local_only": False,
                        "dry_run": True,
                    },
                )()
                self.assertEqual(matrix.main(), 0)
            finally:
                matrix.parse_args = old_parse_args
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["dry_run"])
            self.assertEqual(len(report["cases"]), 2)
            self.assertIn("risk_warning", markdown.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
