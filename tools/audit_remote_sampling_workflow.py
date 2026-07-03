#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "ComfyUI-Remote-Sampling"
PROFILE_DIR = PACKAGE_ROOT / "profiles"
FIXED_PROFILE_WARN_LIST = {"anima_qwen_aella_xcn"}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"expected JSON object: {path}")
    return data


def profile_path(profile: str | Path) -> Path:
    raw = Path(profile)
    if raw.exists():
        return raw
    name = str(profile).replace("\\", "/")
    if name.endswith(".json"):
        return PROFILE_DIR / name
    return PROFILE_DIR / f"{name}.json"


def profile_id(profile: str | Path) -> str:
    name = str(profile).replace("\\", "/")
    return Path(name).with_suffix("").name


def is_fixed_profile(profile: str | Path) -> bool:
    return profile_id(profile) in FIXED_PROFILE_WARN_LIST


def load_profile(profile: str | Path) -> tuple[dict[str, Any] | None, Path]:
    path = profile_path(profile)
    if not path.exists():
        return None, path
    return read_json(path), path


def lora_summary(loras: Any) -> list[dict[str, Any]]:
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


def profile_summary(profile_name: str, profile: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    if profile is None:
        return {
            "profile": profile_name,
            "profile_path": str(path),
            "exists": False,
            "warnings": [f"profile not found: {path}"],
            "errors": [f"profile not found: {path}"],
        }
    warnings: list[str] = []
    errors: list[str] = []
    profile_id = str(profile.get("name") or profile_name)
    if is_fixed_profile(profile_id) or is_fixed_profile(profile_name):
        warnings.append(
            "fixed profile anima_qwen_aella_xcn loads Aella/xcn LoRA; unsafe for equivalence tests unless explicitly intended"
        )
    loras = lora_summary(profile.get("loras"))
    return {
        "profile": profile_id,
        "profile_path": str(path),
        "exists": True,
        "unet": profile.get("unet", {}),
        "clip": profile.get("clip", {}),
        "loras": loras,
        "lora_count": len(loras),
        "warnings": warnings,
        "errors": errors,
    }


def audit_profile(profile_name: str) -> dict[str, Any]:
    profile, path = load_profile(profile_name)
    return {
        "kind": "profile",
        "profile": profile_summary(profile_name, profile, path),
        "warnings": profile_summary(profile_name, profile, path).get("warnings", []),
        "errors": profile_summary(profile_name, profile, path).get("errors", []),
    }


def remote_sampling_nodes(prompt: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    nodes: list[tuple[str, dict[str, Any]]] = []
    for node_id, node in prompt.items():
        if isinstance(node, dict) and node.get("class_type") == "Remote_Sampling_local":
            nodes.append((str(node_id), node))
    return nodes


def audit_workflow(path: Path) -> dict[str, Any]:
    prompt = read_json(path)
    samplers: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    for node_id, node in remote_sampling_nodes(prompt):
        inputs = node.get("inputs", {})
        profile_name = str(inputs.get("remote_profile", ""))
        if not profile_name:
            summary = {
                "node": node_id,
                "sampler_id": inputs.get("sampler_id"),
                "remote_profile": None,
                "errors": ["Remote_Sampling_local has no remote_profile"],
            }
            errors.extend(summary["errors"])
            samplers.append(summary)
            continue
        profile, path_found = load_profile(profile_name)
        summary = profile_summary(profile_name, profile, path_found)
        warnings.extend(summary.get("warnings", []))
        errors.extend(summary.get("errors", []))
        samplers.append(
            {
                "node": node_id,
                "sampler_id": inputs.get("sampler_id"),
                "remote_profile": profile_name,
                "profile": summary,
            }
        )
    if not samplers:
        warnings.append("no Remote_Sampling_local nodes found")
    return {
        "kind": "workflow",
        "path": str(path),
        "remote_sampling_nodes": samplers,
        "warnings": warnings,
        "errors": errors,
    }


def audit_job(path: Path) -> dict[str, Any]:
    job_dir = path if path.is_dir() else path.parent
    job_path = path / "job.json" if path.is_dir() else path
    job = read_json(job_path)
    profile_name = str(job.get("remote_profile") or job.get("profile", {}).get("name") or "")
    embedded_profile = job.get("profile") if isinstance(job.get("profile"), dict) else None
    if embedded_profile is None and profile_name:
        loaded_profile, loaded_path = load_profile(profile_name)
    else:
        loaded_profile = embedded_profile
        loaded_path = job_path
    profile = profile_summary(profile_name, loaded_profile, loaded_path) if profile_name else {
        "exists": False,
        "errors": ["job has no remote_profile/profile.name"],
        "warnings": [],
    }
    remote = job.get("remote", {}) if isinstance(job.get("remote"), dict) else {}
    classes = remote.get("prompt_class_list") or []
    forbidden_image_nodes = remote.get("forbidden_image_nodes") or []
    warnings = list(profile.get("warnings", []))
    errors = list(profile.get("errors", []))
    if forbidden_image_nodes:
        errors.append(f"remote prompt contains forbidden image nodes: {forbidden_image_nodes}")
    return {
        "kind": "job",
        "job_dir": str(job_dir),
        "job_json": str(job_path),
        "remote_profile": profile_name or None,
        "profile": profile,
        "runtime_alignment": job.get("runtime_alignment") if isinstance(job.get("runtime_alignment"), dict) else {},
        "remote_prompt_class_list": classes,
        "remote_lora_loader_count": sum(1 for item in classes if item == "LoraLoader"),
        "forbidden_image_nodes": forbidden_image_nodes,
        "status_exists": (job_dir / "status.json").exists(),
        "result_exists": (job_dir / "result.json").exists(),
        "warnings": warnings,
        "errors": errors,
    }


def audit_bundle(path: Path) -> dict[str, Any]:
    bundle_dir = path
    manifest_path = bundle_dir / "manifest.json"
    audit_path = bundle_dir / "audit.json"
    manifest = read_json(manifest_path)
    audit = read_json(audit_path) if audit_path.is_file() else {}
    profiles = manifest.get("profile_snapshots", [])
    warnings = list(manifest.get("warnings", []))
    errors = list(manifest.get("errors", []))
    if not manifest.get("ok"):
        errors.append(manifest.get("error", {}).get("message", "bundle conversion failed"))
    return {
        "kind": "bundle",
        "run_id": manifest.get("run_id") or bundle_dir.name,
        "run_dir": str(bundle_dir),
        "manifest": str(manifest_path),
        "source_prompt_sha256": manifest.get("source_prompt_sha256"),
        "converted_prompt_sha256": manifest.get("converted_prompt_sha256"),
        "profile_snapshots": profiles,
        "converted_node_ids": manifest.get("converted_node_ids", []),
        "audit": audit,
        "warnings": warnings,
        "errors": errors,
    }


def format_loras(loras: list[dict[str, Any]]) -> list[str]:
    if not loras:
        return ["    LoRA: none"]
    lines = ["    LoRA:"]
    for item in loras:
        lines.append(
            "      - {name} (model={model}, clip={clip})".format(
                name=item.get("lora_name"),
                model=item.get("strength_model"),
                clip=item.get("strength_clip"),
            )
        )
    return lines


def format_profile_block(summary: dict[str, Any], indent: str = "  ") -> list[str]:
    if not summary.get("exists"):
        return [f"{indent}Profile missing: {summary.get('profile_path')}"]
    unet = summary.get("unet", {})
    clip = summary.get("clip", {})
    lines = [
        f"{indent}Profile: {summary.get('profile')}",
        f"{indent}Path: {summary.get('profile_path')}",
        f"{indent}UNET: {unet.get('unet_name')} ({unet.get('class_type')})",
        f"{indent}CLIP: {clip.get('clip_name')} ({clip.get('class_type')})",
    ]
    lines.extend(f"{indent}{line}" for line in format_loras(summary.get("loras", [])))
    return lines


def format_human(report: dict[str, Any]) -> str:
    lines = [f"Remote Sampling Audit: {report['kind']}"]
    if report["kind"] == "workflow":
        lines.append(f"Path: {report['path']}")
        for sampler in report["remote_sampling_nodes"]:
            lines.append("")
            lines.append(f"Node {sampler.get('node')} sampler_id={sampler.get('sampler_id')}")
            if "profile" in sampler:
                lines.extend(format_profile_block(sampler["profile"]))
            else:
                lines.extend(f"  ERROR: {err}" for err in sampler.get("errors", []))
    elif report["kind"] == "job":
        lines.append(f"Job: {report['job_dir']}")
        lines.append(f"Job JSON: {report['job_json']}")
        lines.extend(format_profile_block(report["profile"]))
        lines.append(f"  Remote classes: {', '.join(report.get('remote_prompt_class_list') or [])}")
        lines.append(f"  Remote LoraLoader count: {report.get('remote_lora_loader_count')}")
        lines.append(f"  Forbidden image nodes: {report.get('forbidden_image_nodes')}")
        alignment = report.get("runtime_alignment") or {}
        if alignment:
            lines.append(f"  Runtime bundle id: {alignment.get('runtime_bundle_id')}")
            lines.append(f"  Runtime bundle dir: {alignment.get('runtime_bundle_dir')}")
            lines.append(f"  Local prompt sha256: {alignment.get('local_prompt_sha256')}")
            lines.append(f"  Profile sha256: {alignment.get('profile_sha256')}")
            lines.append(f"  Remote prompt sha256: {alignment.get('remote_prompt_sha256')}")
            lines.append(f"  Remote prompt rebuilt per job: {alignment.get('remote_prompt_rebuilt_per_job')}")
        lines.append(f"  status.json exists: {report.get('status_exists')}")
        lines.append(f"  result.json exists: {report.get('result_exists')}")
    elif report["kind"] == "bundle":
        lines.append(f"Run: {report.get('run_id')}")
        lines.append(f"Dir: {report.get('run_dir')}")
        lines.append(f"Source prompt sha256: {report.get('source_prompt_sha256')}")
        lines.append(f"Converted prompt sha256: {report.get('converted_prompt_sha256')}")
        for profile in report.get("profile_snapshots", []):
            lines.append("")
            lines.append(f"Node {profile.get('node')}")
            lines.append(f"  Snapshot profile: {profile.get('snapshot_profile')}")
            lines.append(f"  LoRA count: {profile.get('lora_count')}")
            for lora in profile.get("loras", []):
                lines.append(
                    f"    - {lora.get('lora_name')} (model={lora.get('strength_model')}, clip={lora.get('strength_clip')})"
                )
    elif report["kind"] == "profile":
        lines.extend(format_profile_block(report["profile"]))
    if report.get("warnings"):
        lines.append("")
        lines.append("Warnings:")
        for warning in report["warnings"]:
            lines.append(f"  - {warning}")
    if report.get("errors"):
        lines.append("")
        lines.append("Errors:")
        for error in report["errors"]:
            lines.append(f"  - {error}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Remote_Sampling workflow/job/profile resources and fixed-profile pollution risk."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--workflow", type=Path, help="Converted ComfyUI API prompt JSON to audit.")
    group.add_argument("--job", type=Path, help="Remote sampling job directory or job.json to audit.")
    group.add_argument("--profile", help="Profile name or profile JSON path to audit.")
    group.add_argument("--bundle", type=Path, help="Runtime conversion run bundle directory to audit.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.workflow:
        report = audit_workflow(args.workflow)
    elif args.job:
        report = audit_job(args.job)
    elif args.bundle:
        report = audit_bundle(args.bundle)
    else:
        report = audit_profile(args.profile)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_human(report))
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
