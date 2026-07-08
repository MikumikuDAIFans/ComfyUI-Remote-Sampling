# Install

This project is a workflow-level ComfyUI plugin. It uses a local ComfyUI instance for workflow editing, image input, VAE encode/decode and final image output, and a remote Linux ComfyUI instance for latent sampling.

## Requirements

- Local ComfyUI running on Windows or Linux.
- Remote Linux server with GPU, Python, Git and a working ComfyUI checkout.
- SSH access from local machine to the remote server.
- Local and remote model directories should mirror the same relative layout under `ComfyUI/models`.

The remote server must not need RGB input/output files for remote sampling jobs. The intended data path is latent upload, latent sampling, latent download.

## Local Plugin Install

Copy or clone this repository, then install the custom node package into local ComfyUI:

```powershell
cd F:\path\to\ComfyUI\custom_nodes
git clone https://github.com/MikumikuDAIFans/ComfyUI-Remote-Sampling.git
```

If you are developing from a separate project checkout, copy the `ComfyUI-Remote-Sampling` folder into local `ComfyUI/custom_nodes`.

Restart local ComfyUI and confirm these nodes exist in `/object_info`:

- `Remote_Sampling_local`
- `Remote_Sampling_remote`

## Remote Plugin Install

Install the same `ComfyUI-Remote-Sampling` folder under remote:

```bash
cd /home/user/remote_ComfyUI/ComfyUI/custom_nodes
git clone https://github.com/MikumikuDAIFans/ComfyUI-Remote-Sampling.git
```

The remote ComfyUI environment must be able to import the package. Use the same Python environment that runs remote ComfyUI.

## Configure Paths

Copy `.env.example` to `.env`, or export equivalent variables in your shell.

Important values:

- `REMOTE_SAMPLING_PROJECT_ROOT`: local project checkout.
- `REMOTE_SAMPLING_BRIDGE_PYTHON`: local Python used by the bridge CLI.
- `REMOTE_SAMPLING_SERVER_EXEC`: command executor used to run remote commands.
- `REMOTE_SAMPLING_REMOTE_BASE`: remote workspace root, for example `/home/user/remote_ComfyUI`.
- `REMOTE_SAMPLING_REMOTE_PYTHON`: remote ComfyUI Python interpreter.
- `REMOTE_SAMPLING_LOCAL_COMFY_ROOT`: local ComfyUI root.
- `REMOTE_SAMPLING_LOCAL_COMFY_MODELS`: local `ComfyUI/models`.
- `REMOTE_SAMPLING_REMOTE_CUSTOM_NODES_ROOT`: remote `ComfyUI/custom_nodes`.

For a generic SSH server, use:

```text
REMOTE_SAMPLING_SERVER_EXEC=F:\path\to\Remote_comfyui\tools\generic_ssh_exec.py
REMOTE_SAMPLING_SSH_TARGET=user@example.com
REMOTE_SAMPLING_SSH_PORT=22
REMOTE_SAMPLING_SSH_KEY=C:\path\to\id_ed25519
```

## Daily Workflow

1. Open a normal local workflow in ComfyUI.
2. Confirm the local workflow has no missing local model/LoRA/custom-node resources.
3. In the floating `Remote Workflow Runtime` panel, click `Check & Sync`.
4. Click `Convert Canvas`.
5. Confirm supported `KSampler` nodes were replaced by `Remote_Sampling_local`.
6. Click ComfyUI's native Queue/Run button.
7. Watch workflow-level diagnostics in `Recent Runs` and sampling progress in the node panel.

Do not use old converted workflow files as the normal entry. Convert from the current canvas whenever the workflow changes.

## Validation

Run local tests from the project root:

```powershell
python -m py_compile ComfyUI-Remote-Sampling\workflow_runtime.py
python -m unittest discover -s tests -p test_*.py -v
```

For a remote privacy check, inspect the latest remote job directory and remote `ComfyUI/output`. Remote sampling jobs should not create `png`, `jpg`, `jpeg` or `webp` files.
