## 计划元数据
- Plan ID: remote-sampling-monitoring-and-resource-preflight
- Version: v2
- Last updated: 2026-07-01 18:55 +08:00
- Canonical progress file: `F:\TieguoDun\Remote_comfyui\remote_sampling_monitoring_task_book.md`
- Related handoff file: `F:\TieguoDun\Remote_comfyui\plan.md`
- Current branch: not applicable
- Current active phase: Phase 6: 回归验证与文档固化
- Execution readiness: executing

## 目标
为 `ComfyUI-Remote-Sampling` 自定义节点增加可观测监控与资源对齐校验能力，使用户在本地执行 `Remote_Sampling_local` 时能够明确看到远端采样任务处于哪个阶段、latent 上传/下载是否成功及网速、远端采样百分比与耗时、总耗时；同时在模型或 LoRA 资源未对齐时，给出明确、可执行的报错与补齐提示，避免静默生成错误图片。

最终目标是让远端仍只负责 latent/conditioning 采样，不接触 RGB 输入/输出图片；监控和校验不得破坏当前已验证的远程采样隐私边界。

## 范围与约束
- In scope:
  - 为 remote sampling job 增加 `status.json` 和可选 `events.jsonl` 状态协议。
  - 记录并展示 latent/input 上传速度、output latent 下载速度、远端采样 step 进度、采样耗时、总耗时。
  - 将本地 bridge 从一次性 `capture_output` 升级为可流式解析进度事件的执行方式。
  - 远端 `Remote_Sampling_remote` 改为可回调采样进度的实现路径。
  - 增加资源 preflight，检查远端 profile 声明的 UNET、CLIP、LoRA 是否存在，并对缺失资源给出本地路径、远端路径、上传命令建议。
  - 保持现有 `Remote_Sampling_local` 第一个输出仍为 `LATENT`，避免破坏已有工作流。
  - 第一阶段使用 ComfyUI 原生进度条和 job report；后续增加前端 JS，把状态显示在 `Remote_Sampling_local` 节点面板中。
- Out of scope:
  - 不在本任务中实现强隐私加密推理或防 latent 反推方案。
  - 不在本任务中支持任意复杂 custom conditioning 的跨机器序列化。
  - 不在本任务中让远端读取/保存 RGB 图片。
  - 不在本任务中强制镜像同步整个本地 ComfyUI 模型目录；只校验当前 profile/采样器实际需要的资源。
  - 不在第一阶段修改 ComfyUI 核心源码。
- Constraints:
  - 远端操作范围限定在 `/home/user02/remote_ComfyUI` 内。
  - 连接远端必须使用 `company-lab-2-server` 技能既有脚本和密码认证策略。
  - 现有已验证工作流必须继续可运行：文生图、图生图 clean latent、双采样器串联、`ComfyUI_00042` 完整尺寸。
  - 远端 job 目录仍不得出现 PNG/JPG/JPEG/WEBP。
  - `status.json` 写入必须低频、轻量，不能明显拖慢采样。
  - 出错信息必须面向人类可操作，不能只抛 Python traceback。

## 执行阶段
### Phase 1: 状态协议与可观测性基线
- Purpose: 定义稳定的 job 状态数据结构，让本地、bridge、远端可以用同一套字段描述进度、耗时、速度和错误。
- Outputs:
  - `ComfyUI-Remote-Sampling\protocol.py` 增加 status/event helper。
  - job 目录新增 `status.json` 当前状态文件。
  - 可选新增 `events.jsonl` 事件流水文件，用于调试和事后审计。
  - 文档记录状态字段规范。
- Completion criteria:
  - 每个 job 至少能记录 `stage`、`created_at`、`updated_at`、`total_elapsed_sec`。
  - 支持阶段值：`preparing`、`uploading`、`queued`、`sampling`、`downloading`、`completed`、`failed`。
  - 状态文件在失败时也能写入 `error.type`、`error.message`、`error.action_hint`。
- Validation:
  - 本地运行一个不连接远端的 status helper 单元 smoke，确认 JSON 可读写。
  - 执行一次最小 remote sampling job，确认本地 job 目录和远端 job 目录均有可读的 `status.json`。
- Evidence:
  - `F:\TieguoDun\Remote_comfyui\jobs\<job_id>\status.json`
  - `/home/user02/remote_ComfyUI/jobs/<job_id>/status.json`
  - 更新后的 `remote_sampling_usage.md` 状态字段说明。

### Phase 2: 本地传输监控与整体进度条
- Purpose: 让 `Remote_Sampling_local` 在本地显示 latent 发送、等待远端、latent 接收的整体进度，并记录上传/下载速度。
- Outputs:
  - `remote_sampling_job_cli.py` 的 upload/download 增加进度回调和速度统计。
  - bridge stdout 输出机器可解析的进度事件，例如 `RS_PROGRESS {json}`。
  - `remote_sampling_local.py` 从 `capture_output` 改为流式读取 bridge stdout，并用 `comfy.utils.ProgressBar` 更新本地进度。
  - job 结束后写入 `job.json.local.metrics`。
- Completion criteria:
  - 上传阶段能记录 `bytes_total`、`bytes_done`、`elapsed_sec`、`mbps`。
  - 下载阶段能记录 `bytes_total`、`bytes_done`、`elapsed_sec`、`mbps`。
  - 本地进度条至少覆盖 `0-35%` 上传前后和 `90-100%` 下载完成。
  - 原有 `LATENT` 输出兼容，不破坏已有 workflow。
- Validation:
  - 使用 `remote_sampling_g2_8188_smoke` 级别的最小 workflow 验证本地节点能完成。
  - 检查 `job.json.local.metrics.upload` 和 `job.json.local.metrics.download` 字段。
  - 人工观察 ComfyUI 前端执行时有整体进度条变化。
- Evidence:
  - 新 job 的 `job.json.local.metrics`。
  - 本地输出图仍生成成功。
  - 远端 job 目录无图片文件。

### Phase 3: 远端采样 step 进度
- Purpose: 获取真正的远端采样百分比、采样耗时、单步耗时和 ETA，而不是只知道远端任务正在运行。
- Outputs:
  - `Remote_Sampling_remote` 从 `nodes.common_ksampler(...)` 改为等价的 `comfy.sample.sample(..., callback=...)` 采样路径。
  - callback 每步更新远端 `status.json.sampling`。
  - bridge 在等待远端 `/history` 时轮询远端 `status.json`，把采样进度转发给本地节点。
- Completion criteria:
  - 远端采样状态包含 `step`、`steps`、`percent`、`elapsed_sec`、`sec_per_step`、`eta_sec`。
  - 本地进度条 `35-90%` 随远端 step 推进。
  - 采样失败时能把远端错误写入 `status.json` 并回传给本地。
  - 输出 latent 与旧实现保持合理一致；至少同 seed、同参数下图像结构正常，不出现采样路径退化。
- Validation:
  - 最小 4-step workflow 可观察到 step 1/4 至 step 4/4。
  - 30-step workflow 可观察到多个中间进度更新。
  - 与旧版 `real00042_full` 同类任务对比，输出质量正常。
- Evidence:
  - `status.json.sampling` 完整字段。
  - bridge stdout 中的 `RS_PROGRESS` 采样事件。
  - 本地完成图片与 job 审计。

### Phase 4: 资源 preflight 与人类可执行报错
- Purpose: 在真正上传 latent 和启动采样前确认远端资源与当前 profile 逻辑对齐，避免 LoRA 缺失或 profile 漂移导致静默错误。
- Outputs:
  - `remote_sampling_job_cli.py` 增加 `preflight_remote_resources(...)`。
  - 检查 profile 中声明的 UNET、CLIP、LoRA 路径是否存在于远端 ComfyUI models 目录。
  - 可选检查 size/SHA256：优先读取已知本地文件并与远端文件比较；缺 hash 时至少检查存在性和大小。
  - 缺失时输出明确错误和上传建议。
- Completion criteria:
  - 远端缺 LoRA 时，任务在上传 latent 前失败。
  - 错误信息包含：缺失资源类型、profile 名称、期望远端路径、可能的本地路径、建议上传命令。
  - 若远端 profile 只声明 2 个 LoRA，而原 workflow 自动 profile 应有 3 个 LoRA，转换或 preflight 能标记 profile mismatch，而不是静默运行。
  - preflight 可通过参数关闭，仅用于紧急调试；默认开启。
- Validation:
  - 构造一个缺失 LoRA profile，确认报错可读且不会上传 latent。
  - 构造一个正常 profile，确认 preflight 通过并能正常采样。
  - 检查失败 job 的 `status.json.stage = failed` 且有 `action_hint`。
- Evidence:
  - 缺失资源失败样例 job。
  - 正常资源通过样例 job。
  - 文档中的错误示例和补齐命令模板。

### Phase 5: 节点面板显示与执行后报告
- Purpose: 把监控信息从日志/进度条提升到用户可直接查看的 `Remote_Sampling_local` 节点体验。
- Outputs:
  - 第一层：执行后生成 `remote_sampling_report` 文本，记录阶段耗时、传输速度、采样速度、总耗时。
  - 第二层：前端 JS extension，在 `Remote_Sampling_local` 节点面板显示最后一次 job 的状态摘要。
  - 可选新增 `Remote_Sampling_Report_Viewer` 节点，用于读取 job report 并在 ComfyUI 中显示。
- Completion criteria:
  - 不破坏 `Remote_Sampling_local` 现有第一个 `LATENT` 输出。
  - 前端面板至少显示：当前阶段、上传 MB/s、采样 step/steps、采样百分比、下载 MB/s、总耗时、最后错误。
  - 没有前端 JS 时，仍能通过 progress bar、日志和 report 完成监控。
- Validation:
  - 本地 8188 启动后确认 `Remote_Sampling_local` 节点面板可见状态摘要。
  - 执行成功 job 后状态显示 `completed` 和总耗时。
  - 执行资源缺失 job 后状态显示 `failed` 和补齐提示。
- Evidence:
  - 节点截图或人工确认记录。
  - `remote_sampling_report` 示例。
  - 更新后的 `remote_sampling_usage.md`。

### Phase 6: 回归验证与文档固化
- Purpose: 确保监控和 preflight 没有破坏当前已证明可行的远程采样核心路径，并把使用方式固化给后续会话。
- Outputs:
  - 更新 `plan.md`、`remote_sampling_usage.md`、`remote_sampling_workflow_conversion_rules.md`。
  - 完成 smoke、img2img、dual sampler、真实 `ComfyUI_00042` reduced/full 至少一组代表性回归。
  - 同步本地和远端 custom node 包。
- Completion criteria:
  - 所有代表性 workflow 均成功。
  - 每个新 job 都有 status/report/metrics。
  - 远端 job 和 output 目录仍无图片文件。
  - 远端服务状态可正常 start/status/stop。
- Validation:
  - 本地 API 提交至少 2 条工作流：一个低步数 smoke，一个 20-30 step 正式质量流。
  - 远端命令检查 job 目录图片文件为 0。
  - 检查本地输出图片存在且视觉正常。
- Evidence:
  - 回归 workflow 路径。
  - 本地输出图片路径。
  - 远端 job 路径。
  - 文档更新记录。

## 决策记录
- Verified facts:
  - 当前远程采样链路已能运行，且远端不保存 RGB 输出图片。
  - 当前 `Remote_Sampling_remote` 调用 `nodes.common_ksampler(...)`，该路径不直接向我们的节点暴露逐 step 回调。
  - ComfyUI 提供 `comfy.utils.ProgressBar`，可用于节点执行期间的本地进度展示。
  - 旧 smoke workflow 的 `steps=3` 不适合正式画质判断，`steps=30` 已验证可以恢复正常输出质量。
  - 资源不对齐可能直接报错，也可能静默生成不一致结果；静默不一致比显式报错更危险。
  - `status.json/events.jsonl/remote_sampling_report.txt` 已在 monitor smoke 和 20-step quality flow 中生成。
  - 资源 preflight 已验证能在上传 latent 前拦截缺失 LoRA，并给出上传命令提示。
- Active assumptions:
  - 远端 `comfy.sample.sample(..., callback=...)` 在当前 ComfyUI 0.26.0 中可稳定复刻 `common_ksampler` 的行为。
  - 通过 SFTP 轮询远端 `status.json` 的开销足够低，不会显著拖慢采样。
  - 第一阶段无需前端 JS，即可通过 progress bar、日志和 report 满足排障需求。
  - 本地 LoRA 根目录仍为 `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\models\loras`。
- Locked decisions:
  - `Remote_Sampling_local` 的第一个输出继续保持 `LATENT`，保护已有 workflow。
  - preflight 默认开启；资源缺失时在上传 latent 前失败。
  - 远端仍只运行模型加载、LoRA 加载和采样，不引入 VAE decode/save image。
  - 监控先做后端协议和 ProgressBar，再做节点面板 JS。
  - 自动 profile 仍是正式转换路径，固定 profile 只用于明确指定的调试或手写 workflow。
  - 第一版节点面板显示采用 ComfyUI `ui.text` 返回执行后 report，同时保留原生 ProgressBar；暂不引入前端 JS。
- Open questions:
  - 是否要求对所有模型资源做 SHA256 强校验，还是先采用存在性 + size 校验以降低耗时？
  - 节点面板显示是否必须实时刷新，还是接受执行完成后显示最后一次 job 摘要？
  - 是否为 `Remote_Sampling_local` 增加第二个 `STRING` 输出，还是新建独立 `Remote_Sampling_Report_Viewer` 节点以避免破坏 UI 布局？
  - 多个 `Remote_Sampling_local` 并行或串联时，前端状态面板是否需要按 `sampler_id` 分组显示？

## 关键制品与环境
- Canonical docs:
  - `F:\TieguoDun\Remote_comfyui\remote_sampling_monitoring_task_book.md`: 本任务书。
  - `F:\TieguoDun\Remote_comfyui\remote_sampling_monitoring_goal_prompt.md`: 与本任务书配套的最终结果导向执行提示词。
  - `F:\TieguoDun\Remote_comfyui\plan.md`: 主项目进度与已验证证据。
  - `F:\TieguoDun\Remote_comfyui\remote_sampling_usage.md`: 用户使用说明。
  - `F:\TieguoDun\Remote_comfyui\remote_sampling_workflow_conversion_rules.md`: workflow 转换规则。
- Important code or output artifacts:
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\protocol.py`: status/event 协议应落在这里。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\nodes\remote_sampling_local.py`: 本地节点进度展示和 bridge 调用。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\nodes\remote_sampling_remote.py`: 远端采样回调和 status 更新。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\tools\remote_sampling_job_cli.py`: 上传/下载速度、preflight、远端状态轮询。
  - `F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py`: 自动 profile 生成与资源声明来源。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles`: 内置与自动生成 profile。
- Required commands:
  - `python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py status`: 检查远端服务状态。
  - `python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py start`: 启动远端服务。
  - `python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py stop`: 停止远端服务。
  - `python C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py --cmd "<cmd>"`: 远端检查与验证。
  - `python -m py_compile ...`: 修改 Python 文件后的基本语法验证。
- Environment baseline:
  - 本地 workspace: `F:\TieguoDun\Remote_comfyui`
  - 本地 ComfyUI: `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI`
  - 本地 ComfyUI API: `127.0.0.1:8188`
  - 远端 project: `/home/user02/remote_ComfyUI`
  - 远端 ComfyUI: `/home/user02/remote_ComfyUI/ComfyUI`
  - 远端 API: `127.0.0.1:8197`
  - 远端节点包: `/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/ComfyUI-Remote-Sampling`
  - 远端工作边界: 只写 `/home/user02` 下内容。

## 进度台账
- Overall progress: 监控、远端 step 回传、资源 preflight、执行后 report、同步、代表性回归与文档固化均已完成。
- Phase 1: done
- Phase 2: done
- Phase 3: done
- Phase 4: done
- Phase 5: done
- Phase 6: done
- Validation status: `python -m py_compile` 已通过；4-step monitor smoke 已通过；20-step quality flow 已通过；缺失 ASCII LoRA preflight 已通过；2026-07-01 修复 8197 临时远端服务并发误杀问题后，30-step converted workflow 与两个并发 bridge CLI lockfix job 均已通过；远端 job 与 output 目录未发现匹配图片文件。
- Residual risks:
  - 直接替换 `common_ksampler` 为 `comfy.sample.sample` 需要仔细保持参数等价，否则可能引入画质或行为差异。
  - 前端 JS 节点面板显示未在第一版实现；当前采用 ProgressBar + `ui.text` report + 文件 report，后续如需更强 UI 可单独扩展。
  - SHA256 强校验大模型会耗时，可能需要先做 size 校验，再异步补 hash。
  - 远端状态轮询过频可能影响 SFTP/SSH 稳定性，应限制为 0.5-2 秒级。
  - 远端服务端口目前按 8197 串行化保护；如后续需要真正并发采样，应改为每 job 独立端口或持久服务调度，而不是移除锁。

## 下一步动作
向用户提交最终汇报。

## 进度更新
- Overall progress: 已完成 Remote Sampling 监控与资源校验优化的核心实现、代表性验证、同步、并发误杀修复和文档固化。
- Active phase: Phase 6: 回归验证与文档固化
- Execution readiness: executing
- Phase status:
  - Phase 1: 状态协议与可观测性基线: done
  - Phase 2: 本地传输监控与整体进度条: done
  - Phase 3: 远端采样 step 进度: done
  - Phase 4: 资源 preflight 与人类可执行报错: done
  - Phase 5: 节点面板显示与执行后报告: done
  - Phase 6: 回归验证与文档固化: done
- Change summary: `protocol.py` 增加 status/event/report helper；`remote_sampling_local.py` 改为流式读取 bridge 进度并用 ProgressBar 更新；`remote_sampling_remote.py` 改为带 callback 的采样路径；`remote_sampling_job_cli.py` 增加 preflight、上传/下载速度统计、远端 status 轮询、report 生成、8197 端口级远端互斥锁和异常失败状态补强；本地和远端 custom node 包均已同步。
- Validation result: `python -m py_compile` 通过；monitor smoke、20-step quality flow、缺失 LoRA preflight 均已通过；2026-07-01 30-step converted workflow `remote_sampling_20260701_223516_3a6d217d_converted_fixed30_500` 成功，采样 30/30；并发 CLI lockfix job `remote_sampling_20260701_lockfix_a_500` 与 `remote_sampling_20260701_lockfix_b_500` 均成功，采样 4/4；远端 job 检查未发现图片文件；本地 8188 确认 `Remote_Sampling_local` 可见；远端 8197 无常驻监听、无 helper 进程、无残留锁。
- Decision updates:
  - Verified facts: `Remote_Sampling_local` 可通过 `ui.text` 返回执行后 report，且不改变第一个 `LATENT` 输出。
  - Locked decisions: 第一版不做前端 JS，避免引入前端版本兼容风险。
  - Open questions: 后续是否需要更强的实时节点面板 UI，仍作为扩展项。
- Residual risks: 复杂 conditioning、多采样器并行仍需后续扩展验证；当前已覆盖单采样器代表性路径，并已验证两个 bridge CLI 同时启动时不会互相杀掉远端临时 ComfyUI 服务。
- Next recommended action: 后续如需更强 UI，再单独扩展前端 JS 节点面板。
