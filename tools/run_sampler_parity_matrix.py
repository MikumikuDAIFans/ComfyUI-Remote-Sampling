#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any


DEFAULT_PROJECT_ROOT = Path(r"F:\TieguoDun\Remote_comfyui")
DEFAULT_LOCAL_COMFY_ROOT = Path(r"F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI")
DEFAULT_API = "http://127.0.0.1:8188"
RECOMMENDED = {("euler", "normal")}
RISK_WARNING = {("seeds_2", "simple")}


def json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def post_json(api: str, endpoint: str, payload: dict[str, Any], *, timeout: int = 1800) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{api.rstrip('/')}{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{endpoint} returned non-object JSON")
    return data


def get_json(api: str, endpoint: str, *, timeout: int = 20) -> dict[str, Any]:
    with urllib.request.urlopen(f"{api.rstrip('/')}{endpoint}", timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{endpoint} returned non-object JSON")
    return data


def wait_history(api: str, prompt_id: str, *, timeout_sec: int) -> dict[str, Any]:
    start = time.time()
    while time.time() - start < timeout_sec:
        history = get_json(api, f"/history/{prompt_id}", timeout=20)
        item = history.get(prompt_id)
        if isinstance(item, dict):
            status = item.get("status") if isinstance(item.get("status"), dict) else {}
            if status.get("completed") or status.get("status_str") in {"error", "failed"}:
                item["elapsed_sec"] = round(time.time() - start, 3)
                return item
        time.sleep(2)
    raise TimeoutError(f"prompt timed out: {prompt_id}")


def case_policy(sampler_name: str, scheduler: str) -> dict[str, Any]:
    key = (sampler_name, scheduler)
    if key in RECOMMENDED:
        return {
            "classification": "recommended",
            "reason": "已作为稳定推荐组合纳入矩阵；仍需保留每次运行的 prompt/profile/job hash 证据。",
        }
    if key in RISK_WARNING:
        return {
            "classification": "risk_warning",
            "reason": "历史实测存在本地/远端同 seed 结果不一致风险；保留语义但前端/report 应提示。",
        }
    return {
        "classification": "unverified",
        "reason": "尚未建立稳定等价性证据；仅作为探索组合。",
    }


def build_prompt(
    *,
    sampler_name: str,
    scheduler: str,
    seed: int,
    steps: int,
    cfg: float,
    prefix: str,
) -> dict[str, Any]:
    return {
        "45": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_06b_base.safetensors",
                "type": "stable_diffusion",
                "device": "default",
            },
        },
        "11": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "masterpiece, best quality, newest, score_9, small animal, cat, moonlight, simple background",
                "clip": ["45", 0],
            },
        },
        "12": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "worst quality, low quality, blurry, deformed, human",
                "clip": ["45", 0],
            },
        },
        "114": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768, "batch_size": 1}},
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "anima-base-v1.0.safetensors", "weight_dtype": "default"},
        },
        "500": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["11", 0],
                "negative": ["12", 0],
                "latent_image": ["114", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": 1.0,
            },
        },
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae_2.safetensors"}},
        "3": {"class_type": "VAEDecode", "inputs": {"samples": ["500", 0], "vae": ["2", 0]}},
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0], "filename_prefix": prefix}},
    }


def output_images(item: dict[str, Any], local_comfy_root: Path) -> list[dict[str, Any]]:
    outputs = item.get("outputs") if isinstance(item.get("outputs"), dict) else {}
    images: list[dict[str, Any]] = []
    for output in outputs.values():
        if not isinstance(output, dict):
            continue
        for image in output.get("images", []) or []:
            if not isinstance(image, dict):
                continue
            path = local_comfy_root / "output" / str(image.get("subfolder", "")) / str(image.get("filename", ""))
            images.append(
                {
                    **image,
                    "path": str(path),
                    "exists": path.is_file(),
                    "size": path.stat().st_size if path.is_file() else None,
                    "sha256": file_sha256(path),
                }
            )
    return images


def submit_prompt(api: str, prompt: dict[str, Any], *, timeout_sec: int) -> tuple[str, dict[str, Any]]:
    queued = post_json(
        api,
        "/prompt",
        {"prompt": prompt, "client_id": "sampler-parity-" + uuid.uuid4().hex},
        timeout=30,
    )
    prompt_id = str(queued.get("prompt_id"))
    return prompt_id, wait_history(api, prompt_id, timeout_sec=timeout_sec)


def run_case(
    *,
    api: str,
    project_root: Path,
    local_comfy_root: Path,
    sampler_name: str,
    scheduler: str,
    seed: int,
    steps: int,
    cfg: float,
    timeout_sec: int,
    run_remote: bool,
    run_local: bool,
) -> dict[str, Any]:
    slug = f"{sampler_name}_{scheduler}".replace("/", "_")
    source = build_prompt(
        sampler_name=sampler_name,
        scheduler=scheduler,
        seed=seed,
        steps=steps,
        cfg=cfg,
        prefix=f"remote_sampling_parity/{slug}_local",
    )
    result: dict[str, Any] = {
        "sampler_name": sampler_name,
        "scheduler": scheduler,
        "seed": seed,
        "steps": steps,
        "cfg": cfg,
        "policy": case_policy(sampler_name, scheduler),
        "source_prompt_sha256": json_sha256(source),
    }
    if run_local:
        local_prompt = json.loads(json.dumps(source))
        local_prompt["4"]["inputs"]["filename_prefix"] = f"remote_sampling_parity/{slug}_local"
        prompt_id, history = submit_prompt(api, local_prompt, timeout_sec=timeout_sec)
        result["local"] = {
            "prompt_id": prompt_id,
            "status": history.get("status", {}),
            "elapsed_sec": history.get("elapsed_sec"),
            "images": output_images(history, local_comfy_root),
        }
    if run_remote:
        payload = {
            "prompt": source,
            "workflow": source,
            "project_root": str(project_root),
            "options": {
                "project_root": str(project_root),
                "python_executable": r"C:\Python314\python.exe",
                "timeout_sec": timeout_sec,
                "remote_profile": "auto",
                "auto_sync_resources": True,
                "auto_sync_custom_nodes": False,
                "resource_hash_strategy": "size_only",
                "local_comfy_api": api,
            },
        }
        prepared = post_json(api, "/remote_workflow/runtime/run", payload, timeout=max(timeout_sec, 1800))
        if not prepared.get("ok"):
            result["remote"] = {"prepared": prepared, "status": {"status_str": "prepare_failed"}}
        else:
            converted = prepared.get("converted_prompt_object")
            if not isinstance(converted, dict):
                result["remote"] = {"prepared": prepared, "status": {"status_str": "missing_converted_prompt"}}
            else:
                converted["4"]["inputs"]["filename_prefix"] = f"remote_sampling_parity/{slug}_remote"
                prompt_id, history = submit_prompt(api, converted, timeout_sec=timeout_sec)
                result["remote"] = {
                    "run_id": prepared.get("run_id"),
                    "run_dir": prepared.get("run_dir"),
                    "prompt_id": prompt_id,
                    "status": history.get("status", {}),
                    "elapsed_sec": history.get("elapsed_sec"),
                    "images": output_images(history, local_comfy_root),
                    "remote_execution_plan": prepared.get("remote_execution_plan"),
                    "converted_prompt_sha256": prepared.get("converted_local_prompt_sha256"),
                }
    return result


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Sampler Parity Matrix Report",
        "",
        f"- created_at: `{report['created_at']}`",
        f"- project_root: `{report['project_root']}`",
        "",
        "| sampler | scheduler | classification | local | remote | notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        local_status = case.get("local", {}).get("status", {}).get("status_str", "not_run")
        remote_status = case.get("remote", {}).get("status", {}).get("status_str", "not_run")
        policy = case["policy"]
        lines.append(
            f"| `{case['sampler_name']}` | `{case['scheduler']}` | `{policy['classification']}` | "
            f"`{local_status}` | `{remote_status}` | {policy['reason']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_case(text: str) -> tuple[str, str]:
    if "/" in text:
        sampler, scheduler = text.split("/", 1)
    elif ":" in text:
        sampler, scheduler = text.split(":", 1)
    else:
        raise ValueError(f"case must be sampler/scheduler: {text}")
    return sampler.strip(), scheduler.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or prepare a local/remote sampler parity matrix.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--local-comfy-root", type=Path, default=DEFAULT_LOCAL_COMFY_ROOT)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--case", action="append", default=["euler/normal", "seeds_2/simple"])
    parser.add_argument("--seed", type=int, default=2026070807)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--cfg", type=float, default=5.2)
    parser.add_argument("--timeout-sec", type=int, default=2400)
    parser.add_argument("--remote-only", action="store_true")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_local = not args.remote_only and not args.dry_run
    run_remote = not args.local_only and not args.dry_run
    cases = [parse_case(item) for item in args.case]
    report = {
        "schema_version": "sampler-parity-matrix-v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "project_root": str(args.project_root),
        "local_comfy_root": str(args.local_comfy_root),
        "api": args.api,
        "dry_run": bool(args.dry_run),
        "cases": [],
    }
    for sampler_name, scheduler in cases:
        if args.dry_run:
            report["cases"].append(
                {
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "policy": case_policy(sampler_name, scheduler),
                    "status": "dry_run",
                }
            )
        else:
            report["cases"].append(
                run_case(
                    api=args.api,
                    project_root=args.project_root,
                    local_comfy_root=args.local_comfy_root,
                    sampler_name=sampler_name,
                    scheduler=scheduler,
                    seed=args.seed,
                    steps=args.steps,
                    cfg=args.cfg,
                    timeout_sec=args.timeout_sec,
                    run_remote=run_remote,
                    run_local=run_local,
                )
            )
    output = args.output or args.project_root / "runs" / f"sampler_parity_matrix_{time.strftime('%Y%m%d_%H%M%S')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_output = args.markdown_output or output.with_suffix(".md")
    write_markdown(markdown_output, report)
    print(json.dumps({"ok": True, "output": str(output), "markdown_output": str(markdown_output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
