from pathlib import Path

from aiohttp import web
from server import PromptServer

from .nodes.remote_sampling_local import RemoteSamplingLocal
from .nodes.remote_sampling_remote import RemoteSamplingRemote
from .protocol import read_json


NODE_CLASS_MAPPINGS = {
    "Remote_Sampling_local": RemoteSamplingLocal,
    "Remote_Sampling_remote": RemoteSamplingRemote,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Remote_Sampling_local": "Remote Sampling Local",
    "Remote_Sampling_remote": "Remote Sampling Remote",
}

# ComfyUI serves JavaScript files from this folder as frontend extensions.
WEB_DIRECTORY = "./web"


def _latest_status_for_sampler(project_root: str, sampler_id: str) -> tuple[Path | None, dict | None]:
    root = Path(project_root).expanduser()
    jobs_dir = root / "jobs"
    if not jobs_dir.is_dir():
        return None, None

    clean_sampler_id = (sampler_id or "sampler_001").strip() or "sampler_001"
    candidates = [
        path
        for path in jobs_dir.iterdir()
        if path.is_dir() and path.name.endswith(f"_{clean_sampler_id}")
    ]
    if not candidates:
        return None, None

    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    status_file = latest / "status.json"
    if not status_file.is_file():
        return latest, None
    return latest, read_json(status_file)


@PromptServer.instance.routes.get("/remote_sampling/status")
async def remote_sampling_status(request):
    project_root = request.query.get("project_root", "")
    sampler_id = request.query.get("sampler_id", "")
    if not project_root:
        return web.json_response(
            {"ok": False, "reason": "missing_project_root"},
            headers={"Cache-Control": "no-store"},
        )

    try:
        job_dir, status = _latest_status_for_sampler(project_root, sampler_id)
    except Exception as error:
        return web.json_response(
            {"ok": False, "reason": "read_error", "error": str(error)},
            status=500,
            headers={"Cache-Control": "no-store"},
        )

    if not job_dir:
        return web.json_response(
            {"ok": False, "reason": "no_job"},
            headers={"Cache-Control": "no-store"},
        )
    if status is None:
        return web.json_response(
            {"ok": False, "reason": "missing_status", "job_dir": str(job_dir)},
            headers={"Cache-Control": "no-store"},
        )

    return web.json_response(
        {"ok": True, "job_dir": str(job_dir), "status": status},
        headers={"Cache-Control": "no-store"},
    )
