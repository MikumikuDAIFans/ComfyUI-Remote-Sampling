#!/usr/bin/env python3
"""Run a remote latent-only ComfyUI workflow, download the latent, and decode locally.

This script uses the existing company-lab jump-host connection facts from the
company-lab-2-server skill. It keeps remote ComfyUI bound to 127.0.0.1 and uses
SSH/SFTP for command execution and latent download.

For img2img, pass --input-image. The source image is encoded locally to a clean
latent, only that latent is uploaded to the remote ComfyUI input directory, and
remote sampling uses LoadLatent -> KSampler(denoise < 1) -> SaveLatent.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import posixpath
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import paramiko


ROOT = Path(__file__).resolve().parents[1]
# Environment-specific defaults. Keep these as examples for the original lab
# machine; set the matching REMOTE_SAMPLING_* environment variables for another
# server or local ComfyUI layout.
SERVER_EXEC = Path(
    os.environ.get(
        "REMOTE_SAMPLING_SERVER_EXEC",
        r"C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py",
    )
)
REMOTE_BASE = os.environ.get("REMOTE_SAMPLING_REMOTE_BASE", "/home/user02/remote_ComfyUI")
REMOTE_COMFY = f"{REMOTE_BASE}/ComfyUI"
REMOTE_PYTHON = os.environ.get("REMOTE_SAMPLING_REMOTE_PYTHON", f"{REMOTE_BASE}/.venv/bin/python")
REMOTE_HELPER = f"{REMOTE_BASE}/scripts/remote_submit_prompt.py"
DEFAULT_WORKFLOW = ROOT / "workflows" / "ComfyUI_00042_latent_only_api.json"
DEFAULT_LOCAL_COMFY = Path(
    os.environ.get(
        "REMOTE_SAMPLING_LOCAL_COMFY_ROOT",
        r"F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI",
    )
)

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
    req = urllib.request.Request(
        base + "/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        submitted = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(json.dumps({"ok": False, "stage": "submit", "http_code": exc.code, "body": body}, ensure_ascii=False))
        return 2

    prompt_id = submitted["prompt_id"]
    deadline = time.time() + args.timeout
    last_queue_print = 0.0
    while time.time() < deadline:
        history = read_json_url(base + f"/history/{prompt_id}")
        if prompt_id in history:
            item = history[prompt_id]
            status = item.get("status", {})
            ok = status.get("status_str") == "success"
            print(json.dumps({
                "ok": ok,
                "submitted": submitted,
                "history": item,
            }, ensure_ascii=False))
            return 0 if ok else 3
        now = time.time()
        if now - last_queue_print >= 30:
            queue = read_json_url(base + "/queue")
            print(json.dumps({"waiting": prompt_id, "queue": queue}, ensure_ascii=False), flush=True)
            last_queue_print = now
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_remote(client: paramiko.SSHClient, remote_path: str) -> str:
    code, out, err = run_remote(client, f"sha256sum {shell_quote(remote_path)}", timeout=120)
    if code != 0:
        raise RuntimeError(f"remote sha256 failed: {err or out}")
    return out.strip().split()[0]


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def run_remote(client: paramiko.SSHClient, command: str, timeout: int = 60) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(f"cd {shell_quote(REMOTE_BASE)} && {command}", timeout=timeout)
    stdin.close()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = [p for p in remote_dir.split("/") if p]
    current = "/" if remote_dir.startswith("/") else "."
    for part in parts:
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def sftp_write_text(sftp: paramiko.SFTPClient, remote: str, text: str) -> None:
    mkdir_p(sftp, posixpath.dirname(remote))
    with sftp.file(remote + ".uploading", "w") as f:
        f.write(text)
    try:
        sftp.remove(remote)
    except FileNotFoundError:
        pass
    sftp.rename(remote + ".uploading", remote)


def sftp_upload_bytes(sftp: paramiko.SFTPClient, remote: str, content: bytes) -> None:
    mkdir_p(sftp, posixpath.dirname(remote))
    with sftp.file(remote + ".uploading", "wb") as f:
        f.write(content)
    try:
        sftp.remove(remote)
    except FileNotFoundError:
        pass
    sftp.rename(remote + ".uploading", remote)


def sftp_download(sftp: paramiko.SFTPClient, remote: str, local: Path) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    tmp = local.with_name(local.name + ".downloading")
    if tmp.exists():
        tmp.unlink()
    attrs = sftp.stat(remote)
    print(f"download {remote} -> {local} ({attrs.st_size} bytes)", flush=True)
    sftp.get(remote, str(tmp))
    tmp.replace(local)


def sftp_upload_file(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    mkdir_p(sftp, posixpath.dirname(remote))
    tmp = remote + ".uploading"
    try:
        sftp.remove(tmp)
    except FileNotFoundError:
        pass
    print(f"upload {local} -> {remote} ({local.stat().st_size} bytes)", flush=True)
    sftp.put(str(local), tmp)
    try:
        sftp.remove(remote)
    except FileNotFoundError:
        pass
    sftp.rename(tmp, remote)


def request_json(url: str, payload: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
    if payload is None:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read().decode("utf-8"))
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8"))


def wait_local_comfy(url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            request_json(url.rstrip("/") + "/object_info", timeout=5)
            return
        except Exception as exc:
            last = exc
            time.sleep(0.5)
    raise RuntimeError(f"local ComfyUI API is not ready at {url}: {last}")


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


def ensure_remote_comfy(client: paramiko.SSHClient, port: int, run_id: str) -> int | None:
    code, _out, _err = run_remote(client, f"ss -ltn | grep -q ':{port} '", timeout=20)
    if code == 0:
        print(f"remote ComfyUI already listening on 127.0.0.1:{port}", flush=True)
        return None

    log = f"{REMOTE_BASE}/logs/remote_pipeline_{run_id}.log"
    db = f"{REMOTE_COMFY}/user/remote_pipeline_{run_id}.db"
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
        f"os.makedirs({str(log.rsplit('/', 1)[0])!r}, exist_ok=True); "
        f"log=open({log!r}, 'ab', buffering=0); "
        f"p=subprocess.Popen({argv!r}, cwd={REMOTE_BASE!r}, stdin=subprocess.DEVNULL, "
        "stdout=log, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True); "
        "log.close(); "
        "print(p.pid)"
    )
    command = f"python3 -c {shell_quote(launcher)}"
    code, out, err = run_remote(client, command, timeout=30)
    if code != 0:
        raise RuntimeError(f"failed to start remote ComfyUI: {out}\n{err}")
    pid = int(out.strip().splitlines()[-1])
    print(f"started remote ComfyUI pid={pid}, log={log}", flush=True)
    wait_remote_comfy(client, port)
    return pid


def stop_remote_pid(client: paramiko.SSHClient, pid: int) -> None:
    code, out, err = run_remote(client, f"kill {pid} || true; sleep 2; ps -p {pid} >/dev/null && kill -9 {pid} || true", timeout=30)
    if code != 0:
        print(f"warning: failed to stop remote pid {pid}: {out} {err}", file=sys.stderr)


def make_remote_prompt(args: argparse.Namespace, run_id: str, remote_input_latent_name: str | None = None) -> dict[str, Any]:
    prompt = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
    for node in prompt.values():
        if node.get("class_type") == "KSampler":
            if args.steps is not None:
                node["inputs"]["steps"] = args.steps
            if args.seed is not None:
                node["inputs"]["seed"] = args.seed
            if args.denoise is not None:
                node["inputs"]["denoise"] = args.denoise
        if node.get("class_type") == "EmptyLatentImage":
            if args.width is not None:
                node["inputs"]["width"] = args.width
            if args.height is not None:
                node["inputs"]["height"] = args.height
        if node.get("class_type") == "SaveLatent":
            node["inputs"]["filename_prefix"] = f"latents/{run_id}"
    if remote_input_latent_name is not None:
        replaced = False
        for node in prompt.values():
            if node.get("class_type") == "EmptyLatentImage":
                node["class_type"] = "LoadLatent"
                node["inputs"] = {"latent": remote_input_latent_name}
                node["_meta"] = {"title": "Load local-encoded input latent"}
                replaced = True
        if not replaced:
            raise RuntimeError("img2img mode requires a workflow containing an EmptyLatentImage node to replace with LoadLatent")
    return prompt


def run_remote_prompt(
    client: paramiko.SSHClient,
    sftp: paramiko.SFTPClient,
    prompt: dict[str, Any],
    run_id: str,
    port: int,
    timeout: int,
) -> dict[str, Any]:
    sftp_upload_bytes(sftp, REMOTE_HELPER, REMOTE_HELPER_SOURCE.encode("utf-8"))
    code, _out, err = run_remote(client, f"chmod +x {shell_quote(REMOTE_HELPER)}", timeout=20)
    if code != 0:
        raise RuntimeError(f"chmod remote helper failed: {err}")

    remote_prompt = f"{REMOTE_BASE}/workflows/runs/{run_id}_latent_api.json"
    sftp_write_text(sftp, remote_prompt, json.dumps(prompt, ensure_ascii=False, indent=2))
    command = (
        f"{shell_quote(REMOTE_PYTHON)} {shell_quote(REMOTE_HELPER)} "
        f"--prompt {shell_quote(remote_prompt)} --port {port} "
        f"--client-id {shell_quote('remote-pipeline-' + run_id)} --timeout {timeout}"
    )
    print(f"submit remote prompt: {remote_prompt}", flush=True)
    code, out, err = run_remote(client, command, timeout=timeout + 90)
    if err.strip():
        print(err, file=sys.stderr, end="")
    lines = [line for line in out.splitlines() if line.strip()]
    result = json.loads(lines[-1])
    result["remote_prompt"] = remote_prompt
    if code != 0 or not result.get("ok"):
        raise RuntimeError(f"remote prompt failed: {json.dumps(result, ensure_ascii=False)[:4000]}")
    return result


def extract_remote_latents(remote_result: dict[str, Any]) -> list[str]:
    outputs = remote_result["history"].get("outputs", {})
    latents: list[str] = []
    for output in outputs.values():
        for item in output.get("latents", []):
            subfolder = item.get("subfolder") or ""
            filename = item["filename"]
            latents.append(posixpath.join(REMOTE_COMFY, "output", subfolder, filename))
    if not latents:
        raise RuntimeError("remote prompt succeeded but returned no latent outputs")
    return latents


def decode_local(
    args: argparse.Namespace,
    local_latent: Path,
    run_id: str,
) -> dict[str, Any]:
    local_comfy = Path(args.local_comfy_root)
    input_dir = local_comfy / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    input_latent = input_dir / local_latent.name
    shutil.copy2(local_latent, input_latent)

    url = args.local_comfy_url.rstrip("/")
    wait_local_comfy(url)
    prompt = {
        "1": {"class_type": "LoadLatent", "inputs": {"latent": local_latent.name}, "_meta": {"title": "Load downloaded latent"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": args.vae_name}, "_meta": {"title": "Load local VAE"}},
        "3": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0], "vae": ["2", 0]}, "_meta": {"title": "Local VAE Decode"}},
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0], "filename_prefix": f"{args.local_output_subfolder}/{run_id}"}, "_meta": {"title": "Save local image"}},
    }
    decode_prompt_path = ROOT / "workflows" / "runs" / f"{run_id}_local_decode_api.json"
    decode_prompt_path.parent.mkdir(parents=True, exist_ok=True)
    decode_prompt_path.write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")

    submitted = request_json(url + "/prompt", {"prompt": prompt, "client_id": f"local-decode-{run_id}"})
    prompt_id = submitted["prompt_id"]
    deadline = time.time() + args.local_timeout
    while time.time() < deadline:
        history = request_json(url + f"/history/{prompt_id}", timeout=10)
        if prompt_id in history:
            item = history[prompt_id]
            status = item.get("status", {})
            if status.get("status_str") != "success":
                raise RuntimeError(f"local decode failed: {json.dumps(item, ensure_ascii=False)[:4000]}")
            images = []
            for output in item.get("outputs", {}).values():
                for image in output.get("images", []):
                    images.append(image)
            local_images = []
            for image in images:
                path = local_comfy / "output" / (image.get("subfolder") or "") / image["filename"]
                local_images.append({
                    "path": str(path),
                    "size": path.stat().st_size if path.exists() else None,
                    "sha256": sha256_file(path) if path.exists() else None,
                })
            return {
                "submitted": submitted,
                "history": item,
                "input_latent": str(input_latent),
                "decode_prompt": str(decode_prompt_path),
                "images": local_images,
            }
        time.sleep(2)
    raise TimeoutError(f"local decode timed out for prompt_id={prompt_id}")


def encode_input_image_local(args: argparse.Namespace, run_id: str) -> dict[str, Any]:
    if not args.input_image:
        raise ValueError("input_image is required")
    image_src = Path(args.input_image)
    if not image_src.is_file():
        raise FileNotFoundError(image_src)

    local_comfy = Path(args.local_comfy_root)
    input_dir = local_comfy / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    safe_suffix = image_src.suffix if image_src.suffix else ".png"
    image_name = f"{run_id}_input_image{safe_suffix}"
    image_dst = input_dir / image_name
    shutil.copy2(image_src, image_dst)

    url = args.local_comfy_url.rstrip("/")
    wait_local_comfy(url)
    prompt = {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}, "_meta": {"title": "Load local input image"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": args.vae_name}, "_meta": {"title": "Load local VAE"}},
        "3": {"class_type": "VAEEncode", "inputs": {"pixels": ["1", 0], "vae": ["2", 0]}, "_meta": {"title": "Encode input image locally"}},
        "4": {"class_type": "SaveLatent", "inputs": {"samples": ["3", 0], "filename_prefix": f"encoded_inputs/{run_id}_input"}, "_meta": {"title": "Save local input latent"}},
    }
    encode_prompt_path = ROOT / "workflows" / "runs" / f"{run_id}_local_encode_api.json"
    encode_prompt_path.parent.mkdir(parents=True, exist_ok=True)
    encode_prompt_path.write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")

    submitted = request_json(url + "/prompt", {"prompt": prompt, "client_id": f"local-encode-{run_id}"})
    prompt_id = submitted["prompt_id"]
    deadline = time.time() + args.local_timeout
    while time.time() < deadline:
        history = request_json(url + f"/history/{prompt_id}", timeout=10)
        if prompt_id in history:
            item = history[prompt_id]
            status = item.get("status", {})
            if status.get("status_str") != "success":
                raise RuntimeError(f"local input encode failed: {json.dumps(item, ensure_ascii=False)[:4000]}")
            latents = []
            for output in item.get("outputs", {}).values():
                for latent in output.get("latents", []):
                    path = local_comfy / "output" / (latent.get("subfolder") or "") / latent["filename"]
                    latents.append(path)
            if not latents:
                raise RuntimeError("local input encode succeeded but returned no latent output")
            latent_path = latents[0]
            return {
                "source_image": str(image_src),
                "source_image_sha256": sha256_file(image_src),
                "local_comfy_input_image": str(image_dst),
                "encode_prompt": str(encode_prompt_path),
                "submitted": submitted,
                "history": item,
                "local_input_latent": str(latent_path),
                "local_input_latent_size": latent_path.stat().st_size,
                "local_input_latent_sha256": sha256_file(latent_path),
            }
        time.sleep(2)
    raise TimeoutError(f"local input encode timed out for prompt_id={prompt_id}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", default=str(DEFAULT_WORKFLOW), help="Local latent-only ComfyUI API prompt JSON.")
    parser.add_argument("--run-id", default=time.strftime("remote_%Y%m%d_%H%M%S"))
    parser.add_argument("--remote-port", type=int, default=8197)
    parser.add_argument("--remote-timeout", type=int, default=2400)
    parser.add_argument("--keep-remote", action="store_true", help="Do not stop remote ComfyUI if this script starts it.")
    parser.add_argument("--steps", type=int, help="Override KSampler steps for this run.")
    parser.add_argument("--width", type=int, help="Override EmptyLatentImage width for this run.")
    parser.add_argument("--height", type=int, help="Override EmptyLatentImage height for this run.")
    parser.add_argument("--seed", type=int, help="Override KSampler seed for this run.")
    parser.add_argument("--denoise", type=float, help="Override KSampler denoise. Required behavior for img2img is usually < 1.")
    parser.add_argument("--input-image", help="Local image path for img2img. The image is VAE-encoded locally; only the latent is uploaded.")
    parser.add_argument("--latents-dir", default=str(ROOT / "latents"))
    parser.add_argument("--metadata-dir", default=str(ROOT / "runs"))
    parser.add_argument("--no-decode", action="store_true")
    parser.add_argument("--local-comfy-url", default="http://127.0.0.1:8188")
    parser.add_argument("--local-comfy-root", default=str(DEFAULT_LOCAL_COMFY))
    parser.add_argument("--local-output-subfolder", default="remote_decode")
    parser.add_argument("--local-timeout", type=int, default=900)
    parser.add_argument("--vae-name", default="qwen_image_vae_2.safetensors")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = args.run_id
    if args.input_image and args.denoise is None:
        args.denoise = 0.55
    if args.input_image and not (0.0 <= args.denoise <= 1.0):
        raise ValueError("--denoise must be between 0 and 1")
    metadata: dict[str, Any] = {
        "run_id": run_id,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "workflow": str(Path(args.workflow).resolve()),
        "remote_port": args.remote_port,
        "mode": "img2img" if args.input_image else "txt2img",
        "overrides": {"steps": args.steps, "width": args.width, "height": args.height, "seed": args.seed, "denoise": args.denoise},
    }

    server_exec = load_server_exec()
    ssh_port = server_exec.free_port()
    tunnel: subprocess.Popen[str] = server_exec.open_tunnel(ssh_port)
    remote_pid: int | None = None
    client: paramiko.SSHClient | None = None
    sftp: paramiko.SFTPClient | None = None
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
        sftp = paramiko.SFTPClient.from_transport(
            transport,
            window_size=128 * 1024 * 1024,
            max_packet_size=16 * 1024 * 1024,
        )

        remote_input_latent_name: str | None = None
        if args.input_image:
            encoded = encode_input_image_local(args, run_id)
            remote_input_latent_name = f"{run_id}_input.latent"
            remote_input_latent = f"{REMOTE_COMFY}/input/{remote_input_latent_name}"
            sftp_upload_file(sftp, Path(encoded["local_input_latent"]), remote_input_latent)
            encoded["remote_input_latent"] = remote_input_latent
            encoded["remote_input_latent_name"] = remote_input_latent_name
            encoded["remote_input_latent_sha256"] = sha256_remote(client, remote_input_latent)
            metadata["local_input_encode"] = encoded

        prompt = make_remote_prompt(args, run_id, remote_input_latent_name)

        remote_pid = ensure_remote_comfy(client, args.remote_port, run_id)
        metadata["remote_started_pid"] = remote_pid
        remote_result = run_remote_prompt(client, sftp, prompt, run_id, args.remote_port, args.remote_timeout)
        metadata["remote"] = remote_result

        remote_latents = extract_remote_latents(remote_result)
        local_latents = []
        for remote_latent in remote_latents:
            local_latent = Path(args.latents_dir) / Path(remote_latent).name
            sftp_download(sftp, remote_latent, local_latent)
            local_latents.append({
                "remote_path": remote_latent,
                "remote_sha256": sha256_remote(client, remote_latent),
                "local_path": str(local_latent),
                "local_size": local_latent.stat().st_size,
                "local_sha256": sha256_file(local_latent),
            })
        metadata["latents"] = local_latents

        if not args.no_decode:
            metadata["local_decode"] = decode_local(args, Path(local_latents[0]["local_path"]), run_id)

        metadata["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        metadata_dir = Path(args.metadata_dir)
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = metadata_dir / f"{run_id}.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"metadata: {metadata_path}", flush=True)
        if metadata.get("local_decode", {}).get("images"):
            for image in metadata["local_decode"]["images"]:
                print(f"local image: {image['path']}", flush=True)
        return 0
    finally:
        if remote_pid is not None and not args.keep_remote and client is not None:
            stop_remote_pid(client, remote_pid)
        if sftp is not None:
            sftp.close()
        if client is not None:
            client.close()
        if tunnel.poll() is None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=4)
            except subprocess.TimeoutExpired:
                tunnel.kill()


if __name__ == "__main__":
    raise SystemExit(main())
