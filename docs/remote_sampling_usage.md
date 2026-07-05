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

4. 推荐正式入口：在本地 ComfyUI 打开原始 workflow 后，优先使用 `Remote Workflow Runtime` 面板。

可用按钮：

- `Plan Current Workflow`：只分析当前画布，生成 `workflow_analysis.json`、`resources_plan.json`、`custom_nodes_plan.json`，不排队。
- `Convert`：从当前画布重新生成本次专属 `converted_local_prompt.json` 和 `remote_execution_plan.json`，不排队。
- `Run Guarded`：先创建 workflow-level plan 并显示准备阶段进度；随后执行远端资源检查/同步、自定义节点检查/同步、依赖安装计划、远端 `object_info` import smoke，再从当前画布重新转换；全部通过后把 converted prompt 提交到 ComfyUI 队列。

旧的 `Remote Sampling` 面板 `Run Current Workflow` 仍保留为兼容入口，但后续正式能力会优先落在 `Remote Workflow Runtime`。

5. `Run Guarded` 每次运行都会生成新的 workflow-level run bundle：

```text
F:\TieguoDun\Remote_comfyui\runs\workflow_runtime_<timestamp>_<id>
```

bundle 中包含：

```text
source_prompt.json
source_workflow.json
workflow_analysis.json
resources_plan.json
custom_nodes_plan.json
converted_local_prompt.json
remote_execution_plan.json
resources_diff.json
remote_environment_report.json
remote_custom_node_dependency_install.json
remote_custom_node_import_smoke.json
workflow_status.json
workflow_events.jsonl
workflow_runtime_report.txt
manifest.json
```

`Run Guarded` 前端会轮询：

```text
/remote_workflow/runtime/run_status?run_id=<workflow_runtime_run_id>
```

因此资源检查、资源同步、自定义节点同步、依赖计划、import smoke、转换和 queue-ready 等阶段可以在面板中实时或准实时看到，而不需要等后端请求完全结束后再刷新。

`run_id` 复用规则：

- `Run Guarded` 会把本次 plan 绑定到当前 source prompt/workflow hash。
- 如果脚本或前端复用旧 `run_id`，但又传入不同的当前 workflow/prompt，后端会在 `local_preflight` 以 `SourcePromptHashMismatch` 或 `SourceWorkflowHashMismatch` 失败。
- 这类失败发生在远端资源检查、workflow conversion、latent 上传和远端采样之前。
- 当前画布发生实质变化后，应重新执行 `Plan Current Workflow` 或直接重新 `Run Guarded`，不要复用旧 run bundle。

随后底层 remote sampling node 仍会生成 job bundle：

```text
F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_<timestamp>_<id>_<sampler_id>
```

其中 `status.json`、`events.jsonl`、`job.json.local.metrics` 记录上传、采样、下载和总耗时。

依赖安装说明：

- 默认只生成 `remote_custom_node_dependency_install.json`，不会自动联网 `pip install`。
- 如确实需要执行依赖安装，必须由操作者明确允许，例如在后端 payload 中设置 `allow_remote_dependency_install: true`，或手动运行 `tools/install_remote_custom_node_dependencies.py --execute`。
- 如果依赖未安装导致远端 `object_info` 缺少节点 class，`Run Guarded` 会在上传 latent 前失败。

兼容入口会从当前画布生成 API prompt，调用本地 `/remote_sampling/convert`，即时转换并审计，然后把 converted prompt 提交到 ComfyUI 队列。每次运行都会生成旧格式 run bundle：

```text
F:\TieguoDun\Remote_comfyui\runs\runtime_<timestamp>_<id>
```

bundle 中包含：

```text
source_prompt.json
source_workflow.json
converted_prompt.json
profiles\<node>_<profile>.json
manifest.json
audit.json
audit.txt
```

`manifest.json` 会记录 `source_prompt_sha256`、`converted_prompt_sha256`、profile snapshot SHA256、转换器版本和策略版本。正式运行不再建议手动打开历史 `workflows\runs\*.json`。

缓存策略：当前版本默认每次运行重新转换。后续如果启用缓存，cache key 必须至少包含 source prompt SHA256、converter version、policy version、custom node version 和 model/LoRA chain summary hash；任何字段不一致都必须重新转换。

6. 手写或调试时，也可以在本地 workflow 中直接使用 `Remote_Sampling_local` 替代普通 `KSampler`。

手写调试时常用参数：

```text
remote_profile: anima_qwen_aella_xcn
project_root: F:\TieguoDun\Remote_comfyui
python_executable: C:\Python314\python.exe
timeout_sec: 3600
```

注意：`anima_qwen_aella_xcn` 是固定调试 profile，会加载 Aella 角色 LoRA 和 xcn 画风 LoRA。正式把本地 workflow 转为远端采样时，不要手工套用这个 profile，除非原始本地 workflow 本来就应使用同一组 LoRA。

节点运行时也会保护你：`Remote_Sampling_local` 默认拒绝 `anima_qwen_aella_xcn` 这类 fixed profile，旧 workflow 会在上传 latent 前失败。只有确认本次运行确实要使用这个固定 profile 时，才把节点的 `allow_fixed_profile` 设为 `true`。

7. 结束后停止远端服务：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py stop
```

### 转换已有 API workflow
日常优先使用前端 `Run Current Workflow`。下面的 CLI 仍保留给调试、批处理和回归验证。

基础转换：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py <input_api.json> <output_api.json> --sampler-prefix <prefix>
```

默认 `--remote-profile auto` 会从原 workflow 的 `KSampler.model` 链自动生成远端 profile：
- 原 workflow 没有 LoRA 时，远端 profile 也不会加载 LoRA。
- 原 workflow 使用 `LoraLoader` 或 `Lora Loader (LoraManager)` 时，会把激活 LoRA、模型强度、CLIP 强度写入 `ComfyUI-Remote-Sampling\profiles\generated\*.json`。
- 不再建议对转换脚本手动指定固定 profile，除非你明确知道该 workflow 应该套用哪组远端模型/LoRA。
- 如果显式指定 `--remote-profile anima_qwen_aella_xcn`，转换器默认会拒绝，以避免无 LoRA workflow 被污染。只有调试或演示时确认需要该固定 profile，才加 `--allow-fixed-profile`。
- 自动生成的 profile 会记录 `conversion_source.source_prompt_sha256`，用于追踪它来自哪一次本地 API prompt。

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

转换后建议立即审计：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\audit_remote_sampling_workflow.py --workflow <output_api.json>
```

审计输出应确认：
- base-only workflow: `LoRA: none`，远端 prompt 不应含 `LoraLoader`。
- LoRA workflow: LoRA 清单和强度必须与原始本地 model 链一致。
- 如果出现 `fixed profile anima_qwen_aella_xcn` warning，不要把它当作资源等价验证结果。

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
runtime_alignment.local_prompt_sha256
runtime_alignment.profile_sha256
runtime_alignment.remote_prompt_sha256
runtime_alignment.remote_prompt_rebuilt_per_job
```

可以用审计工具检查任意 job：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\audit_remote_sampling_workflow.py --job F:\TieguoDun\Remote_comfyui\jobs\<job_dir>
```

它会展开 `remote_profile`、UNET、CLIP、LoRA、LoRA strength、远端 prompt class list、是否存在 forbidden image nodes，以及 fixed profile 污染 warning。

也可以审计 runtime run bundle：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\audit_remote_sampling_workflow.py --bundle F:\TieguoDun\Remote_comfyui\runs\<runtime_run_dir>
```

`runtime_alignment` 字段用于证明本次运行的对齐关系：
- `local_prompt_sha256`: 本次本地 ComfyUI prompt 的指纹。
- `profile_sha256`: 本次使用的 profile 文件指纹。
- `remote_prompt_sha256`: 本次重新生成并上传到远端的 latent-only prompt 指纹。
- `remote_prompt_rebuilt_per_job: true`: 远端 prompt 不是复用旧文件，而是每个 job 重新生成。
- `runtime_bundle_id` / `runtime_bundle_dir`: 本次 job 对应的运行时转换 bundle。

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

`Remote_Sampling_local` 节点内置实时面板。执行中可以直接在节点内部看到：

```text
overall progress
preflight / upload / sampling / download progress
upload speed
remote sampling step / elapsed / sec_per_step
download speed
total elapsed
```

面板由 `ComfyUI-Remote-Sampling/web/remote_sampling_panel.js` 提供，ComfyUI 重启后会通过 `WEB_DIRECTORY` 自动加载。面板会同时接收 websocket progress 事件，并每秒通过本地 `/remote_sampling/status` 读取 `jobs/<job>/status.json` 作为兜底刷新来源；因此即使右侧详情面板没有重新点击，画布节点内的进度也应持续更新。

当前 ComfyUI 前端对 canvas custom widget 存在缓存行为，扩展会在状态更新时对节点尺寸做约 1px 的不可感知刷新，以强制画布重绘。后端仍会保留原有审计文件；执行完成后也会通过 ComfyUI `ui.text` 返回 `remote_sampling_report.txt` 的摘要。如果前端没有显示该文本，可直接打开 job 目录中的 report 文件。

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
