from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import comfy.samplers
import comfy.utils
from server import PromptServer

from ..protocol import (
    build_job_manifest,
    file_info,
    init_status,
    json_sha256,
    load_output,
    make_run_id,
    read_json,
    save_inputs,
    update_status,
    write_json,
    write_report,
)


# These defaults match the original Windows development machine. For a public
# install, set REMOTE_SAMPLING_PROJECT_ROOT / REMOTE_SAMPLING_BRIDGE_PYTHON or
# edit the node fields in ComfyUI instead of changing the node code.
DEFAULT_PROJECT_ROOT = Path(os.environ.get("REMOTE_SAMPLING_PROJECT_ROOT", r"F:\TieguoDun\Remote_comfyui"))
DEFAULT_BRIDGE_PYTHON = os.environ.get("REMOTE_SAMPLING_BRIDGE_PYTHON", r"C:\Python314\python.exe")
AUDITED_JOB_FILES = ("inputs.pt", "output.pt", "result.json", "status.json", "events.jsonl", "remote_sampling_report.txt")
PROGRESS_PREFIX = "RS_PROGRESS "
PANEL_EVENT = "remote_sampling_progress"
FIXED_PROFILE_WARN_LIST = {"anima_qwen_aella_xcn"}


def profile_id(profile_name: str) -> str:
    normalized = profile_name.replace("\\", "/")
    return Path(normalized).with_suffix("").name


def is_fixed_profile(profile_name: str) -> bool:
    return profile_id(profile_name) in FIXED_PROFILE_WARN_LIST


def runtime_bundle_info(remote_profile: str) -> dict[str, str | None]:
    path = Path(remote_profile)
    parts = list(path.parts)
    for index, part in enumerate(parts):
        if part == "runs" and index + 1 < len(parts):
            run_id = parts[index + 1]
            if run_id.startswith("runtime_"):
                return {
                    "runtime_bundle_id": run_id,
                    "runtime_bundle_dir": str(Path(*parts[: index + 2])),
                }
    return {"runtime_bundle_id": None, "runtime_bundle_dir": None}


def latent_pixel_size(latent_image) -> tuple[int | None, int | None]:
    samples = latent_image.get("samples") if isinstance(latent_image, dict) else None
    shape = getattr(samples, "shape", None)
    if shape is None or len(shape) < 4:
        return None, None
    return int(shape[-1]) * 8, int(shape[-2]) * 8


def quality_warnings(latent_image, steps: int) -> list[str]:
    width, height = latent_pixel_size(latent_image)
    warnings: list[str] = []
    if steps < 8:
        if width and height:
            warnings.append(
                f"steps={steps} is a smoke-test setting for {width}x{height}; use 20-40 steps for quality checks."
            )
        else:
            warnings.append(f"steps={steps} is a smoke-test setting; use 20-40 steps for quality checks.")
    if width and height and max(width, height) >= 1536 and steps < 20:
        warnings.append(
            f"{width}x{height} with steps={steps} is likely under-sampled; raise steps before judging image quality."
        )
    return warnings


def update_local_audit(job_dir: Path, stdout: str, stderr: str) -> None:
    job_path = job_dir / "job.json"
    manifest: dict[str, Any] = read_json(job_path)
    files = {}
    for name in AUDITED_JOB_FILES:
        path = job_dir / name
        if path.exists():
            files[name] = file_info(path)
    manifest["local"] = {
        "job_dir": str(job_dir),
        "files": files,
        "bridge_stdout_tail": stdout[-4000:],
        "bridge_stderr_tail": stderr[-4000:],
    }
    status_path = job_dir / "status.json"
    if status_path.exists():
        status = read_json(status_path)
        metrics = {
            name: status[name]
            for name in ("preflight", "upload", "sampling", "download")
            if isinstance(status.get(name), dict)
        }
        if metrics:
            manifest["local"]["metrics"] = metrics
    write_json(job_path, manifest)


def read_pipe(pipe, stream_name: str, output: queue.Queue[tuple[str, str | None]]) -> None:
    try:
        for line in iter(pipe.readline, ""):
            output.put((stream_name, line))
    finally:
        output.put((stream_name, None))


def send_panel_event(node_id: str | None, job_id: str, payload: dict[str, Any]) -> None:
    if not node_id:
        return
    data = {
        "node": str(node_id),
        "job_id": job_id,
        **payload,
    }
    try:
        PromptServer.instance.send_sync(PANEL_EVENT, data, PromptServer.instance.client_id)
    except Exception:
        pass


def run_bridge(
    cmd: list[str],
    cwd: Path,
    timeout_sec: int,
    job_dir: Path,
    *,
    node_id: str | None = None,
    job_id: str = "",
) -> tuple[int, str, str]:
    completed = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )
    assert completed.stdout is not None
    assert completed.stderr is not None
    output: queue.Queue[tuple[str, str | None]] = queue.Queue()
    threads = [
        threading.Thread(target=read_pipe, args=(completed.stdout, "stdout", output), daemon=True),
        threading.Thread(target=read_pipe, args=(completed.stderr, "stderr", output), daemon=True),
    ]
    for thread in threads:
        thread.start()

    pbar = comfy.utils.ProgressBar(100)
    pbar.update_absolute(1, 100)
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    deadline = time.time() + timeout_sec + 120
    closed = {"stdout": False, "stderr": False}
    while True:
        if time.time() > deadline:
            completed.kill()
            update_status(
                job_dir,
                stage="failed",
                message="Bridge timeout",
                error={
                    "type": "TimeoutError",
                    "message": f"remote sampling bridge exceeded {timeout_sec + 120} seconds",
                    "action_hint": "Check remote ComfyUI logs and network connectivity, then retry.",
                },
            )
            raise TimeoutError(f"remote sampling bridge exceeded {timeout_sec + 120} seconds")
        try:
            stream, line = output.get(timeout=0.2)
        except queue.Empty:
            if completed.poll() is not None and all(closed.values()):
                break
            continue
        if line is None:
            closed[stream] = True
            if completed.poll() is not None and all(closed.values()):
                break
            continue
        if stream == "stdout":
            stdout_parts.append(line)
            if line.startswith(PROGRESS_PREFIX):
                try:
                    event = json.loads(line[len(PROGRESS_PREFIX) :])
                    send_panel_event(node_id, job_id, event)
                    percent = event.get("overall_percent")
                    if percent is not None:
                        pbar.update_absolute(int(max(0, min(100, float(percent)))), 100)
                except Exception:
                    pass
        else:
            stderr_parts.append(line)
    return completed.wait(), "".join(stdout_parts), "".join(stderr_parts)


class RemoteSamplingLocal:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 8.0, "min": 0.0, "max": 100.0, "step": 0.1, "round": 0.01}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "remote_profile": ("STRING", {"default": "anima_qwen_aella_xcn"}),
                "project_root": ("STRING", {"default": str(DEFAULT_PROJECT_ROOT)}),
                "python_executable": ("STRING", {"default": DEFAULT_BRIDGE_PYTHON}),
                "timeout_sec": ("INT", {"default": 2400, "min": 60, "max": 20000}),
            },
            "optional": {
                "sampler_id": ("STRING", {"default": ""}),
                "allow_fixed_profile": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
            },
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "sample"
    CATEGORY = "remote_sampling"
    DESCRIPTION = "Local proxy sampler: serializes latent/conditioning, asks the remote server to sample, and returns the remote output latent."

    def sample(
        self,
        positive,
        negative,
        latent_image,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        remote_profile,
        project_root,
        python_executable,
        timeout_sec,
        sampler_id="",
        allow_fixed_profile=False,
        unique_id=None,
        prompt=None,
    ):
        root = Path(project_root)
        run_id = make_run_id("remote_sampling")
        clean_sampler_id = sampler_id.strip() or "sampler_001"
        job_id = f"{run_id}_{clean_sampler_id}"
        job_dir = root / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        init_status(job_dir, job_id=job_id, stage="preparing", message="Preparing remote sampling job")
        send_panel_event(
            unique_id,
            job_id,
            {
                "event": "preparing",
                "stage": "preparing",
                "message": "Preparing remote sampling job",
                "overall_percent": 1,
            },
        )

        manifest = build_job_manifest(
            run_id=run_id,
            sampler_id=clean_sampler_id,
            remote_profile=remote_profile,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=denoise,
        )
        manifest["runtime_alignment"] = {
            "local_prompt_sha256": json_sha256(prompt) if prompt is not None else None,
            "local_node_id": str(unique_id) if unique_id is not None else None,
            "remote_profile": remote_profile,
            "remote_profile_id": profile_id(remote_profile),
            "fixed_profile": is_fixed_profile(remote_profile),
            "allow_fixed_profile": bool(allow_fixed_profile),
            "alignment_note": "Remote prompt is rebuilt and uploaded for every job from this runtime profile.",
            **runtime_bundle_info(remote_profile),
        }
        warnings = quality_warnings(latent_image, int(steps))
        if warnings:
            manifest["quality_warnings"] = warnings
        write_json(job_dir / "job.json", manifest)

        if is_fixed_profile(remote_profile) and not allow_fixed_profile:
            message = (
                f"Refusing fixed remote profile '{remote_profile}'. This profile loads Aella/xcn LoRA and can "
                "pollute old converted workflows. Re-convert the original API prompt with "
                "`--remote-profile auto`, or set allow_fixed_profile=true only when this exact profile is intended."
            )
            update_status(
                job_dir,
                stage="failed",
                message="Fixed remote profile refused",
                overall_percent=100,
                error={
                    "type": "FixedRemoteProfileRefused",
                    "message": message,
                    "action_hint": (
                        "Run tools/convert_ksampler_to_remote_sampling.py <input_api.json> <output_api.json> "
                        "--remote-profile auto, then reload the converted workflow."
                    ),
                },
            )
            send_panel_event(
                unique_id,
                job_id,
                {
                    "event": "failed",
                    "stage": "failed",
                    "message": "Fixed remote profile refused",
                    "overall_percent": 100,
                },
            )
            write_report(job_dir)
            raise RuntimeError(message)

        save_inputs(job_dir / "inputs.pt", latent_image, positive, negative)
        update_status(job_dir, stage="preparing", message="Serialized latent and conditioning", overall_percent=5)

        cli = root / "ComfyUI-Remote-Sampling" / "tools" / "remote_sampling_job_cli.py"
        cmd = [
            python_executable,
            str(cli),
            "--job-dir",
            str(job_dir),
            "--remote-profile",
            remote_profile,
            "--timeout",
            str(timeout_sec),
        ]
        returncode, stdout, stderr = run_bridge(
            cmd,
            root,
            timeout_sec,
            job_dir,
            node_id=unique_id,
            job_id=job_id,
        )
        if returncode != 0:
            update_status(job_dir, stage="failed", message="Remote sampling bridge failed")
            send_panel_event(
                unique_id,
                job_id,
                {
                    "event": "failed",
                    "stage": "failed",
                    "message": "Remote sampling bridge failed",
                    "overall_percent": 100,
                },
            )
            write_report(job_dir)
            raise RuntimeError(
                "Remote sampling job failed\n"
                f"command: {' '.join(cmd)}\n"
                f"stdout:\n{stdout}\n"
                f"stderr:\n{stderr}"
            )
        output_path = job_dir / "output.pt"
        if not output_path.exists():
            update_status(job_dir, stage="failed", message="Remote sampling did not produce output latent")
            write_report(job_dir)
            raise FileNotFoundError(f"remote sampling did not produce {output_path}\nstdout:\n{stdout}")
        update_local_audit(job_dir, stdout, stderr)
        update_status(job_dir, stage="completed", message="Remote sampling complete", overall_percent=100)
        send_panel_event(
            unique_id,
            job_id,
            {
                "event": "completed",
                "stage": "completed",
                "message": "Remote sampling complete",
                "overall_percent": 100,
            },
        )
        report_path = write_report(job_dir)
        report_text = report_path.read_text(encoding="utf-8")
        return {"ui": {"text": [report_text]}, "result": (load_output(output_path),)}
