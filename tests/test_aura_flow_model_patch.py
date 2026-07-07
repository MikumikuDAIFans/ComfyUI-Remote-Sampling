from __future__ import annotations

import importlib.util
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


def aura_prompt() -> dict:
    return {
        "62": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"},
        },
        "66": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"},
        },
        "67": {"class_type": "CLIPTextEncode", "inputs": {"text": "positive", "clip": ["62", 0]}},
        "68": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "69": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3, "model": ["66", 0]}},
        "70": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 8,
                "cfg": 1,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "denoise": 1,
                "model": ["69", 0],
                "positive": ["67", 0],
                "negative": ["71", 0],
                "latent_image": ["68", 0],
            },
        },
        "71": {"class_type": "CLIPTextEncode", "inputs": {"text": "negative", "clip": ["62", 0]}},
    }


class AuraFlowModelPatchTests(unittest.TestCase):
    def test_analyzer_treats_aura_flow_as_supported_model_patch(self):
        analyzer = load_module("workflow_analyzer_aura_test", "ComfyUI-Remote-Sampling/workflow_analyzer.py")
        temp = Path(tempfile.mkdtemp(prefix="rwr-aura-models-"))
        try:
            for subdir, filename in (
                ("unet", "z_image_turbo_bf16.safetensors"),
                ("clip", "qwen_3_4b.safetensors"),
            ):
                path = temp / subdir / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"test")
            analysis = analyzer.analyze_prompt(aura_prompt(), models_root=temp)
        finally:
            shutil.rmtree(temp, ignore_errors=True)

        self.assertFalse(analysis["fatal"])
        self.assertEqual(analysis["custom_node_classes"], [])
        model = analysis["samplers"][0]["model"]
        self.assertEqual(model["unet_name"], "z_image_turbo_bf16.safetensors")
        self.assertEqual(model["model_patches"][0]["class_type"], "ModelSamplingAuraFlow")
        self.assertEqual(model["model_patches"][0]["inputs"], {"shift": 3})

    def test_converter_profile_preserves_aura_flow_patch(self):
        converter = load_module("convert_ksampler_aura_test", "tools/convert_ksampler_to_remote_sampling.py")
        temp = Path(tempfile.mkdtemp(prefix="rwr-aura-convert-"))
        try:
            output = temp / "converted.json"
            converted, converted_ids, _removed, _rewired, profiles = converter.convert_prompt(
                prompt=aura_prompt(),
                remote_profile="auto",
                project_root=str(PROJECT_ROOT),
                python_executable="python",
                timeout_sec=2400,
                sampler_prefix="aura",
                prune_unreachable=False,
                bypass_local_lora_clip=False,
                allow_fixed_profile=False,
                output_path=output,
                lora_root=temp / "loras",
            )
        finally:
            shutil.rmtree(temp, ignore_errors=True)

        self.assertEqual(converted_ids, ["70"])
        self.assertEqual(converted["70"]["class_type"], "Remote_Sampling_local")
        patch = profiles[0]["unet"]["model_patches"][0]
        self.assertEqual(patch["class_type"], "ModelSamplingAuraFlow")
        self.assertEqual(patch["inputs"], {"shift": 3})

    def test_remote_prompt_applies_model_patch_before_remote_sampler(self):
        cli = load_module("remote_sampling_job_cli_aura_test", "ComfyUI-Remote-Sampling/tools/remote_sampling_job_cli.py")
        profile = {
            "unet": {
                "class_type": "UNETLoader",
                "unet_name": "z_image_turbo_bf16.safetensors",
                "weight_dtype": "default",
                "model_patches": [{"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3}}],
            },
            "clip": {"class_type": "CLIPLoader", "clip_name": "qwen_3_4b.safetensors", "type": "lumina2"},
            "loras": [],
        }
        prompt = cli.build_profile_prompt("inline_aura_profile", "aura_job", profile)

        self.assertEqual(prompt["120"]["class_type"], "ModelSamplingAuraFlow")
        self.assertEqual(prompt["120"]["inputs"]["model"], ["44", 0])
        self.assertEqual(prompt["900"]["inputs"]["model"], ["120", 0])


if __name__ == "__main__":
    unittest.main()
