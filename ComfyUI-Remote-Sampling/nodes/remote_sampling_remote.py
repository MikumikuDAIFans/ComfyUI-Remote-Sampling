from __future__ import annotations

import os
import time
import traceback
from pathlib import Path

import comfy.sample
import comfy.utils
from ..protocol import file_info, load_inputs, read_json, sampling_metrics, save_output, update_status, write_json, write_report


class RemoteSamplingRemote:
    @classmethod
    def INPUT_TYPES(cls):
        # Default job root is the original remote lab path. Override with
        # REMOTE_SAMPLING_REMOTE_JOB_ROOT or edit this field in the remote
        # workflow when deploying to another server.
        default_job_root = os.environ.get("REMOTE_SAMPLING_REMOTE_JOB_ROOT", "/home/user02/remote_ComfyUI/jobs")
        return {
            "required": {
                "model": ("MODEL",),
                "job_id": ("STRING", {"default": "remote_sampling_job"}),
                "job_root": ("STRING", {"default": default_job_root}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "sample"
    CATEGORY = "remote_sampling"
    OUTPUT_NODE = True
    DESCRIPTION = "Remote worker node: reads a serialized sampling job, samples with progress callbacks, writes output.pt/result.json."

    def sample_with_progress(self, model, params, positive, negative, latent, job_dir: Path):
        latent_image = latent["samples"]
        latent_image = comfy.sample.fix_empty_latent_channels(
            model,
            latent_image,
            latent.get("downscale_ratio_spacial", None),
            latent.get("downscale_ratio_temporal", None),
        )
        disable_noise = False
        batch_inds = latent["batch_index"] if "batch_index" in latent else None
        noise = comfy.sample.prepare_noise(latent_image, params["seed"], batch_inds)
        noise_mask = latent.get("noise_mask")

        steps = int(params["steps"])
        sampling_started = time.time()
        pbar = comfy.utils.ProgressBar(steps)

        def callback(step, x0, x, total_steps):
            completed = int(step) + 1
            metrics = sampling_metrics(completed, int(total_steps), time.time() - sampling_started)
            update_status(
                job_dir,
                stage="sampling",
                message=f"Remote sampling {completed}/{total_steps}",
                overall_percent=35 + 55 * (metrics["percent"] / 100),
                data={"sampling": metrics},
            )
            pbar.update_absolute(completed, total_steps)

        update_status(
            job_dir,
            stage="sampling",
            message="Remote sampling started",
            overall_percent=35,
            data={"sampling": sampling_metrics(0, steps, 0.0)},
            event_type="sampling_started",
        )
        disable_pbar = not comfy.utils.PROGRESS_BAR_ENABLED
        samples = comfy.sample.sample(
            model,
            noise,
            steps,
            params["cfg"],
            params["sampler_name"],
            params["scheduler"],
            positive,
            negative,
            latent_image,
            denoise=params["denoise"],
            disable_noise=disable_noise,
            noise_mask=noise_mask,
            callback=callback,
            disable_pbar=disable_pbar,
            seed=params["seed"],
        )
        out = latent.copy()
        out.pop("downscale_ratio_spacial", None)
        out.pop("downscale_ratio_temporal", None)
        out["samples"] = samples
        return out

    def sample(self, model, job_id: str, job_root: str):
        started = time.time()
        job_dir = Path(job_root) / job_id
        job_path = job_dir / "job.json"
        result_path = job_dir / "result.json"
        try:
            manifest = read_json(job_path)
            inputs = load_inputs(job_dir / manifest["files"]["inputs"])
            params = manifest["params"]
            latent = inputs["latent"]
            positive = inputs["positive"]
            negative = inputs["negative"]
            output_latent = self.sample_with_progress(model, params, positive, negative, latent, job_dir)
            output_path = job_dir / manifest["files"]["output"]
            update_status(job_dir, stage="sampling", message="Saving output latent", overall_percent=90)
            save_output(output_path, output_latent)
            result = {
                "ok": True,
                "job_id": job_id,
                "elapsed_sec": round(time.time() - started, 3),
                "output": manifest["files"]["output"],
                "files": {
                    manifest["files"]["output"]: file_info(output_path),
                },
            }
            write_json(
                result_path,
                result,
            )
            update_status(job_dir, stage="sampling", message="Remote sampling finished", overall_percent=90)
            write_report(job_dir, result)
            return (output_latent,)
        except Exception as exc:
            error = {
                "type": type(exc).__name__,
                "message": str(exc),
                "action_hint": "Check remote ComfyUI logs, profile resources, and serialized conditioning compatibility.",
            }
            update_status(job_dir, stage="failed", message="Remote sampling failed", error=error)
            write_json(
                result_path,
                {
                    "ok": False,
                    "job_id": job_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                    "elapsed_sec": round(time.time() - started, 3),
                },
            )
            raise
