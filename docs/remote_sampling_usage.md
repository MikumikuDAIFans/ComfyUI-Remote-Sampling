## Remote Sampling 使用说明

### 日常使用流程
1. 启动远端 ComfyUI 采样服务：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py start
```

2. 确认远端服务状态：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py status
```

期望结果：
- `tmux_running: true`
- `api_ready: true`
- `has_remote_sampling_remote: true`
- 监听地址只应是 `127.0.0.1:8197`

3. 打开本地 ComfyUI：

```text
http://127.0.0.1:8188
```

本地 `8188` 已验证可以加载：

```text
Remote_Sampling_local
```

4. 在本地 workflow 中使用 `Remote_Sampling_local` 替代普通 `KSampler`。

常用参数：

```text
remote_profile: anima_qwen_aella_xcn
project_root: F:\TieguoDun\Remote_comfyui
python_executable: C:\Python314\python.exe
timeout_sec: 3600
```

5. 结束后停止远端服务：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py stop
```

### 转换已有 API workflow
基础转换：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py <input_api.json> <output_api.json> --sampler-prefix <prefix>
```

默认 `--remote-profile auto` 会从原 workflow 的 `KSampler.model` 链自动生成远端 profile：
- 原 workflow 没有 LoRA 时，远端 profile 也不会加载 LoRA。
- 原 workflow 使用 `LoraLoader` 或 `Lora Loader (LoraManager)` 时，会把激活 LoRA、模型强度、CLIP 强度写入 `ComfyUI-Remote-Sampling\profiles\generated\*.json`。
- 不再建议对转换脚本手动指定固定 profile，除非你明确知道该 workflow 应该套用哪组远端模型/LoRA。

如果原 workflow 的 `CLIPTextEncode.clip` 来自 LoRA Loader 或 LoRA Manager，使用：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py <input_api.json> <output_api.json> --sampler-prefix <prefix> --bypass-local-lora-clip
```

已验证样例：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py `
  F:\TieguoDun\Remote_comfyui\workflows\extracted_ComfyUI_00042\prompt.json `
  F:\TieguoDun\Remote_comfyui\workflows\runs\ComfyUI_00042_remote_sampling_converted_20260630_api.json `
  --sampler-prefix real00042 `
  --bypass-local-lora-clip
```

### 当前 profile
内置 Profile 文件：

```text
F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\anima_qwen_aella_xcn.json
F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\anima_qwen_base.json
```

`anima_qwen_aella_xcn` 远端模型链路：

```text
UNET: anima-base-v1.0.safetensors
CLIP: qwen_3_06b_base.safetensors
LoRA:
  Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors
  Anima/画风/xcn_ogpt_v1a.safetensors
```

`anima_qwen_base` 只加载 base UNET 和 CLIP，不加载 LoRA。

自动生成的 profile 位于：

```text
F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\generated
```

### 质量参数注意
不要用 smoke workflow 判断画质。已经确认：
- `workflows\runs\remote_sampling_converter_converted_20260630_1755_api.json` 是 3-step 烟测流，只用于验证链路。
- 在 `1024x1960` 这类大尺寸下，`steps=3` 会明显欠采样，表现为过曝、色块异常、结构混乱。
- 正式质量测试建议 `steps=20-40`；当前 Anima/Qwen/Aella/xcn 实测 `steps=30` 正常。

本次问题复现与修复验证：

```text
异常输入:
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\converted_20260630_1755_00003_.png

修正版 workflow:
F:\TieguoDun\Remote_comfyui\workflows\runs\converted_00003_fixed_steps30_20260701_api.json

修正版输出:
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\converted_fixed30_20260701_00001_.png
```

### 验证远端没有图片输出
每次测试后可以检查：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py status
```

并检查远端 job：

```text
/home/user02/remote_ComfyUI/jobs/<job_id>
```

期望只包含：

```text
job.json
inputs.pt
output.pt
result.json
```

不应出现：

```text
*.png
*.jpg
*.jpeg
*.webp
```

### Job 审计字段
每个新 job 的 `job.json` 会记录：

```text
profile.name
profile.unet
profile.clip
profile.loras
remote.job_dir
remote.prompt
remote.prompt_class_list
remote.forbidden_image_nodes
local.files.inputs.pt.sha256
local.files.output.pt.sha256
local.files.result.json.sha256
local.metrics.preflight
local.metrics.upload
local.metrics.sampling
local.metrics.download
```

`result.json` 会记录：

```text
files.output.pt.size
files.output.pt.sha256
```

每个新 job 还会生成：

```text
status.json
events.jsonl
remote_sampling_report.txt
```

`status.json` 是当前状态快照，常用字段：

```text
stage
message
overall_percent
total_elapsed_sec
preflight.checked / preflight.missing
upload.bytes_total / upload.bytes_done / upload.mbps
sampling.step / sampling.steps / sampling.percent / sampling.sec_per_step / sampling.eta_sec
download.bytes_total / download.bytes_done / download.mbps
error.type / error.message / error.action_hint
```

`Remote_Sampling_local` 执行完成后会通过 ComfyUI `ui.text` 返回 `remote_sampling_report.txt` 的摘要；如果前端没有显示该文本，可直接打开 job 目录中的 report 文件。

### 资源 preflight
`remote_sampling_job_cli.py` 默认会在上传 `inputs.pt` 前检查远端资源。检查范围来自当前 `remote_profile`：

```text
UNET -> /home/user02/remote_ComfyUI/ComfyUI/models/diffusion_models 或 models/unet
CLIP -> /home/user02/remote_ComfyUI/ComfyUI/models/clip
LoRA -> /home/user02/remote_ComfyUI/ComfyUI/models/loras
```

如果资源缺失，任务会在上传 latent 前失败，并给出可执行提示，例如：

```text
Missing remote lora: Anima/missing/__missing_preflight_validation__.safetensors
expected: /home/user02/remote_ComfyUI/ComfyUI/models/loras/Anima/missing/__missing_preflight_validation__.safetensors
local: F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\models\loras\Anima\missing\__missing_preflight_validation__.safetensors
upload: python F:\TieguoDun\Remote_comfyui\tools\upload_to_company_server.py "local=remote"
```

紧急调试时 bridge 支持 `--skip-preflight`，但日常不建议关闭。

### 已验证输出
本地 `8188` smoke：

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\g2_8188_smoke_20260701_00001_.png
```

真实 workflow 完整尺寸：

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\real00042_full_20260701_00001_.png
```

最终审计 smoke：

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\g4_audit_final_20260701_00001_.png
```

监控 smoke：

```text
Workflow: F:\TieguoDun\Remote_comfyui\workflows\runs\remote_sampling_monitor_smoke_20260701_api.json
Job: F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260701_183734_ac924e97_monitor_smoke_500
Output: F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\monitor_smoke_20260701_00001_.png
```

监控正式质量流：

```text
Workflow: F:\TieguoDun\Remote_comfyui\workflows\runs\remote_sampling_monitor_quality20_20260701_api.json
Job: F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260701_184221_bdc900a2_monitor_quality20_500
Output: F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\monitor_quality20_20260701_00001_.png
```

资源缺失 preflight 验证：

```text
Profile: F:\TieguoDun\Remote_comfyui\workflows\runs\missing_ascii_lora_preflight_profile.json
Job: F:\TieguoDun\Remote_comfyui\jobs\preflight_missing_ascii_lora_validation
Result: failed before latent upload with RemoteResourceMissing and upload command hint
```

### 隐私边界
当前方案可以做到：
- 远端不读取原始输入图片文件。
- 远端不生成最终输出图片文件。
- 远端只处理 latent、conditioning 和采样参数。

当前方案不能保证：
- clean latent 不可逆。
- conditioning 不泄露文本语义。
- 复杂自定义 conditioning 节点一定能跨机器序列化。

### 常见故障
#### 本地节点不可见
检查：

```powershell
python - <<'PY'
import json, urllib.request
data=json.loads(urllib.request.urlopen('http://127.0.0.1:8188/object_info').read().decode())
print('Remote_Sampling_local' in data)
PY
```

如果是 `False`，重启本地 ComfyUI。

#### 远端节点不可见
检查：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py status
```

如果 `has_remote_sampling_remote` 是 `false`，重启远端服务：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py stop
python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py start
```

#### 查看远端日志

```powershell
python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py logs --lines 120
```
