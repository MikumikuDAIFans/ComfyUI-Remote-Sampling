from pathlib import Path

from aiohttp import web
from server import PromptServer

from .nodes.remote_sampling_local import RemoteSamplingLocal
from .nodes.remote_sampling_remote import RemoteSamplingRemote
from .protocol import read_json
from .runtime_conversion import CONVERTER_VERSION, POLICY_VERSION, convert_runtime_prompt
from .workflow_runtime import (
    create_workflow_runtime_conversion,
    create_workflow_runtime_guarded_run,
    create_workflow_runtime_plan,
    read_workflow_runtime_run_status,
    record_workflow_runtime_client_event,
    workflow_runtime_status,
)


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


@PromptServer.instance.routes.get("/remote_sampling/runtime/status")
async def remote_sampling_runtime_status(request):
    return web.json_response(
        {
            "ok": True,
            "version": CONVERTER_VERSION,
            "policy_version": POLICY_VERSION,
            "capabilities": {
                "convert": True,
                "convert_and_queue": True,
                "queue_mode": "frontend_converts_then_posts_converted_prompt",
                "expects_api_prompt": True,
                "accepts_frontend_workflow_snapshot": True,
                "default_remote_profile": "auto",
                "fixed_profiles_fail_closed": True,
                "remote_prompt_rebuilt_per_job": True,
            },
        },
        headers={"Cache-Control": "no-store"},
    )


@PromptServer.instance.routes.post("/remote_sampling/convert")
async def remote_sampling_runtime_convert(request):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise TypeError("JSON body must be an object")
        result = convert_runtime_prompt(payload)
        status = 200 if result.get("ok") else 400
        return web.json_response(result, status=status, headers={"Cache-Control": "no-store"})
    except Exception as error:
        return web.json_response(
            {
                "ok": False,
                "error": {
                    "type": error.__class__.__name__,
                    "message": str(error),
                },
            },
            status=500,
            headers={"Cache-Control": "no-store"},
        )


@PromptServer.instance.routes.get("/remote_workflow/runtime/status")
async def remote_workflow_runtime_status(request):
    return web.json_response(workflow_runtime_status(), headers={"Cache-Control": "no-store"})


@PromptServer.instance.routes.get("/remote_workflow/runtime/run_status")
async def remote_workflow_runtime_run_status(request):
    run_id = request.query.get("run_id", "")
    project_root = request.query.get("project_root")
    tail_text = request.query.get("tail", "40")
    try:
        tail = max(0, min(500, int(tail_text)))
    except ValueError:
        tail = 40
    if not run_id:
        return web.json_response(
            {
                "ok": False,
                "error": {"type": "InvalidPayload", "message": "run_id query parameter is required."},
            },
            status=400,
            headers={"Cache-Control": "no-store"},
        )
    result = read_workflow_runtime_run_status(project_root, run_id, tail=tail)
    status_code = 200 if result.get("ok") else 404
    return web.json_response(result, status=status_code, headers={"Cache-Control": "no-store"})


@PromptServer.instance.routes.post("/remote_workflow/runtime/plan")
async def remote_workflow_runtime_plan(request):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise TypeError("JSON body must be an object")
        result = create_workflow_runtime_plan(payload)
        status = 200 if result.get("ok") else 400
        return web.json_response(result, status=status, headers={"Cache-Control": "no-store"})
    except Exception as error:
        return web.json_response(
            {
                "ok": False,
                "error": {
                    "type": error.__class__.__name__,
                    "message": str(error),
                },
            },
            status=500,
            headers={"Cache-Control": "no-store"},
        )


@PromptServer.instance.routes.post("/remote_workflow/runtime/client_event")
async def remote_workflow_runtime_client_event(request):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise TypeError("JSON body must be an object")
        result = record_workflow_runtime_client_event(payload)
        status = 200 if result.get("ok") else 400
        return web.json_response(result, status=status, headers={"Cache-Control": "no-store"})
    except Exception as error:
        return web.json_response(
            {
                "ok": False,
                "stage": "failed",
                "error": {"type": type(error).__name__, "message": str(error)},
            },
            status=500,
            headers={"Cache-Control": "no-store"},
        )


@PromptServer.instance.routes.post("/remote_workflow/runtime/convert")
async def remote_workflow_runtime_convert(request):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise TypeError("JSON body must be an object")
        result = create_workflow_runtime_conversion(payload)
        status = 200 if result.get("ok") else 400
        return web.json_response(result, status=status, headers={"Cache-Control": "no-store"})
    except Exception as error:
        return web.json_response(
            {
                "ok": False,
                "error": {
                    "type": error.__class__.__name__,
                    "message": str(error),
                },
            },
            status=500,
            headers={"Cache-Control": "no-store"},
        )


@PromptServer.instance.routes.post("/remote_workflow/runtime/run")
async def remote_workflow_runtime_run(request):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise TypeError("JSON body must be an object")
        result = create_workflow_runtime_guarded_run(payload)
        status = 200 if result.get("ok") else 400
        return web.json_response(result, status=status, headers={"Cache-Control": "no-store"})
    except Exception as error:
        return web.json_response(
            {
                "ok": False,
                "error": {
                    "type": error.__class__.__name__,
                    "message": str(error),
                },
            },
            status=500,
            headers={"Cache-Control": "no-store"},
        )
