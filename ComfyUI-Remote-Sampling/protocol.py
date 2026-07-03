from __future__ import annotations

import json
import hashlib
import time
import uuid
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = 1
HASH_CHUNK_SIZE = 1024 * 1024
STATUS_FILE = "status.json"
EVENTS_FILE = "events.jsonl"
REPORT_FILE = "remote_sampling_report.txt"


def now_epoch() -> float:
    return time.time()


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def make_run_id(prefix: str = "remote_sampling") -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_dict(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_dict(base[key], value)
        else:
            base[key] = value
    return base


def status_path(job_dir: Path) -> Path:
    return job_dir / STATUS_FILE


def events_path(job_dir: Path) -> Path:
    return job_dir / EVENTS_FILE


def report_path(job_dir: Path) -> Path:
    return job_dir / REPORT_FILE


def init_status(job_dir: Path, *, job_id: str, stage: str = "preparing", message: str = "") -> dict[str, Any]:
    created = now_epoch()
    status = {
        "protocol_version": PROTOCOL_VERSION,
        "job_id": job_id,
        "stage": stage,
        "message": message,
        "created_at": now_text(),
        "created_at_epoch": created,
        "updated_at": now_text(),
        "updated_at_epoch": created,
        "total_elapsed_sec": 0.0,
        "overall_percent": 0.0,
    }
    write_json(status_path(job_dir), status)
    append_event(job_dir, "status_init", {"stage": stage, "message": message})
    return status


def read_status(job_dir: Path) -> dict[str, Any]:
    path = status_path(job_dir)
    if not path.is_file():
        return {}
    return read_json(path)


def update_status(
    job_dir: Path,
    *,
    stage: str | None = None,
    message: str | None = None,
    overall_percent: float | None = None,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    path = status_path(job_dir)
    status = read_json(path) if path.is_file() else {}
    created_now = now_epoch()
    status.setdefault("protocol_version", PROTOCOL_VERSION)
    status.setdefault("created_at", now_text())
    status.setdefault("created_at_epoch", created_now)
    if stage is not None:
        status["stage"] = stage
    if message is not None:
        status["message"] = message
    if overall_percent is not None:
        status["overall_percent"] = round(float(overall_percent), 3)
    if data:
        merge_dict(status, data)
    if error is not None:
        status["error"] = error
    updated = now_epoch()
    status["updated_at"] = now_text()
    status["updated_at_epoch"] = updated
    created = float(status.get("created_at_epoch", updated))
    status["total_elapsed_sec"] = round(updated - created, 3)
    write_json(path, status)
    if event_type:
        append_event(
            job_dir,
            event_type,
            {
                "stage": status.get("stage"),
                "message": status.get("message"),
                "overall_percent": status.get("overall_percent"),
            },
        )
    return status


def append_event(job_dir: Path, event_type: str, payload: dict[str, Any] | None = None) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "time": now_text(),
        "time_epoch": now_epoch(),
        "event": event_type,
    }
    if payload:
        event.update(payload)
    with events_path(job_dir).open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        f.write("\n")


def transfer_metrics(bytes_done: int, elapsed_sec: float) -> dict[str, Any]:
    mb = bytes_done / (1024 * 1024)
    mbps = mb / elapsed_sec if elapsed_sec > 0 else 0.0
    return {
        "bytes": int(bytes_done),
        "mb": round(mb, 3),
        "elapsed_sec": round(elapsed_sec, 3),
        "mbps": round(mbps, 3),
    }


def sampling_metrics(step: int, steps: int, elapsed_sec: float) -> dict[str, Any]:
    completed = max(0, int(step))
    total = max(1, int(steps))
    sec_per_step = elapsed_sec / completed if completed > 0 else None
    remaining = max(0, total - completed)
    eta = remaining * sec_per_step if sec_per_step is not None else None
    return {
        "step": completed,
        "steps": total,
        "percent": round(completed / total * 100, 3),
        "elapsed_sec": round(elapsed_sec, 3),
        "sec_per_step": round(sec_per_step, 3) if sec_per_step is not None else None,
        "eta_sec": round(eta, 3) if eta is not None else None,
    }


def format_report(status: dict[str, Any], result: dict[str, Any] | None = None) -> str:
    lines = [
        "Remote Sampling Report",
        f"job_id: {status.get('job_id', '')}",
        f"stage: {status.get('stage', '')}",
        f"message: {status.get('message', '')}",
        f"total_elapsed_sec: {status.get('total_elapsed_sec', '')}",
    ]
    for key in ("preflight", "upload", "sampling", "download"):
        value = status.get(key)
        if isinstance(value, dict):
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
    if status.get("error"):
        lines.append(f"error: {json.dumps(status['error'], ensure_ascii=False, sort_keys=True)}")
    if result:
        lines.append(f"result: {json.dumps(result, ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines) + "\n"


def write_report(job_dir: Path, result: dict[str, Any] | None = None) -> Path:
    status = read_status(job_dir)
    path = report_path(job_dir)
    path.write_text(format_report(status, result), encoding="utf-8")
    return path


def file_info(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(HASH_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return {"size": path.stat().st_size, "sha256": digest.hexdigest()}


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def json_sha256(data: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(data)).hexdigest()


def save_inputs(path: Path, latent: Any, positive: Any, negative: Any) -> None:
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "latent": latent,
            "positive": positive,
            "negative": negative,
        },
        path,
    )


def load_inputs(path: Path) -> dict[str, Any]:
    import torch

    return torch.load(path, map_location="cpu", weights_only=False)


def save_output(path: Path, latent: Any) -> None:
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"latent": latent}, path)


def load_output(path: Path) -> Any:
    import torch

    return torch.load(path, map_location="cpu", weights_only=False)["latent"]


def build_job_manifest(
    *,
    run_id: str,
    sampler_id: str,
    remote_profile: str,
    seed: int,
    steps: int,
    cfg: float,
    sampler_name: str,
    scheduler: str,
    denoise: float,
) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "sampler_id": sampler_id,
        "remote_profile": remote_profile,
        "created_at": now_text(),
        "files": {
            "inputs": "inputs.pt",
            "output": "output.pt",
            "result": "result.json",
            "status": STATUS_FILE,
            "events": EVENTS_FILE,
            "report": REPORT_FILE,
        },
        "params": {
            "seed": int(seed),
            "steps": int(steps),
            "cfg": float(cfg),
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "denoise": float(denoise),
        },
        "privacy": {
            "contains_rgb_input_image": False,
            "contains_rgb_output_image": False,
            "contains_latent": True,
            "contains_conditioning": True,
        },
    }
