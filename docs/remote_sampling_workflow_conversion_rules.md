## Remote Sampling 工作流转换规则

### 目标
把本地 ComfyUI API prompt 中的基础采样阶段外包到远端服务器，同时保持本地负责图片输入、VAE 编码、VAE 解码和图片保存。转换后的远端侧只应运行模型加载、LoRA 加载和 `Remote_Sampling_remote`，不应包含任何图片输入或图片输出节点。

### 当前支持范围
- 支持基础 `KSampler` 转换为 `Remote_Sampling_local`。
- 支持文生图：`EmptyLatentImage -> KSampler -> VAEDecode -> SaveImage`。
- 支持图生图 clean latent：本地 `LoadImage -> VAEEncode` 后，把 latent 输入给 `Remote_Sampling_local`。
- 支持多个 `Remote_Sampling_local` 串联，后一个采样器接收前一个返回的 latent。
- 支持 profile-based 远端模型链路：
  - `UNETLoader`
  - `CLIPLoader`
  - 一个或多个 `LoraLoader`
  - `Remote_Sampling_remote`
- 支持 `--remote-profile auto` 自动推导远端 profile：
  - 从 `KSampler.model` 反向解析 `UNETLoader`。
  - 从 `LoraLoader` 或 `Lora Loader (LoraManager)` 解析 LoRA 路径与强度。
  - 从 `CLIPTextEncode.clip` 反向解析 `CLIPLoader`。
  - 生成 profile 到 `ComfyUI-Remote-Sampling\profiles\generated`。
- 支持从本地 LoRA Loader clip 链路绕回上游 `CLIPLoader`：
  - 转换脚本参数：`--bypass-local-lora-clip`
  - 目的：避免本地 `UNETLoader` 或 LoRA Loader 分支因 `CLIPTextEncode.clip` 引用而保持可达。
- 支持运行时监控与资源 preflight：
  - `status.json` 记录当前阶段、传输速度、采样 step、总耗时和错误提示。
  - `events.jsonl` 记录关键事件。
  - `remote_sampling_report.txt` 记录执行后摘要，并由 `Remote_Sampling_local` 通过 `ui.text` 返回。
  - bridge 在上传 latent 前检查远端 UNET/CLIP/LoRA 是否存在。

### 当前不支持或需人工确认的范围
- ControlNet、IPAdapter、AnimateDiff、Tiled Diffusion、区域提示词、采样 hook、自定义 sampler patch。
- 会把复杂对象塞入 `CONDITIONING` 的自定义节点，除非已用 smoke test 证明 `.pt` 序列化兼容。
- 依赖本地 `MODEL` 对象内部状态的节点。
- 需要远端读取图片文件的工作流。
- 需要远端保存、预览或后处理 RGB 图片的工作流。
- 任意前端 workflow JSON 的完整自动转换；当前转换器处理的是 ComfyUI API prompt。

### 转换脚本
脚本：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py <input_api.json> <output_api.json> --sampler-prefix <prefix>
```

默认等价于：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py <input_api.json> <output_api.json> --remote-profile auto --sampler-prefix <prefix>
```

转换器会输出 `profile_summary`，其中包含每个 KSampler 对应的远端 profile、UNET、CLIP、LoRA 数量、LoRA 名称和 `is_fixed_profile` 标记。正式转换结果应优先使用 `generated/...` profile。

固定 profile 防污染规则：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py `
  <input_api.json> `
  <output_api.json> `
  --remote-profile anima_qwen_aella_xcn
```

默认会失败，因为 `anima_qwen_aella_xcn` 会加载 Aella/xcn LoRA。只有明确需要这个固定 profile 时才允许：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py `
  <input_api.json> `
  <output_api.json> `
  --remote-profile anima_qwen_aella_xcn `
  --allow-fixed-profile
```

常用真实工作流转换命令：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py `
  F:\TieguoDun\Remote_comfyui\workflows\extracted_ComfyUI_00042\prompt.json `
  F:\TieguoDun\Remote_comfyui\workflows\runs\ComfyUI_00042_remote_sampling_converted_20260630_api.json `
  --sampler-prefix real00042 `
  --bypass-local-lora-clip
```

### 具体转换规则
#### 1. KSampler 替换
输入：

```text
KSampler(model, positive, negative, latent_image, seed, steps, cfg, sampler_name, scheduler, denoise)
```

转换为：

```text
Remote_Sampling_local(positive, negative, latent_image, seed, steps, cfg, sampler_name, scheduler, denoise, remote_profile, project_root, python_executable, timeout_sec, sampler_id)
```

处理细节：
- 删除 `model` 输入。
- 保留 `positive`、`negative`、`latent_image` 和所有采样参数。
- 补齐：
  - `remote_profile`
  - `project_root`
  - `python_executable`
  - `timeout_sec`
  - `sampler_id`

如果 `remote_profile` 为 `auto`：
- 每个 KSampler 会获得独立的 `generated/<profile_name>`。
- 无 LoRA 的原始 model 链生成无 LoRA profile。
- 有 LoRA 的原始 model 链按原顺序写入远端 profile。
- 这避免了旧版转换器把所有工作流都固定映射到 `anima_qwen_aella_xcn` 的问题。

转换后审计：

```powershell
python F:\TieguoDun\Remote_comfyui\tools\audit_remote_sampling_workflow.py --workflow <output_api.json>
```

审计工具会展开每个 `Remote_Sampling_local.remote_profile` 的 UNET、CLIP、LoRA 和 LoRA strength；如果发现 fixed profile `anima_qwen_aella_xcn`，会给出高可见 warning。

#### 2. 不可达节点裁剪
转换后从输出节点反向追踪依赖，只保留可达节点。

常见会被裁剪的节点：
- 本地 `UNETLoader`
- 本地 LoRA Loader
- 只用于提示词编辑 UI、但不被实际执行链路引用的节点

#### 3. LoRA clip 绕回
当 `CLIPTextEncode.clip` 指向本地 LoRA Loader 时，转换器可把它改回原始 `CLIPLoader`。

示例：

```text
CLIPTextEncode.clip: [LoraManager, 1] -> [CLIPLoader, 0]
```

这样本地不会为了文本编码保留本地 LoRA/model 链路。远端 LoRA 由 profile 负责加载。

### 远端 profile 规则
内置 profile 文件位置：

```text
F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\anima_qwen_aella_xcn.json
F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\anima_qwen_base.json
```

当前 profile：

```text
UNET: anima-base-v1.0.safetensors
CLIP: qwen_3_06b_base.safetensors
LoRA:
  Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors, model 1.1, clip 1.1
  Anima/画风/xcn_ogpt_v1a.safetensors, model 1.0, clip 1.0
```

自动生成 profile 位置：

```text
F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\generated
```

远端 prompt 允许节点：
- `UNETLoader`
- `CLIPLoader`
- `LoraLoader`
- `Remote_Sampling_remote`

远端 prompt 禁止节点：
- `LoadImage`
- `VAEEncode`
- `VAELoader`
- `VAEDecode`
- `PreviewImage`
- `SaveImage`

### 隐私边界
- 远端不会看到原始 RGB 输入图片文件。
- 远端不会生成或保存最终 RGB 输出图片文件。
- 远端会看到：
  - latent tensor
  - positive/negative conditioning
  - seed、steps、cfg、sampler、scheduler、denoise
  - profile 中的模型和 LoRA 配置
- clean latent 不是强隐私格式；如果远端拥有匹配 VAE，理论上可以重建近似图像。
- conditioning 包含文本语义，不能视为隐私安全内容。

### 验证要求
每个转换 workflow 至少验证：
- 本地输出图片存在。
- 本地 job 包含 `job.json`、`inputs.pt`、`output.pt`、`result.json`、`status.json`、`events.jsonl`、`remote_sampling_report.txt`。
- `job.json.remote.prompt_class_list` 不含图片节点。
- `job.json.remote.forbidden_image_nodes` 为空。
- `result.json.files.output.pt.sha256` 存在。
- `job.json.local.files.inputs.pt/output.pt/result.json` 均有 size 和 SHA256。
- `job.json.local.metrics.upload/download/sampling` 均存在。
- `status.json.sampling.step == status.json.sampling.steps`。
- 远端 job 目录不含 PNG/JPG/JPEG/WEBP。
- 远端 ComfyUI output 目录不含与该 job 匹配的图片文件。
- 不要用 `steps < 8` 的 smoke 参数判断画质；大尺寸正式测试建议 `steps=20-40`。

### 运行时监控字段
`Remote_Sampling_local` 执行时会更新本地 ComfyUI 进度条。整体进度分配：

```text
0-10%: 准备与资源 preflight
10-35%: 上传 inputs.pt
35-90%: 远端采样 step 进度
90-100%: 下载 output.pt 和结果文件
```

`status.json` 关键字段：

```text
preflight.checked / preflight.missing
upload.bytes_total / upload.bytes_done / upload.mbps
sampling.step / sampling.steps / sampling.percent / sampling.sec_per_step / sampling.eta_sec
download.bytes_total / download.bytes_done / download.mbps
error.type / error.message / error.action_hint
```

资源缺失时，preflight 必须在上传 latent 前失败。错误信息应包含缺失资源类型、profile、期望远端路径、可能本地路径和上传命令。

### 已修复问题
#### 固定 profile 污染
旧版转换器默认把所有 KSampler 都映射到 `anima_qwen_aella_xcn`，即使原始 workflow 是 base-only，也会在远端强行加载 Aella/xcn LoRA。现在默认 `--remote-profile auto`，由原始 model 链决定远端 profile；显式指定 `anima_qwen_aella_xcn` 时默认会失败，必须加 `--allow-fixed-profile` 才能作为调试流使用。

已冻结审计报告：

```text
F:\TieguoDun\Remote_comfyui\docs\reports\remote_sampling_profile_pollution_audit_20260704.md
```

该报告确认最近异常实测 job 命中了 fixed profile，并且远端 prompt 中存在两个 `LoraLoader`。

#### 3-step smoke 误用
`remote_sampling_converter_converted_20260630_1755_api.json` 是 3 步烟测流，不能用于质量判断。用户实测异常图：

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\converted_20260630_1755_00002_.png
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\converted_20260630_1755_00003_.png
```

嵌入参数显示 `1024x1960 / steps=3`，属于明显欠采样。保持同一提示词、同一尺寸、同一远端 profile，把 steps 提到 30 后输出恢复正常：

```text
F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\converted_fixed30_20260701_00001_.png
```

### 已验证样例
- 单采样器 reduced smoke：已通过。
- 图生图 clean latent smoke：已通过。
- 双 `Remote_Sampling_local` 串联：已通过。
- `ComfyUI_00042` 真实提取 workflow reduced：已通过。
- `ComfyUI_00042` 真实提取 workflow 完整尺寸 `1216x1920 / 30 steps`：已通过。
- 监控 smoke `4 steps`：已通过，job `F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260701_183734_ac924e97_monitor_smoke_500`。
- 监控正式质量流 `20 steps`：已通过，job `F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260701_184221_bdc900a2_monitor_quality20_500`。
- 缺失 LoRA preflight：已通过，job `F:\TieguoDun\Remote_comfyui\jobs\preflight_missing_ascii_lora_validation`，在上传 latent 前失败并给出上传命令提示。

### 后续扩展策略
- 如果要支持 ControlNet/IPAdapter，应先验证这些节点输出的 conditioning/control 对象能否可靠 `.pt` 序列化。
- 如果 conditioning 对象不稳定，应为对应节点设计显式中间格式。
- 如果需要更强隐私，应研究不把 clean latent 直接暴露给远端的推理方案；这超出第一版范围。
- 如果 profile 增多，应把 profile 名称、模型清单和 LoRA 清单做成可选 UI 或配置选择器。
