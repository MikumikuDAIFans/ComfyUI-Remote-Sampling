#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


# Defaults point to the original development machine. Override with
# REMOTE_SAMPLING_PROJECT_ROOT and REMOTE_SAMPLING_LOCAL_LORA_ROOT when
# converting workflows on another workstation.
DEFAULT_PROJECT_ROOT = os.environ.get("REMOTE_SAMPLING_PROJECT_ROOT", r"F:\TieguoDun\Remote_comfyui")
DEFAULT_BRIDGE_PYTHON = os.environ.get("REMOTE_SAMPLING_BRIDGE_PYTHON", r"C:\Python314\python.exe")
DEFAULT_REMOTE_PROFILE = "auto"
FIXED_PROFILE_WARN_LIST = {"anima_qwen_aella_xcn"}
DEFAULT_LOCAL_LORA_ROOT = os.environ.get(
    "REMOTE_SAMPLING_LOCAL_LORA_ROOT",
    r"F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\models\loras",
)
PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ComfyUI-Remote-Sampling"
PROFILE_DIR = PACKAGE_ROOT / "profiles"
GENERATED_PROFILE_DIR = PROFILE_DIR / "generated"
OUTPUT_NODE_TYPES = {
    "SaveImage",
    "PreviewImage",
    "SaveLatent",
    "Remote_Sampling_remote",
}
LORA_LOADER_TYPES = {
    "LoraLoader",
    "Lora Loader (LoraManager)",
}
CLIP_LOADER_TYPES = {
    "CLIPLoader",
}
UNET_LOADER_TYPES = {
    "UNETLoader",
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"expected a ComfyUI API prompt object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def json_sha256(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def profile_path(profile_name: str) -> Path:
    normalized = profile_name.replace("\\", "/")
    if normalized.endswith(".json"):
        return PROFILE_DIR / normalized
    return PROFILE_DIR / f"{normalized}.json"


def profile_id(profile_name: str) -> str:
    normalized = profile_name.replace("\\", "/")
    return Path(normalized).with_suffix("").name


def is_fixed_profile(profile_name: str) -> bool:
    return profile_id(profile_name) in FIXED_PROFILE_WARN_LIST


def read_profile(profile_name: str) -> dict[str, Any] | None:
    path = profile_path(profile_name)
    if not path.exists():
        return None
    return read_json(path)


def profile_lora_summary(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not profile:
        return []
    loras = profile.get("loras", [])
    if not isinstance(loras, list):
        return []
    result: list[dict[str, Any]] = []
    for item in loras:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "lora_name": item.get("lora_name"),
                "strength_model": item.get("strength_model"),
                "strength_clip": item.get("strength_clip"),
            }
        )
    return result


def profile_summary(profile_name: str, profile: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "remote_profile": profile_name,
        "profile_path": str(profile_path(profile_name)),
        "is_fixed_profile": is_fixed_profile(profile_name),
        "unet": (profile or {}).get("unet", {}),
        "clip": (profile or {}).get("clip", {}),
        "lora_count": len(profile_lora_summary(profile)),
        "loras": profile_lora_summary(profile),
    }


def iter_refs(value: Any):
    if (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    ):
        yield value[0]
        return
    if isinstance(value, list):
        for item in value:
            yield from iter_refs(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_refs(item)


def reachable_from_outputs(prompt: dict[str, Any]) -> set[str]:
    output_ids = {
        node_id
        for node_id, node in prompt.items()
        if isinstance(node, dict) and node.get("class_type") in OUTPUT_NODE_TYPES
    }
    if not output_ids:
        return set(prompt)

    reachable: set[str] = set()
    stack = list(output_ids)
    while stack:
        node_id = stack.pop()
        if node_id in reachable or node_id not in prompt:
            continue
        reachable.add(node_id)
        inputs = prompt[node_id].get("inputs", {})
        for ref_id in iter_refs(inputs):
            if ref_id not in reachable:
                stack.append(ref_id)
    return reachable


def is_node_ref(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def ref_node(prompt: dict[str, Any], ref: Any) -> tuple[str, dict[str, Any]] | None:
    if not is_node_ref(ref):
        return None
    node_id = ref[0]
    node = prompt.get(node_id)
    if not isinstance(node, dict):
        return None
    return node_id, node


def parse_float(value: Any, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def relative_lora_path(path: Path, lora_root: Path) -> str:
    try:
        return path.relative_to(lora_root).as_posix()
    except ValueError:
        return path.name


def resolve_lora_name(name: str, lora_root: Path) -> str:
    cleaned = name.strip()
    if cleaned.endswith(".safetensors") and ("/" in cleaned or "\\" in cleaned):
        return cleaned.replace("\\", "/")
    stem = Path(cleaned).stem
    if lora_root.is_dir():
        candidates = list(lora_root.rglob(f"{stem}.safetensors"))
        if not candidates and cleaned.endswith(".safetensors"):
            candidates = list(lora_root.rglob(cleaned))
        if candidates:
            candidates.sort(key=lambda p: (len(str(p)), str(p).casefold()))
            return relative_lora_path(candidates[0], lora_root)
    return cleaned if cleaned.endswith(".safetensors") else f"{cleaned}.safetensors"


def loras_from_lora_manager(node: dict[str, Any], lora_root: Path) -> list[dict[str, Any]]:
    raw_loras = node.get("inputs", {}).get("loras", {}).get("__value__", [])
    if not isinstance(raw_loras, list):
        return []
    loras: list[dict[str, Any]] = []
    for raw in raw_loras:
        if not isinstance(raw, dict) or raw.get("active") is False:
            continue
        name = raw.get("name")
        if not name:
            continue
        strength_model = parse_float(raw.get("strength"), 1.0)
        strength_clip = parse_float(raw.get("clipStrength"), strength_model)
        loras.append(
            {
                "class_type": "LoraLoader",
                "lora_name": resolve_lora_name(str(name), lora_root),
                "strength_model": strength_model,
                "strength_clip": strength_clip,
            }
        )
    return loras


def model_chain_profile(
    prompt: dict[str, Any],
    model_ref: Any,
    lora_root: Path,
    seen: set[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    target = ref_node(prompt, model_ref)
    if target is None:
        raise ValueError(f"cannot resolve model reference: {model_ref!r}")
    node_id, node = target
    if seen is None:
        seen = set()
    if node_id in seen:
        raise ValueError(f"cycle in model chain at node {node_id}")
    seen.add(node_id)

    class_type = node.get("class_type")
    inputs = node.get("inputs", {})
    if class_type in UNET_LOADER_TYPES:
        return (
            {
                "class_type": class_type,
                "unet_name": inputs["unet_name"],
                "weight_dtype": inputs.get("weight_dtype", "default"),
            },
            [],
        )
    if class_type == "LoraLoader":
        unet, loras = model_chain_profile(prompt, inputs.get("model"), lora_root, seen)
        loras.append(
            {
                "class_type": "LoraLoader",
                "lora_name": resolve_lora_name(str(inputs["lora_name"]), lora_root),
                "strength_model": parse_float(inputs.get("strength_model"), 1.0),
                "strength_clip": parse_float(inputs.get("strength_clip"), 1.0),
            }
        )
        return unet, loras
    if class_type == "Lora Loader (LoraManager)":
        unet, loras = model_chain_profile(prompt, inputs.get("model"), lora_root, seen)
        loras.extend(loras_from_lora_manager(node, lora_root))
        return unet, loras
    raise ValueError(f"unsupported model chain node {node_id}: {class_type}")


def clip_loader_profile(
    prompt: dict[str, Any],
    clip_ref: Any,
    seen: set[str] | None = None,
) -> dict[str, Any]:
    target = ref_node(prompt, clip_ref)
    if target is None:
        raise ValueError(f"cannot resolve clip reference: {clip_ref!r}")
    node_id, node = target
    if seen is None:
        seen = set()
    if node_id in seen:
        raise ValueError(f"cycle in clip chain at node {node_id}")
    seen.add(node_id)

    class_type = node.get("class_type")
    inputs = node.get("inputs", {})
    if class_type in CLIP_LOADER_TYPES:
        return {
            "class_type": class_type,
            "clip_name": inputs["clip_name"],
            "type": inputs.get("type", "stable_diffusion"),
            "device": inputs.get("device", "default"),
        }
    if class_type in LORA_LOADER_TYPES:
        return clip_loader_profile(prompt, inputs.get("clip"), seen)
    raise ValueError(f"unsupported clip chain node {node_id}: {class_type}")


def first_conditioning_clip_ref(prompt: dict[str, Any], sampler_inputs: dict[str, Any]) -> Any | None:
    for key in ("positive", "negative"):
        cond = ref_node(prompt, sampler_inputs.get(key))
        if cond is None:
            continue
        _node_id, node = cond
        inputs = node.get("inputs", {})
        if "clip" in inputs:
            return inputs["clip"]
    return None


def write_generated_profile(
    *,
    prompt: dict[str, Any],
    sampler_node_id: str,
    sampler_inputs: dict[str, Any],
    output_path: Path,
    lora_root: Path,
) -> tuple[str, dict[str, Any]]:
    unet, loras = model_chain_profile(prompt, sampler_inputs.get("model"), lora_root)
    clip_ref = first_conditioning_clip_ref(prompt, sampler_inputs)
    if clip_ref is None:
        raise ValueError(f"KSampler node {sampler_node_id} has no CLIPTextEncode clip reference to infer profile")
    clip = clip_loader_profile(prompt, clip_ref)
    profile_name = f"auto_{output_path.stem}_{sampler_node_id}"
    relative_profile = f"generated/{profile_name}"
    profile = {
        "name": relative_profile,
        "description": f"Auto-generated from {output_path.name}, KSampler node {sampler_node_id}.",
        "conversion_source": {
            "output_workflow": str(output_path),
            "sampler_node_id": sampler_node_id,
            "source_prompt_sha256": json_sha256(prompt),
        },
        "unet": unet,
        "clip": clip,
        "loras": loras,
    }
    GENERATED_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    write_json(GENERATED_PROFILE_DIR / f"{profile_name}.json", profile)
    return relative_profile, profile


def bypass_lora_clip_ref(prompt: dict[str, Any], ref: Any) -> Any:
    if not is_node_ref(ref):
        return ref
    current = list(ref)
    seen: set[str] = set()
    while True:
        node_id = current[0]
        if node_id in seen:
            return current
        seen.add(node_id)
        node = prompt.get(node_id)
        if not isinstance(node, dict) or node.get("class_type") not in LORA_LOADER_TYPES:
            return current
        upstream = node.get("inputs", {}).get("clip")
        if not is_node_ref(upstream):
            return current
        current = list(upstream)


def bypass_local_lora_clip_loaders(prompt: dict[str, Any]) -> list[dict[str, Any]]:
    rewired: list[dict[str, Any]] = []
    for node_id, node in prompt.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or "clip" not in inputs:
            continue
        old_ref = inputs["clip"]
        new_ref = bypass_lora_clip_ref(prompt, old_ref)
        if new_ref != old_ref:
            inputs["clip"] = new_ref
            rewired.append({"node": node_id, "from": old_ref, "to": new_ref})
    return rewired


def convert_prompt(
    prompt: dict[str, Any],
    remote_profile: str,
    project_root: str,
    python_executable: str,
    timeout_sec: int,
    sampler_prefix: str,
    prune_unreachable: bool,
    bypass_local_lora_clip: bool,
    allow_fixed_profile: bool,
    output_path: Path,
    lora_root: Path,
) -> tuple[dict[str, Any], list[str], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    converted = json.loads(json.dumps(prompt, ensure_ascii=False))
    converted_ids: list[str] = []
    rewired_clip_refs: list[dict[str, Any]] = []
    generated_profiles: list[dict[str, Any]] = []

    if bypass_local_lora_clip:
        rewired_clip_refs = bypass_local_lora_clip_loaders(converted)

    if is_fixed_profile(remote_profile) and not allow_fixed_profile:
        raise ValueError(
            "refusing fixed remote profile 'anima_qwen_aella_xcn' because it injects Aella/xcn LoRA. "
            "Use --remote-profile auto for equivalence conversion, or add --allow-fixed-profile only when "
            "you intentionally want this exact remote profile."
        )

    for node_id, node in converted.items():
        if not isinstance(node, dict) or node.get("class_type") != "KSampler":
            continue
        inputs = node.setdefault("inputs", {})
        required = [
            "positive",
            "negative",
            "latent_image",
            "seed",
            "steps",
            "cfg",
            "sampler_name",
            "scheduler",
            "denoise",
        ]
        missing = [name for name in required if name not in inputs]
        if missing:
            raise ValueError(f"KSampler node {node_id} is missing required inputs: {', '.join(missing)}")

        node_remote_profile = remote_profile
        profile_data: dict[str, Any] | None = None
        if remote_profile == "auto":
            node_remote_profile, profile_data = write_generated_profile(
                prompt=converted,
                sampler_node_id=node_id,
                sampler_inputs=inputs,
                output_path=output_path,
                lora_root=lora_root,
            )
        else:
            profile_data = read_profile(node_remote_profile)

        inputs.pop("model", None)
        inputs.setdefault("remote_profile", node_remote_profile)
        inputs.setdefault("project_root", project_root)
        inputs.setdefault("python_executable", python_executable)
        inputs.setdefault("timeout_sec", timeout_sec)
        inputs.setdefault("sampler_id", f"{sampler_prefix}_{node_id}")
        node["class_type"] = "Remote_Sampling_local"
        converted_ids.append(node_id)
        generated_profiles.append(
            {
                "node": node_id,
                "sampler_id": inputs.get("sampler_id"),
                **profile_summary(node_remote_profile, profile_data),
            }
        )

    removed_ids: list[str] = []
    if prune_unreachable:
        keep = reachable_from_outputs(converted)
        removed_ids = sorted(set(converted) - keep, key=lambda item: (len(item), item))
        converted = {node_id: node for node_id, node in converted.items() if node_id in keep}

    return converted, converted_ids, removed_ids, rewired_clip_refs, generated_profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert basic ComfyUI API prompt KSampler nodes to Remote_Sampling_local nodes."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--remote-profile",
        default=DEFAULT_REMOTE_PROFILE,
        help="Use 'auto' to infer a per-sampler remote profile from the original model/LoRA/CLIP chain.",
    )
    parser.add_argument("--project-root", default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--python-executable", default=DEFAULT_BRIDGE_PYTHON)
    parser.add_argument("--timeout-sec", type=int, default=2400)
    parser.add_argument("--sampler-prefix", default="remote")
    parser.add_argument("--lora-root", type=Path, default=Path(DEFAULT_LOCAL_LORA_ROOT))
    parser.add_argument("--keep-unreachable", action="store_true")
    parser.add_argument(
        "--allow-fixed-profile",
        action="store_true",
        help="Allow explicitly selected fixed profiles such as anima_qwen_aella_xcn. Without this flag, fixed profiles are rejected to prevent LoRA pollution.",
    )
    parser.add_argument(
        "--bypass-local-lora-clip",
        action="store_true",
        help="Rewire CLIP inputs that point at local LoRA loaders back to their upstream CLIP, allowing local model/LoRA loader branches to be pruned.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompt = read_json(args.input)
    converted, converted_ids, removed_ids, rewired_clip_refs, generated_profiles = convert_prompt(
        prompt=prompt,
        remote_profile=args.remote_profile,
        project_root=args.project_root,
        python_executable=args.python_executable,
        timeout_sec=args.timeout_sec,
        sampler_prefix=args.sampler_prefix,
        prune_unreachable=not args.keep_unreachable,
        bypass_local_lora_clip=args.bypass_local_lora_clip,
        allow_fixed_profile=args.allow_fixed_profile,
        output_path=args.output,
        lora_root=args.lora_root,
    )
    if not converted_ids:
        raise ValueError("no KSampler nodes found to convert")
    write_json(args.output, converted)
    print(
        json.dumps(
            {
                "ok": True,
                "input": str(args.input),
                "output": str(args.output),
                "converted": converted_ids,
                "rewired_clip_refs": rewired_clip_refs,
                "profile_summary": generated_profiles,
                "removed_unreachable": removed_ids,
                "warnings": [
                    "fixed profile was explicitly allowed; verify the original local workflow intended these LoRA resources"
                ]
                if any(item.get("is_fixed_profile") for item in generated_profiles)
                else [],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
