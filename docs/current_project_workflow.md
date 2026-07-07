# 当前项目工作流程说明

本文档说明 `ComfyUI-Remote-Sampling` 当前已经实现的工作流级远程采样流程。项目不再只是一个单独采样节点，而是由前端面板、工作流分析器、资源同步器、工作流转换器、本地采样代理节点和远端采样执行节点组成的一套综合系统。

## 1. 当前目标

系统目标是在保持隐私边界的前提下，把扩散采样阶段外包给远程 Linux 服务器：

- 本地负责：原始工作流、提示词、图片输入、VAE 编码、VAE 解码、最终图片保存、WebUI 操作。
- 远端负责：模型加载、LoRA 加载、latent 采样、latent 回传。
- 远端不应读取或保存 RGB 输入图片。
- 远端不应保存 PNG/JPG/JPEG/WEBP 输出图片。
- 模型、LoRA、自定义节点等资源需要在远端与本地保持可验证对齐。

核心链路：

```text
本地 workflow
  -> Check & Sync
  -> Convert Canvas / backend conversion
  -> ComfyUI 原生运行按钮
  -> Remote_Sampling_local 序列化 latent/conditioning/参数
  -> 远端 Remote_Sampling_remote 采样
  -> 下载 output latent
  -> 本地 VAEDecode / SaveImage
```

## 2. 日常使用流程

打开一个新的本地工作流后，推荐按以下顺序使用：

1. 确认本地工作流自身能正常运行。

   工作流转换前，本地不能缺模型、LoRA 或必要自定义节点。因为远端资源同步以本地当前可解析的工作流为基准。

2. 点击前端面板的 `Check & Sync`。

   该步骤会执行：

   - 分析当前 ComfyUI API prompt。
   - 找出采样器、UNET、CLIP、LoRA、VAE 和自定义节点依赖。
   - 检查本地资源是否存在。
   - 检查远端资源是否存在、大小是否匹配。
   - 对缺失资源执行同步。
   - 检查远端自定义节点环境。
   - 生成 run 目录、manifest、资源 diff、事件日志和报告。

3. 点击 `Convert Canvas`。

   该步骤会把当前画布中的标准采样器转换为 `Remote_Sampling_local`。视觉上应能看到采样节点发生变化。

4. 使用 ComfyUI 自带的 Queue/Run 按钮出图。

   正式出图不再使用旧的 `Run Guarded` 按钮。转换成功后，原生运行按钮会触发 `Remote_Sampling_local`，由它提交远端采样 job。

5. 查看监控信息。

   当前监控来源包括：

   - `Remote_Sampling_local` 节点内进度面板。
   - ComfyUI 进度条。
   - 节点输出的 `Remote Sampling Report` 文本。
   - 本地 job 目录中的 `status.json`、`events.jsonl`、`remote_sampling_report.txt`。
   - workflow runtime run 目录中的 `workflow_status.json`、`workflow_events.jsonl`、`workflow_runtime_report.txt`。

## 3. 前端面板职责

前端面板当前提供三个主要控件：

- `Check & Sync`

  执行工作流级检查、资源对齐和远端环境准备。

- `Convert Canvas`

  将当前画布里的支持采样器替换为 `Remote_Sampling_local`。转换后仍使用 ComfyUI 原生运行按钮。

- `Hide`

  隐藏面板。面板支持拖动，避免固定位置遮挡工作区。

当前不再把 `Run Guarded` 作为日常使用入口。它的语义已经被拆分为“检查同步”和“画布转换”，最终队列执行交还给 ComfyUI 原生按钮。

## 4. 工作流分析与资源计划

工作流分析阶段读取当前 API prompt，提取以下信息：

- 标准采样器节点，如 `KSampler`、`KSamplerAdvanced`。
- 模型加载链，如 `UNETLoader`。
- CLIP 加载链，如 `CLIPLoader`。
- LoRA 加载链，如 `LoraLoader`。
- 支持的模型 patch，例如 `ModelSamplingAuraFlow`。
- VAE 和本地输出节点。
- 自定义节点依赖。

分析结果会写入：

```text
runs/<workflow_runtime_id>/workflow_analysis.json
runs/<workflow_runtime_id>/resources_plan.json
runs/<workflow_runtime_id>/custom_nodes_plan.json
```

资源路径策略是镜像本地 `ComfyUI/models` 的相对路径。例如：

```text
本地:
ComfyUI/models/loras/Anima/画风/nnmbpx_v1_epoch22.safetensors

远端:
/home/user02/remote_ComfyUI/ComfyUI/models/loras/Anima/画风/nnmbpx_v1_epoch22.safetensors
```

这样可以避免 LoRA 管理器和手写 workflow 因相对目录不一致而找不到资源。

## 5. 资源同步

资源检查分为两层：

1. 工作流级 `Check & Sync`

   检查整个工作流依赖，并在转换前同步缺失资源。

2. 节点级 preflight

   `Remote_Sampling_local` 在上传 latent 前会再次检查远端 profile 需要的 UNET、CLIP、LoRA。资源缺失时应在上传 latent 前失败。

同步工具会优先使用流式上传脚本，以便处理较大的模型和 LoRA 文件。上传完成后会重新检查远端文件大小。对于大型文件，hash 可能采用延迟策略；关键实测中可以手动执行 SHA256 对比。

## 6. 工作流转换

转换阶段会为每个采样器生成 runtime profile，并把本地采样器替换为 `Remote_Sampling_local`。

转换后的本地 workflow 仍保留：

- 本地 CLIPTextEncode。
- 本地 EmptyLatentImage 或本地图像编码后的 latent 输入。
- 本地 VAEDecode。
- 本地 SaveImage。

远端 profile 只包含采样所需部分：

- UNETLoader。
- CLIPLoader。
- LoRA 加载节点。
- 支持的 model patch。
- Remote_Sampling_remote。

每次运行生成的 job 都会记录：

```text
local_prompt_sha256
profile_sha256
remote_prompt_sha256
remote_prompt_rebuilt_per_job
```

这些字段用于确认远端采样 prompt 是从当前本地 workflow 派生，而不是复用旧 workflow。

## 7. 远程采样 job 生命周期

一次 `Remote_Sampling_local` 执行会创建本地 job 目录：

```text
jobs/remote_sampling_<timestamp>_<id>_<sampler_id>/
```

典型文件：

```text
job.json
inputs.pt
output.pt
result.json
status.json
events.jsonl
remote_sampling_report.txt
```

执行流程：

1. 读取本地 positive、negative、latent 和采样参数。
2. 创建 `job.json` 和 `inputs.pt`。
3. 执行远端资源 preflight。
4. 上传 job manifest、status 和 latent/conditioning 输入。
5. 获取远端采样服务锁。
6. 启动或复用远端 ComfyUI 临时进程。
7. 上传远端 latent-only prompt。
8. 远端执行 `Remote_Sampling_remote`。
9. 远端写出 `output.pt` 和 `result.json`。
10. 本地下载 output latent。
11. 本地 workflow 继续执行 VAEDecode 和 SaveImage。

## 8. 监控数据

`status.json` 中重点字段：

```text
stage
message
overall_percent
preflight
upload
sampling
download
total_elapsed_sec
error
```

采样进度字段：

```text
sampling.step
sampling.steps
sampling.percent
sampling.elapsed_sec
sampling.sec_per_step
sampling.eta_sec
```

上传和下载字段：

```text
bytes
bytes_done
bytes_total
percent
elapsed_sec
mbps
```

当前 UI 会显示上传、采样、下载和总耗时。更详细审计应查看 job 目录中的 JSON 和报告文件。

## 9. 隐私边界

当前实现约束：

- 远端 job 输入是 latent、conditioning 和采样参数。
- 远端 job 输出是 output latent。
- 远端不执行 `VAEDecode`。
- 远端不执行 `PreviewImage`。
- 远端不执行 `SaveImage`。
- 远端 job 目录不应出现 PNG/JPG/JPEG/WEBP。
- 远端 `ComfyUI/output` 不应出现与远程采样 job 相关的图片。

验证命令示例：

```bash
find /home/user02/remote_ComfyUI/jobs/<job_id> -type f \
  \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.webp" \) -print
```

## 10. 已知限制

1. 采样器等价性不是对所有采样器都已验证。

   已验证 `euler + normal` 在 anima 测试中可获得本地/远端视觉一致结果。`seeds_2 + simple` 在实测中出现本地/远端同 seed 结果不一致，因此系统会给出采样器等价性 warning。

2. 远端连接稳定性依赖 SSH 隧道。

   当前对 job SFTP 上传和下载做了重连与重试，但工作流级资源检查仍可能受到 `server_exec.py` 临时 tunnel 启动失败影响。

3. 自定义节点同步还处于保守阶段。

   当前优先打包传输本地 custom node。Linux 依赖安装失败时，后续需要更完善的 ComfyUI Manager fallback。

4. 前端面板是项目级入口，不是 ComfyUI 官方原生工作流状态系统。

   复杂状态仍应以 `runs/` 和 `jobs/` 目录中的 JSON 报告为准。

5. Windows 控制台编码可能造成中文路径显示异常。

   例如 `画风` 在某些 PowerShell 或 SSH 输出中可能显示为乱码。实际 JSON 和远端文件系统应以 UTF-8/Unicode escape 校验为准。

## 11. 推荐排障顺序

如果出图失败：

1. 查看 `Remote_Sampling_local` 节点输出的 report。
2. 查看最新 `jobs/<job_id>/status.json`。
3. 查看最新 `jobs/<job_id>/remote_sampling_report.txt`。
4. 查看最新 `runs/<workflow_runtime_id>/workflow_status.json`。
5. 确认远端资源是否存在且大小匹配。
6. 确认采样器是否为已验证组合。
7. 确认远端无残留锁：

```bash
find /home/user02/remote_ComfyUI/locks -maxdepth 2 -print
```

8. 确认远端 ComfyUI 临时进程是否残留：

```bash
ps -eo pid,ppid,etime,cmd | grep -E "ComfyUI/main.py|remote_submit_prompt" | grep -v grep
```

## 12. 后续升级方向

优先级较高的下一步：

1. 把资源检查、资源上传和 custom node 检查统一到一个更稳定的 SSH session 管理器中，减少 `server_exec.py` 临时 tunnel 失败。
2. 对 `euler`、`dpmpp`、`res_multistep`、`seeds_2` 等采样器建立本地/远端等价性测试矩阵。
3. 增加一键“转换前本地 dry-run”检查，确认原始本地 workflow 本身可执行。
4. 增加资源 hash 策略配置：小文件默认 SHA256，大文件可按需 SHA256。
5. 为前端面板增加运行历史、最新 job 快捷入口和错误摘要复制按钮。
6. 为自定义节点同步增加 Linux 依赖检测和 ComfyUI Manager fallback。
