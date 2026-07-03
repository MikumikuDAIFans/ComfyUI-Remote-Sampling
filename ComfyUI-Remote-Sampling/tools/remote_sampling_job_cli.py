#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import posixpath
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import paramiko


# Deployment defaults for the original lab environment. Users running this
# outside that environment should override these with environment variables
# instead of editing call sites throughout the file.
SERVER_EXEC = Path(
    os.environ.get(
        "REMOTE_SAMPLING_SERVER_EXEC",
        r"C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py",
    )
)
REMOTE_BASE = os.environ.get("REMOTE_SAMPLING_REMOTE_BASE", "/home/user02/remote_ComfyUI")
REMOTE_COMFY = f"{REMOTE_BASE}/ComfyUI"
REMOTE_PYTHON = os.environ.get("REMOTE_SAMPLING_REMOTE_PYTHON", f"{REMOTE_BASE}/.venv/bin/python")
REMOTE_JOB_ROOT = f"{REMOTE_BASE}/jobs"
REMOTE_HELPER = f"{REMOTE_BASE}/scripts/remote_submit_prompt.py"
REMOTE_LOCK_ROOT = f"{REMOTE_BASE}/locks"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = PACKAGE_ROOT / "profiles"
LOCAL_COMFY_MODELS = Path(
    os.environ.get(
        "REMOTE_SAMPLING_LOCAL_COMFY_MODELS",
        r"F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\models",
    )
)
FORBIDDEN_REMOTE_IMAGE_NODES = {
    "LoadImage",
    "VAEEncode",
    "VAELoader",
    "VAEDecode",
    "PreviewImage",
    "SaveImage",
}


def load_protocol():
    spec = importlib.util.spec_from_file_location("remote_sampling_protocol", PACKAGE_ROOT / "protocol.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load remote sampling protocol")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


protocol = load_protocol()

REMOTE_HELPER_SOURCE = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


def read_json_url(url: str, timeout: float = 10.0):
    return json.loads(urllib.request.urlopen(url, timeout=timeout).read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    prompt = json.load(open(args.prompt, encoding="utf-8"))
    base = f"http://127.0.0.1:{args.port}"
    payload = json.dumps({"prompt": prompt, "client_id": args.client_id}).encode("utf-8")
    req = urllib.request.Request(base + "/prompt", data=payload, headers={"Content-Type": "application/json"})
    try:
        submitted = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(json.dumps({"ok": False, "stage": "submit", "http_code": exc.code, "body": exc.read().decode("utf-8", errors="replace")}, ensure_ascii=False))
        return 2

    prompt_id = submitted["prompt_id"]
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        history = read_json_url(base + f"/history/{prompt_id}")
        if prompt_id in history:
            item = history[prompt_id]
            ok = item.get("status", {}).get("status_str") == "success"
            print(json.dumps({"ok": ok, "submitted": submitted, "history": item}, ensure_ascii=False))
            return 0 if ok else 3
        time.sleep(5)
    print(json.dumps({"ok": False, "stage": "timeout", "submitted": submitted}, ensure_ascii=False))
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
'''


def load_server_exec():
    spec = importlib.util.spec_from_file_location("company_lab_server_exec", SERVER_EXEC)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SERVER_EXEC}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait_local_port(port: int, timeout: float = 12.0) -> None:
    deadline = time.time() + timeout
    last_error: OSError | None = None
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.25)
    raise TimeoutError(f"local tunnel port {port} not ready: {last_error}")


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def run_remote(client: paramiko.SSHClient, command: str, timeout: int = 60) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(f"cd {shell_quote(REMOTE_BASE)} && {command}", timeout=timeout)
    stdin.close()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def emit_progress(event: str, overall_percent: float | None = None, **payload: Any) -> None:
    data = {"event": event}
    if overall_percent is not None:
        data["overall_percent"] = round(float(overall_percent), 3)
    data.update(payload)
    print("RS_PROGRESS " + json.dumps(data, ensure_ascii=False, sort_keys=True), flush=True)


def mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = [p for p in remote_dir.split("/") if p]
    current = "/" if remote_dir.startswith("/") else "."
    for part in parts:
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


class TransferMeter:
    def __init__(self, *, job_dir: Path, stage: str, label: str, start_percent: float, end_percent: float):
        self.job_dir = job_dir
        self.stage = stage
        self.label = label
        self.start_percent = start_percent
        self.end_percent = end_percent
        self.started = time.time()
        self.last_emit = 0.0
        self.last_metrics: dict[str, Any] = {}

    def update(self, sent: int, total: int, *, force: bool = False) -> None:
        now = time.time()
        if not force and now - self.last_emit < 0.75 and sent < total:
            return
        elapsed = max(0.001, now - self.started)
        metrics = protocol.transfer_metrics(sent, elapsed)
        metrics["bytes_total"] = int(total)
        metrics["bytes_done"] = int(sent)
        metrics["percent"] = round((sent / total * 100) if total else 100.0, 3)
        self.last_metrics = metrics
        local_percent = self.start_percent
        if total:
            local_percent += (self.end_percent - self.start_percent) * (sent / total)
        data = {self.stage: metrics}
        protocol.update_status(
            self.job_dir,
            stage=self.stage,
            message=f"{self.label}: {metrics['percent']}%",
            overall_percent=local_percent,
            data=data,
        )
        emit_progress(self.stage, local_percent, **data)
        self.last_emit = now


def upload_file(
    sftp: paramiko.SFTPClient,
    local: Path,
    remote: str,
    meter: TransferMeter | None = None,
) -> dict[str, Any] | None:
    mkdir_p(sftp, posixpath.dirname(remote))
    tmp = remote + ".uploading"
    try:
        sftp.remove(tmp)
    except FileNotFoundError:
        pass
    if meter is not None:
        total = local.stat().st_size

        def callback(sent: int, total_bytes: int) -> None:
            meter.update(sent, total_bytes)

        sftp.put(str(local), tmp, callback=callback)
        meter.update(total, total, force=True)
    else:
        sftp.put(str(local), tmp)
    try:
        sftp.remove(remote)
    except FileNotFoundError:
        pass
    sftp.rename(tmp, remote)
    return meter.last_metrics if meter is not None else None


def upload_text(sftp: paramiko.SFTPClient, remote: str, text: str) -> None:
    mkdir_p(sftp, posixpath.dirname(remote))
    tmp = remote + ".uploading"
    with sftp.file(tmp, "w") as f:
        f.write(text)
    try:
        sftp.remove(remote)
    except FileNotFoundError:
        pass
    sftp.rename(tmp, remote)


def download_file(
    sftp: paramiko.SFTPClient,
    remote: str,
    local: Path,
    meter: TransferMeter | None = None,
) -> dict[str, Any] | None:
    local.parent.mkdir(parents=True, exist_ok=True)
    tmp = local.with_name(local.name + ".downloading")
    if tmp.exists():
        tmp.unlink()
    if meter is not None:

        def callback(sent: int, total_bytes: int) -> None:
            meter.update(sent, total_bytes)

        sftp.get(remote, str(tmp), callback=callback)
        final_size = tmp.stat().st_size if tmp.exists() else 0
        meter.update(final_size, final_size, force=True)
    else:
        sftp.get(remote, str(tmp))
    tmp.replace(local)
    return meter.last_metrics if meter is not None else None


def wait_remote_comfy(client: paramiko.SSHClient, port: int, timeout: int = 180) -> None:
    command = (
        f"{shell_quote(REMOTE_PYTHON)} - <<'PY'\n"
        "import json, time, urllib.request\n"
        f"url='http://127.0.0.1:{port}/object_info'\n"
        f"deadline=time.time()+{timeout}\n"
        "last=None\n"
        "while time.time()<deadline:\n"
        "    try:\n"
        "        data=json.loads(urllib.request.urlopen(url, timeout=5).read().decode())\n"
        "        print('ready', len(data))\n"
        "        raise SystemExit(0)\n"
        "    except Exception as e:\n"
        "        last=e; time.sleep(1)\n"
        "print('timeout', repr(last))\n"
        "raise SystemExit(2)\n"
        "PY"
    )
    code, out, err = run_remote(client, command, timeout=timeout + 30)
    if code != 0:
        raise RuntimeError(f"remote ComfyUI did not become ready: {out}\n{err}")


def ensure_remote_comfy(client: paramiko.SSHClient, port: int, job_id: str) -> int | None:
    code, _out, _err = run_remote(client, f"ss -ltn | grep -q ':{port} '", timeout=20)
    if code == 0:
        return None
    log = f"{REMOTE_BASE}/logs/remote_sampling_node_{job_id}.log"
    db = f"{REMOTE_COMFY}/user/remote_sampling_node_{job_id}.db"
    argv = [
        REMOTE_PYTHON,
        REMOTE_COMFY + "/main.py",
        "--listen",
        "127.0.0.1",
        "--port",
        str(port),
        "--disable-auto-launch",
        "--database-url",
        f"sqlite:///{db}",
    ]
    launcher = (
        "import os, subprocess; "
        f"os.makedirs({log.rsplit('/', 1)[0]!r}, exist_ok=True); "
        f"log=open({log!r}, 'ab', buffering=0); "
        f"p=subprocess.Popen({argv!r}, cwd={REMOTE_BASE!r}, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True); "
        "log.close(); print(p.pid)"
    )
    code, out, err = run_remote(client, f"python3 -c {shell_quote(launcher)}", timeout=30)
    if code != 0:
        raise RuntimeError(f"failed to start remote ComfyUI: {out}\n{err}")
    pid = int(out.strip().splitlines()[-1])
    wait_remote_comfy(client, port)
    return pid


def stop_remote_pid(client: paramiko.SSHClient, pid: int) -> None:
    run_remote(client, f"kill {pid} || true; sleep 2; ps -p {pid} >/dev/null && kill -9 {pid} || true", timeout=30)


def remote_service_lock_path(port: int) -> str:
    return f"{REMOTE_LOCK_ROOT}/remote_sampling_port_{port}.lock"


def acquire_remote_service_lock(client: paramiko.SSHClient, port: int, job_id: str, timeout: int) -> str:
    lock_path = remote_service_lock_path(port)
    metadata = {
        "job_id": job_id,
        "port": port,
        "created_at": time.time(),
        "local_pid": os.getpid(),
    }
    script = (
        "import json, os, shutil, sys, time\n"
        f"lock={lock_path!r}\n"
        f"meta={metadata!r}\n"
        f"deadline=time.time()+{int(timeout)}\n"
        "os.makedirs(os.path.dirname(lock), exist_ok=True)\n"
        "last_report=0\n"
        "while True:\n"
        "    try:\n"
        "        os.mkdir(lock)\n"
        "        meta['acquired_at']=time.time()\n"
        "        with open(os.path.join(lock, 'owner.json'), 'w', encoding='utf-8') as f:\n"
        "            json.dump(meta, f, ensure_ascii=False, indent=2)\n"
        "        print(json.dumps({'ok': True, 'lock': lock}, ensure_ascii=False))\n"
        "        raise SystemExit(0)\n"
        "    except FileExistsError:\n"
        "        stale = False\n"
        "        try:\n"
        "            age = time.time() - os.stat(lock).st_mtime\n"
        "            stale = age > 21600\n"
        "        except FileNotFoundError:\n"
        "            continue\n"
        "        if stale:\n"
        "            stale_path = lock + '.stale.' + str(int(time.time()))\n"
        "            try:\n"
        "                os.rename(lock, stale_path)\n"
        "                shutil.rmtree(stale_path, ignore_errors=True)\n"
        "                continue\n"
        "            except FileNotFoundError:\n"
        "                continue\n"
        "            except OSError:\n"
        "                pass\n"
        "        if time.time() >= deadline:\n"
        "            owner = None\n"
        "            try:\n"
        "                with open(os.path.join(lock, 'owner.json'), encoding='utf-8') as f:\n"
        "                    owner = json.load(f)\n"
        "            except Exception:\n"
        "                owner = None\n"
        "            print(json.dumps({'ok': False, 'lock': lock, 'owner': owner}, ensure_ascii=False))\n"
        "            raise SystemExit(2)\n"
        "        now=time.time()\n"
        "        if now-last_report>=30:\n"
        "            print(json.dumps({'waiting': True, 'lock': lock}, ensure_ascii=False), flush=True)\n"
        "            last_report=now\n"
        "        time.sleep(1)\n"
    )
    code, out, err = run_remote(client, f"python3 - <<'PY'\n{script}PY", timeout=timeout + 30)
    lines = [line for line in out.splitlines() if line.strip()]
    result: dict[str, Any] = {}
    if lines:
        try:
            result = json.loads(lines[-1])
        except json.JSONDecodeError:
            result = {}
    if code != 0 or not result.get("ok"):
        owner = result.get("owner")
        owner_text = json.dumps(owner, ensure_ascii=False) if owner else "unknown"
        raise TimeoutError(f"remote sampling service lock timed out for port {port}; owner={owner_text}; stderr={err.strip()}")
    return lock_path


def release_remote_service_lock(client: paramiko.SSHClient, lock_path: str) -> None:
    script = (
        "import os, shutil\n"
        f"base={REMOTE_LOCK_ROOT!r}\n"
        f"lock={lock_path!r}\n"
        "base=os.path.abspath(base)\n"
        "lock=os.path.abspath(lock)\n"
        "if lock.startswith(base + os.sep) and os.path.isdir(lock):\n"
        "    shutil.rmtree(lock)\n"
    )
    run_remote(client, f"python3 - <<'PY'\n{script}PY", timeout=20)


def profile_path(profile: str) -> Path:
    candidate = Path(profile)
    if candidate.is_file():
        return candidate
    return PROFILE_DIR / f"{profile}.json"


def load_profile(profile: str) -> dict[str, Any]:
    path = profile_path(profile)
    if not path.is_file():
        raise FileNotFoundError(f"remote sampling profile not found: {profile} ({path})")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"profile must be a JSON object: {path}")
    return data


def profile_summary(profile: str, config: dict[str, Any], path: Path) -> dict[str, Any]:
    unet = config.get("unet", {})
    clip = config.get("clip", {})
    loras = config.get("loras", [])
    try:
        source = str(path.relative_to(PACKAGE_ROOT))
    except ValueError:
        source = path.name
    return {
        "name": config.get("name", profile),
        "source": source,
        "description": config.get("description", ""),
        "unet": {
            "unet_name": unet.get("unet_name"),
            "weight_dtype": unet.get("weight_dtype", "default"),
        },
        "clip": {
            "clip_name": clip.get("clip_name"),
            "type": clip.get("type", "stable_diffusion"),
            "device": clip.get("device", "default"),
        },
        "loras": [
            {
                "lora_name": lora.get("lora_name"),
                "strength_model": lora.get("strength_model", 1.0),
                "strength_clip": lora.get("strength_clip", 1.0),
            }
            for lora in loras
            if isinstance(lora, dict)
        ],
    }


def local_resource_hint(kind: str, name: str) -> str:
    subdirs = {
        "unet": ["diffusion_models", "unet"],
        "clip": ["clip"],
        "lora": ["loras"],
    }[kind]
    normalized = name.replace("/", os.sep).replace("\\", os.sep)
    for subdir in subdirs:
        candidate = LOCAL_COMFY_MODELS / subdir / normalized
        if candidate.exists():
            return str(candidate)
    return str(LOCAL_COMFY_MODELS / subdirs[0] / normalized)


def remote_resource_candidates(kind: str, name: str) -> list[str]:
    subdirs = {
        "unet": ["diffusion_models", "unet"],
        "clip": ["clip"],
        "lora": ["loras"],
    }[kind]
    normalized = name.replace("\\", "/")
    return [f"{REMOTE_COMFY}/models/{subdir}/{normalized}" for subdir in subdirs]


def remote_exists(sftp: paramiko.SFTPClient, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False


def preflight_remote_resources(
    sftp: paramiko.SFTPClient,
    job_dir: Path,
    profile: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    resources: list[dict[str, str]] = []
    unet = config.get("unet", {})
    clip = config.get("clip", {})
    if isinstance(unet, dict) and unet.get("unet_name"):
        resources.append({"kind": "unet", "name": str(unet["unet_name"])})
    if isinstance(clip, dict) and clip.get("clip_name"):
        resources.append({"kind": "clip", "name": str(clip["clip_name"])})
    for lora in config.get("loras", []):
        if isinstance(lora, dict) and lora.get("lora_name"):
            resources.append({"kind": "lora", "name": str(lora["lora_name"])})

    checked: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for resource in resources:
        candidates = remote_resource_candidates(resource["kind"], resource["name"])
        found = next((path for path in candidates if remote_exists(sftp, path)), None)
        item = {
            "kind": resource["kind"],
            "name": resource["name"],
            "remote_path": found,
            "remote_candidates": candidates,
        }
        checked.append(item)
        if found is None:
            local_hint = local_resource_hint(resource["kind"], resource["name"])
            expected_remote = candidates[0]
            upload_command = (
                f'python F:\\TieguoDun\\Remote_comfyui\\tools\\upload_to_company_server.py '
                f'"{local_hint}={expected_remote}"'
            )
            missing.append(
                {
                    "kind": resource["kind"],
                    "name": resource["name"],
                    "expected_remote_path": expected_remote,
                    "possible_local_path": local_hint,
                    "upload_command": upload_command,
                }
            )
    result = {"profile": profile, "checked": checked, "missing": missing, "ok": not missing}
    protocol.update_status(
        job_dir,
        stage="preflight",
        message="Remote resource preflight complete" if result["ok"] else "Remote resource preflight failed",
        overall_percent=8,
        data={"preflight": result},
        event_type="preflight",
    )
    emit_progress("preflight", 8, preflight=result)
    if missing:
        details = "\n".join(
            [
                f"- Missing remote {item['kind']}: {item['name']}\n"
                f"  expected: {item['expected_remote_path']}\n"
                f"  local: {item['possible_local_path']}\n"
                f"  upload: {item['upload_command']}"
                for item in missing
            ]
        )
        protocol.update_status(
            job_dir,
            stage="failed",
            message="Remote resources missing",
            error={
                "type": "RemoteResourceMissing",
                "message": details,
                "action_hint": "Upload the missing resources listed above, then retry the workflow.",
            },
        )
        protocol.write_report(job_dir)
        raise RuntimeError(f"Remote resource preflight failed for profile {profile}:\n{details}")
    return result


def prompt_class_list(prompt: dict[str, Any]) -> list[str]:
    return [node.get("class_type", "") for node in prompt.values() if isinstance(node, dict)]


def enrich_job_manifest(
    job_path: Path,
    profile: str,
    remote_job_dir: str,
    remote_prompt: str,
    prompt: dict[str, Any],
) -> dict[str, Any]:
    path = profile_path(profile)
    config = load_profile(profile)
    classes = prompt_class_list(prompt)
    with job_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["profile"] = profile_summary(profile, config, path)
    manifest["profile"]["file"] = protocol.file_info(path)
    manifest["remote"] = {
        "base": REMOTE_BASE,
        "comfy": REMOTE_COMFY,
        "job_dir": remote_job_dir,
        "prompt": remote_prompt,
        "prompt_sha256": protocol.json_sha256(prompt),
        "job_root": REMOTE_JOB_ROOT,
        "prompt_class_list": classes,
        "forbidden_image_nodes": sorted(set(classes) & FORBIDDEN_REMOTE_IMAGE_NODES),
    }
    manifest.setdefault("runtime_alignment", {})
    manifest["runtime_alignment"].update(
        {
            "profile_sha256": manifest["profile"]["file"]["sha256"],
            "remote_prompt_sha256": manifest["remote"]["prompt_sha256"],
            "remote_prompt_rebuilt_per_job": True,
        }
    )
    with job_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return config


def build_profile_prompt(profile: str, job_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    if config is None:
        config = load_profile(profile)
    unet = config.get("unet")
    clip = config.get("clip")
    if not isinstance(unet, dict) or not isinstance(clip, dict):
        raise ValueError(f"profile {profile} must define object fields 'unet' and 'clip'")

    prompt: dict[str, Any] = {
        "44": {
            "class_type": unet.get("class_type", "UNETLoader"),
            "inputs": {
                "unet_name": unet["unet_name"],
                "weight_dtype": unet.get("weight_dtype", "default"),
            },
        },
        "45": {
            "class_type": clip.get("class_type", "CLIPLoader"),
            "inputs": {
                "clip_name": clip["clip_name"],
                "type": clip.get("type", "stable_diffusion"),
                "device": clip.get("device", "default"),
            },
        },
    }

    model_ref: list[Any] = ["44", 0]
    clip_ref: list[Any] = ["45", 0]
    for index, lora in enumerate(config.get("loras", [])):
        if not isinstance(lora, dict):
            raise TypeError(f"profile {profile} loras[{index}] must be an object")
        node_id = str(150 + index)
        prompt[node_id] = {
            "class_type": lora.get("class_type", "LoraLoader"),
            "inputs": {
                "lora_name": lora["lora_name"],
                "strength_model": lora.get("strength_model", 1.0),
                "strength_clip": lora.get("strength_clip", 1.0),
                "model": model_ref,
                "clip": clip_ref,
            },
        }
        model_ref = [node_id, 0]
        clip_ref = [node_id, 1]

    prompt["900"] = {
        "class_type": "Remote_Sampling_remote",
        "inputs": {
            "model": model_ref,
            "job_id": job_id,
            "job_root": REMOTE_JOB_ROOT,
        },
    }
    forbidden = sorted(
        node.get("class_type", "")
        for node in prompt.values()
        if isinstance(node, dict) and node.get("class_type") in FORBIDDEN_REMOTE_IMAGE_NODES
    )
    if forbidden:
        raise ValueError(f"remote profile {profile} contains forbidden image nodes: {forbidden}")
    return prompt


def remote_status_path(remote_job_dir: str) -> str:
    return f"{remote_job_dir}/status.json"


def read_remote_status(sftp: paramiko.SFTPClient, remote_job_dir: str) -> dict[str, Any] | None:
    try:
        with sftp.file(remote_status_path(remote_job_dir), "r") as f:
            return json.loads(f.read().decode("utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def remote_file_exists(sftp: paramiko.SFTPClient, remote_path: str) -> bool:
    try:
        sftp.stat(remote_path)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def read_remote_json(sftp: paramiko.SFTPClient, remote_path: str) -> dict[str, Any] | None:
    try:
        with sftp.file(remote_path, "r") as f:
            return json.loads(f.read().decode("utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def remote_job_completed(sftp: paramiko.SFTPClient, remote_job_dir: str) -> bool:
    result = read_remote_json(sftp, f"{remote_job_dir}/result.json")
    if result is not None and result.get("ok") is False:
        return False
    status = read_remote_status(sftp, remote_job_dir) or {}
    status_ok = status.get("stage") == "completed" or result is not None
    return status_ok and remote_file_exists(sftp, f"{remote_job_dir}/output.pt")


def merge_remote_status_into_local(sftp: paramiko.SFTPClient, remote_job_dir: str, local_job_dir: Path) -> None:
    remote_status = read_remote_status(sftp, remote_job_dir)
    if not remote_status:
        return
    local_status = protocol.read_status(local_job_dir)
    for key in ("sampling", "remote", "error"):
        if key in remote_status:
            local_status[key] = remote_status[key]
    if remote_status.get("stage") == "failed":
        local_status["stage"] = "failed"
        local_status["message"] = remote_status.get("message", local_status.get("message", "Remote failed"))
    protocol.update_status(
        local_job_dir,
        stage=local_status.get("stage", "download"),
        message=local_status.get("message", "Merged remote status"),
        data=local_status,
    )


def append_remote_events(sftp: paramiko.SFTPClient, remote_job_dir: str, local_job_dir: Path) -> None:
    remote_events = f"{remote_job_dir}/events.jsonl"
    try:
        with sftp.file(remote_events, "r") as f:
            text = f.read().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return
    if text.strip():
        with (local_job_dir / "events.jsonl").open("a", encoding="utf-8", newline="\n") as out:
            out.write(text)
            if not text.endswith("\n"):
                out.write("\n")


def sampling_overall_percent(remote_status: dict[str, Any]) -> float | None:
    sampling = remote_status.get("sampling")
    if not isinstance(sampling, dict):
        return None
    percent = sampling.get("percent")
    if percent is None:
        return None
    return 35 + 55 * (float(percent) / 100)


def submit_remote_prompt(
    client: paramiko.SSHClient,
    sftp: paramiko.SFTPClient,
    prompt: dict[str, Any],
    job_id: str,
    remote_job_dir: str,
    local_job_dir: Path,
    port: int,
    timeout: int,
) -> None:
    upload_text(sftp, REMOTE_HELPER, REMOTE_HELPER_SOURCE)
    code, _out, err = run_remote(client, f"chmod +x {shell_quote(REMOTE_HELPER)}", timeout=20)
    if code != 0:
        raise RuntimeError(err)
    remote_prompt = f"{REMOTE_BASE}/workflows/runs/{job_id}_remote_sampling_api.json"
    upload_text(sftp, remote_prompt, json.dumps(prompt, ensure_ascii=False, indent=2))
    command = (
        f"{shell_quote(REMOTE_PYTHON)} {shell_quote(REMOTE_HELPER)} "
        f"--prompt {shell_quote(remote_prompt)} --port {port} "
        f"--client-id {shell_quote('remote-sampling-node-' + job_id)} --timeout {timeout}"
    )
    stdin, stdout, stderr = client.exec_command(f"cd {shell_quote(REMOTE_BASE)} && {command}", timeout=timeout + 90)
    stdin.close()
    channel = stdout.channel
    start = time.time()
    last_poll = 0.0
    last_step: int | None = None
    out_chunks: list[str] = []
    err_chunks: list[str] = []
    while not channel.exit_status_ready():
        now = time.time()
        if now - start > timeout + 60:
            channel.close()
            raise TimeoutError(f"remote prompt timed out after {timeout + 60} seconds")
        if channel.recv_ready():
            out_chunks.append(channel.recv(65536).decode("utf-8", errors="replace"))
        if channel.recv_stderr_ready():
            err_chunks.append(channel.recv_stderr(65536).decode("utf-8", errors="replace"))
        if now - last_poll >= 1.0:
            remote_status = read_remote_status(sftp, remote_job_dir)
            if remote_status:
                percent = sampling_overall_percent(remote_status)
                sampling = remote_status.get("sampling", {})
                if isinstance(sampling, dict) and sampling.get("step") != last_step:
                    last_step = sampling.get("step")
                    protocol.update_status(
                        local_job_dir,
                        stage=remote_status.get("stage", "sampling"),
                        message=remote_status.get("message", "Remote sampling"),
                        overall_percent=percent,
                        data={"sampling": sampling},
                    )
                    emit_progress("sampling", percent, sampling=sampling)
            last_poll = now
        time.sleep(0.2)
    code = channel.recv_exit_status()
    if channel.recv_ready():
        out_chunks.append(channel.recv(65536).decode("utf-8", errors="replace"))
    if channel.recv_stderr_ready():
        err_chunks.append(channel.recv_stderr(65536).decode("utf-8", errors="replace"))
    out = "".join(out_chunks) + stdout.read().decode("utf-8", errors="replace")
    err = "".join(err_chunks) + stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err, file=sys.stderr, end="")
    lines = [line for line in out.splitlines() if line.strip()]
    if not lines:
        if remote_job_completed(sftp, remote_job_dir):
            return
        raise RuntimeError("remote submit produced no output")
    result = json.loads(lines[-1])
    if remote_job_completed(sftp, remote_job_dir):
        return
    if code != 0 or not result.get("ok"):
        raise RuntimeError(f"remote sampling prompt failed: {json.dumps(result, ensure_ascii=False)[:4000]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--remote-profile", required=True)
    parser.add_argument("--remote-port", type=int, default=8197)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--keep-remote", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    job_dir = Path(args.job_dir)
    if not (job_dir / "job.json").is_file() or not (job_dir / "inputs.pt").is_file():
        raise FileNotFoundError(f"job_dir must contain job.json and inputs.pt: {job_dir}")
    job_id = job_dir.name

    server_exec = load_server_exec()
    ssh_port = server_exec.free_port()
    tunnel: subprocess.Popen[str] = server_exec.open_tunnel(ssh_port)
    client: paramiko.SSHClient | None = None
    sftp: paramiko.SFTPClient | None = None
    remote_pid: int | None = None
    remote_lock: str | None = None
    remote_job_dir: str | None = None
    try:
        time.sleep(0.8)
        if tunnel.poll() is not None:
            _out, err = tunnel.communicate(timeout=2)
            print(err, file=sys.stderr, end="")
            return tunnel.returncode or 1
        wait_local_port(ssh_port)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            "127.0.0.1",
            port=ssh_port,
            username=server_exec.SERVER_USER,
            password=os.environ.get("DGX_SERVER_PASSWORD") or server_exec.SERVER_PASSWORD,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
            look_for_keys=False,
            allow_agent=False,
        )
        transport = client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport was not established")
        transport.set_keepalive(30)
        sftp = paramiko.SFTPClient.from_transport(transport, window_size=128 * 1024 * 1024, max_packet_size=16 * 1024 * 1024)

        remote_job_dir = f"{REMOTE_JOB_ROOT}/{job_id}"
        remote_prompt = f"{REMOTE_BASE}/workflows/runs/{job_id}_remote_sampling_api.json"
        profile_config = load_profile(args.remote_profile)
        prompt = build_profile_prompt(args.remote_profile, job_id, profile_config)
        enrich_job_manifest(job_dir / "job.json", args.remote_profile, remote_job_dir, remote_prompt, prompt)
        protocol.update_status(job_dir, stage="preflight", message="Checking remote model resources", overall_percent=6)
        emit_progress("preflight", 6)
        if not args.skip_preflight:
            preflight_remote_resources(sftp, job_dir, args.remote_profile, profile_config)

        protocol.update_status(job_dir, stage="upload", message="Uploading job manifest", overall_percent=10)
        emit_progress("upload", 10)
        upload_file(sftp, job_dir / "job.json", f"{remote_job_dir}/job.json")
        upload_file(sftp, job_dir / "status.json", f"{remote_job_dir}/status.json")
        upload_file(
            sftp,
            job_dir / "inputs.pt",
            f"{remote_job_dir}/inputs.pt",
            TransferMeter(job_dir=job_dir, stage="upload", label="Uploading latent inputs", start_percent=10, end_percent=35),
        )

        protocol.update_status(job_dir, stage="queued", message="Waiting for exclusive remote sampling slot", overall_percent=35)
        emit_progress("queued", 35, lock={"port": args.remote_port, "state": "waiting"})
        remote_lock = acquire_remote_service_lock(client, args.remote_port, job_id, max(300, args.timeout + 120))
        protocol.update_status(job_dir, stage="queued", message="Exclusive remote sampling slot acquired", overall_percent=35)
        emit_progress("queued", 35, lock={"port": args.remote_port, "state": "acquired", "path": remote_lock})

        remote_pid = ensure_remote_comfy(client, args.remote_port, job_id)
        protocol.update_status(job_dir, stage="queued", message="Remote prompt submitted", overall_percent=35)
        emit_progress("queued", 35)
        submit_remote_prompt(client, sftp, prompt, job_id, remote_job_dir, job_dir, args.remote_port, args.timeout)

        protocol.update_status(job_dir, stage="download", message="Downloading output latent", overall_percent=90)
        emit_progress("download", 90)
        download_file(
            sftp,
            f"{remote_job_dir}/output.pt",
            job_dir / "output.pt",
            TransferMeter(job_dir=job_dir, stage="download", label="Downloading output latent", start_percent=90, end_percent=98),
        )
        download_file(sftp, f"{remote_job_dir}/result.json", job_dir / "result.json")
        merge_remote_status_into_local(sftp, remote_job_dir, job_dir)
        append_remote_events(sftp, remote_job_dir, job_dir)
        result = json.load(open(job_dir / "result.json", encoding="utf-8"))
        protocol.update_status(job_dir, stage="completed", message="Remote sampling complete", overall_percent=100)
        protocol.write_report(job_dir, result)
        emit_progress("completed", 100)
        print(json.dumps({"ok": True, "job_id": job_id, "remote_job_dir": remote_job_dir}, ensure_ascii=False))
        return 0
    except Exception as exc:
        if sftp is not None and remote_job_dir is not None:
            try:
                merge_remote_status_into_local(sftp, remote_job_dir, job_dir)
                append_remote_events(sftp, remote_job_dir, job_dir)
            except Exception:
                pass
        current = protocol.read_status(job_dir)
        existing_error = current.get("error") if isinstance(current, dict) else None
        if existing_error:
            protocol.update_status(
                job_dir,
                stage="failed",
                message=current.get("message", "Remote sampling bridge failed"),
            )
        else:
            protocol.update_status(
                job_dir,
                stage="failed",
                message="Remote sampling bridge failed",
                error={
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                },
            )
        try:
            protocol.write_report(job_dir)
        except Exception:
            pass
        raise
    finally:
        if remote_pid is not None and not args.keep_remote and client is not None:
            try:
                stop_remote_pid(client, remote_pid)
            except Exception as cleanup_exc:
                print(f"warning: failed to stop remote pid {remote_pid}: {cleanup_exc}", file=sys.stderr)
        if remote_lock is not None and client is not None:
            try:
                release_remote_service_lock(client, remote_lock)
            except Exception as cleanup_exc:
                print(f"warning: failed to release remote lock {remote_lock}: {cleanup_exc}", file=sys.stderr)
        if sftp is not None:
            try:
                sftp.close()
            except Exception:
                pass
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        if tunnel.poll() is None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=4)
            except subprocess.TimeoutExpired:
                tunnel.kill()


if __name__ == "__main__":
    raise SystemExit(main())
