from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_LOCAL_COMFY_MODELS = Path(
    os.environ.get(
        "REMOTE_SAMPLING_LOCAL_COMFY_MODELS",
        r"F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\models",
    )
)

SAMPLER_CLASSES = {"KSampler"}
REMOTE_SAMPLER_CLASSES = {"Remote_Sampling_local"}
CLIP_TEXT_CLASSES = {"CLIPTextEncode"}
UNET_LOADER_CLASSES = {"UNETLoader"}
CLIP_LOADER_CLASSES = {"CLIPLoader"}
VAE_LOADER_CLASSES = {"VAELoader"}
LORA_LOADER_CLASSES = {"LoraLoader", "Lora Loader (LoraManager)"}
MODEL_PATCH_CLASSES = {"ModelSamplingAuraFlow"}
IMAGE_IO_CLASSES = {"LoadImage", "PreviewImage", "SaveImage"}
REMOTE_FORBIDDEN_CLASSES = {"LoadImage", "VAEEncode", "VAELoader", "VAEDecode", "PreviewImage", "SaveImage"}

COMMON_COMFY_CLASSES = {
    "CheckpointLoaderSimple",
    "CLIPLoader",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "EmptySD3LatentImage",
    "KSampler",
    "LoadImage",
    "LoraLoader",
    "ModelSamplingAuraFlow",
    "PreviewImage",
    "Remote_Sampling_local",
    "Remote_Sampling_remote",
    "SaveImage",
    "UNETLoader",
    "VAEDecode",
    "VAEEncode",
    "VAELoader",
}


def is_ref(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


def node_ref(prompt: dict[str, Any], value: Any) -> tuple[str, dict[str, Any]] | None:
    if not is_ref(value):
        return None
    node = prompt.get(value[0])
    if isinstance(node, dict):
        return value[0], node
    return None


def iter_refs(value: Any):
    if is_ref(value):
        yield value[0]
    elif isinstance(value, list):
        for item in value:
            yield from iter_refs(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_refs(item)


def as_float(value: Any, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resource_candidates(kind: str, name: str, models_root: Path) -> list[Path]:
    normalized = name.replace("\\", os.sep).replace("/", os.sep)
    subdirs = {
        "unet": ["diffusion_models", "unet"],
        "clip": ["clip"],
        "vae": ["vae"],
        "lora": ["loras"],
    }.get(kind, [])
    return [models_root / subdir / normalized for subdir in subdirs]


def resource_record(kind: str, name: str, models_root: Path, *, source_node: str | None = None) -> dict[str, Any]:
    candidates = resource_candidates(kind, name, models_root)
    found = next((path for path in candidates if path.exists()), None)
    return {
        "kind": kind,
        "name": name,
        "source_node": source_node,
        "exists": found is not None,
        "local_path": str(found) if found else None,
        "local_candidates": [str(path) for path in candidates],
        "relative_path": name.replace("\\", "/"),
    }


def resolve_lora_name(name: str, models_root: Path) -> str:
    cleaned = name.strip()
    if cleaned.endswith(".safetensors") and ("/" in cleaned or "\\" in cleaned):
        return cleaned.replace("\\", "/")
    stem = Path(cleaned).stem
    lora_root = models_root / "loras"
    if lora_root.is_dir():
        candidates = list(lora_root.rglob(f"{stem}.safetensors"))
        if not candidates and cleaned.endswith(".safetensors"):
            candidates = list(lora_root.rglob(cleaned))
        if candidates:
            candidates.sort(key=lambda path: (len(str(path)), str(path).casefold()))
            try:
                return candidates[0].relative_to(lora_root).as_posix()
            except ValueError:
                return candidates[0].name
    return cleaned if cleaned.endswith(".safetensors") else f"{cleaned}.safetensors"


def loras_from_lora_manager(node: dict[str, Any], models_root: Path) -> list[dict[str, Any]]:
    raw_loras = node.get("inputs", {}).get("loras", {}).get("__value__", [])
    if not isinstance(raw_loras, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in raw_loras:
        if not isinstance(raw, dict) or raw.get("active") is False:
            continue
        name = raw.get("name")
        if not name:
            continue
        strength_model = as_float(raw.get("strength"), 1.0)
        strength_clip = as_float(raw.get("clipStrength"), strength_model)
        result.append(
            {
                "lora_name": resolve_lora_name(str(name), models_root),
                "strength_model": strength_model,
                "strength_clip": strength_clip,
                "loader_class": "Lora Loader (LoraManager)",
            }
        )
    return result


def trace_model_chain(
    prompt: dict[str, Any],
    model_ref: Any,
    models_root: Path,
    *,
    seen: set[str] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    target = node_ref(prompt, model_ref)
    if target is None:
        return None, [], [{"type": "UnresolvedModelRef", "message": f"Cannot resolve model reference {model_ref!r}", "fatal": True}]
    node_id, node = target
    if seen is None:
        seen = set()
    if node_id in seen:
        return None, [], [{"type": "ModelChainCycle", "message": f"Cycle in model chain at node {node_id}", "fatal": True}]
    seen.add(node_id)
    cls = node.get("class_type")
    inputs = node.get("inputs", {}) if isinstance(node.get("inputs"), dict) else {}
    if cls in UNET_LOADER_CLASSES and inputs.get("unet_name"):
        return (
            {
                "node_id": node_id,
                "class_type": cls,
                "unet_name": inputs.get("unet_name"),
                "weight_dtype": inputs.get("weight_dtype", "default"),
            },
            [],
            [],
        )
    if cls == "LoraLoader":
        unet, loras, issues = trace_model_chain(prompt, inputs.get("model"), models_root, seen=seen)
        if inputs.get("lora_name"):
            loras.append(
                {
                    "lora_name": resolve_lora_name(str(inputs["lora_name"]), models_root),
                    "strength_model": as_float(inputs.get("strength_model"), 1.0),
                    "strength_clip": as_float(inputs.get("strength_clip"), 1.0),
                    "loader_class": cls,
                    "node_id": node_id,
                }
            )
        return unet, loras, issues
    if cls == "Lora Loader (LoraManager)":
        unet, loras, issues = trace_model_chain(prompt, inputs.get("model"), models_root, seen=seen)
        for item in loras_from_lora_manager(node, models_root):
            item["node_id"] = node_id
            loras.append(item)
        return unet, loras, issues
    if cls in MODEL_PATCH_CLASSES:
        unet, loras, issues = trace_model_chain(prompt, inputs.get("model"), models_root, seen=seen)
        if unet is not None:
            patches = unet.setdefault("model_patches", [])
            patch_inputs = {key: value for key, value in inputs.items() if key != "model"}
            patches.append(
                {
                    "node_id": node_id,
                    "class_type": cls,
                    "inputs": patch_inputs,
                }
            )
        return unet, loras, issues
    return None, [], [{"type": "UnsupportedModelChainNode", "message": f"Unsupported model chain node {node_id}: {cls}", "fatal": True, "node_id": node_id, "class_type": cls}]


def trace_clip_chain(
    prompt: dict[str, Any],
    clip_ref: Any,
    *,
    seen: set[str] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    target = node_ref(prompt, clip_ref)
    if target is None:
        return None, [{"type": "UnresolvedClipRef", "message": f"Cannot resolve CLIP reference {clip_ref!r}", "fatal": True}]
    node_id, node = target
    if seen is None:
        seen = set()
    if node_id in seen:
        return None, [{"type": "ClipChainCycle", "message": f"Cycle in CLIP chain at node {node_id}", "fatal": True}]
    seen.add(node_id)
    cls = node.get("class_type")
    inputs = node.get("inputs", {}) if isinstance(node.get("inputs"), dict) else {}
    if cls in CLIP_LOADER_CLASSES and inputs.get("clip_name"):
        return (
            {
                "node_id": node_id,
                "class_type": cls,
                "clip_name": inputs.get("clip_name"),
                "type": inputs.get("type", "stable_diffusion"),
                "device": inputs.get("device", "default"),
            },
            [],
        )
    if cls in LORA_LOADER_CLASSES:
        return trace_clip_chain(prompt, inputs.get("clip"), seen=seen)
    return None, [{"type": "UnsupportedClipChainNode", "message": f"Unsupported CLIP chain node {node_id}: {cls}", "fatal": True, "node_id": node_id, "class_type": cls}]


def first_conditioning_clip_ref(prompt: dict[str, Any], sampler_inputs: dict[str, Any]) -> Any | None:
    for key in ("positive", "negative"):
        target = node_ref(prompt, sampler_inputs.get(key))
        if target is None:
            continue
        _node_id, node = target
        inputs = node.get("inputs", {}) if isinstance(node.get("inputs"), dict) else {}
        if node.get("class_type") in CLIP_TEXT_CLASSES and "clip" in inputs:
            return inputs["clip"]
    return None


def vae_resources(prompt: dict[str, Any], models_root: Path) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for node_id, node in prompt.items():
        if not isinstance(node, dict) or node.get("class_type") not in VAE_LOADER_CLASSES:
            continue
        inputs = node.get("inputs", {}) if isinstance(node.get("inputs"), dict) else {}
        if inputs.get("vae_name"):
            resources.append(resource_record("vae", str(inputs["vae_name"]), models_root, source_node=str(node_id)))
    return resources


def analyze_prompt(prompt: dict[str, Any], *, models_root: Path | None = None) -> dict[str, Any]:
    models_root = models_root or DEFAULT_LOCAL_COMFY_MODELS
    class_counts = Counter()
    issues: list[dict[str, Any]] = []
    samplers: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    remote_forbidden_classes: set[str] = set()
    custom_classes: set[str] = set()

    for node_id, node in prompt.items():
        if not isinstance(node, dict):
            issues.append({"type": "InvalidNode", "message": f"Node {node_id} is not an object", "fatal": True, "node_id": str(node_id)})
            continue
        cls = node.get("class_type")
        if not isinstance(cls, str):
            issues.append({"type": "MissingClassType", "message": f"Node {node_id} has no class_type", "fatal": True, "node_id": str(node_id)})
            continue
        class_counts[cls] += 1
        if cls in REMOTE_FORBIDDEN_CLASSES:
            remote_forbidden_classes.add(cls)
        if cls not in COMMON_COMFY_CLASSES:
            custom_classes.add(cls)

    for node_id, node in prompt.items():
        if not isinstance(node, dict) or node.get("class_type") not in SAMPLER_CLASSES | REMOTE_SAMPLER_CLASSES:
            continue
        inputs = node.get("inputs", {}) if isinstance(node.get("inputs"), dict) else {}
        sampler = {
            "node_id": str(node_id),
            "class_type": node.get("class_type"),
            "sampler_id": inputs.get("sampler_id"),
            "steps": inputs.get("steps"),
            "cfg": inputs.get("cfg"),
            "sampler_name": inputs.get("sampler_name"),
            "scheduler": inputs.get("scheduler"),
            "denoise": inputs.get("denoise"),
            "remote_profile": inputs.get("remote_profile"),
            "model": None,
            "clip": None,
            "loras": [],
            "issues": [],
        }
        if node.get("class_type") == "KSampler":
            required = ["model", "positive", "negative", "latent_image", "seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"]
            missing = [name for name in required if name not in inputs]
            if missing:
                sampler["issues"].append({"type": "MissingSamplerInput", "message": f"KSampler {node_id} is missing {', '.join(missing)}", "fatal": True})
            unet, loras, model_issues = trace_model_chain(prompt, inputs.get("model"), models_root)
            sampler["model"] = unet
            sampler["loras"] = loras
            sampler["issues"].extend(model_issues)
            if unet and unet.get("unet_name"):
                resources.append(resource_record("unet", str(unet["unet_name"]), models_root, source_node=unet.get("node_id")))
            for lora in loras:
                resources.append(resource_record("lora", str(lora["lora_name"]), models_root, source_node=lora.get("node_id")))
            clip_ref = first_conditioning_clip_ref(prompt, inputs)
            if clip_ref is None:
                sampler["issues"].append({"type": "MissingClipReference", "message": f"KSampler {node_id} has no CLIPTextEncode clip reference", "fatal": True})
            else:
                clip, clip_issues = trace_clip_chain(prompt, clip_ref)
                sampler["clip"] = clip
                sampler["issues"].extend(clip_issues)
                if clip and clip.get("clip_name"):
                    resources.append(resource_record("clip", str(clip["clip_name"]), models_root, source_node=clip.get("node_id")))
        samplers.append(sampler)
        issues.extend(sampler["issues"])

    resources.extend(vae_resources(prompt, models_root))
    if not samplers:
        issues.append({"type": "NoSampler", "message": "No supported sampler node found.", "fatal": True})

    missing_resources = [item for item in resources if not item.get("exists")]
    for item in missing_resources:
        issues.append(
            {
                "type": "LocalResourceMissing",
                "message": f"Missing local {item['kind']}: {item['name']}",
                "fatal": True,
                "resource": item,
            }
        )

    return {
        "schema_version": "workflow-analysis-v1",
        "models_root": str(models_root),
        "node_count": len(prompt),
        "class_counts": dict(sorted(class_counts.items())),
        "samplers": samplers,
        "resources": resources,
        "missing_resources": missing_resources,
        "custom_node_classes": sorted(custom_classes),
        "remote_forbidden_classes": sorted(remote_forbidden_classes),
        "issues": issues,
        "fatal": any(item.get("fatal") for item in issues),
    }
