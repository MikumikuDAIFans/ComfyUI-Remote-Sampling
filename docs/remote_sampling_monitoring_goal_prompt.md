# Remote Sampling 监控与资源校验 Goal 提示词

用途：当 `remote_sampling_monitoring_task_book.md` 经用户审核通过后，把下面提示词复制到新的 Codex 会话中，即可让新会话以最终结果为目标开始端到端实现。

注意：粘贴此提示词即表示用户已批准执行 `remote_sampling_monitoring_task_book.md`。如果仍在讨论方案，不要使用此提示词启动实现。

```text
请基于已批准的 canonical task book，端到端实现 Remote Sampling 自定义节点的监控与资源校验优化。

最终目标：
让 `ComfyUI-Remote-Sampling` 在保持既有隐私边界的前提下，具备可观测、可诊断、可校验的远程采样能力：
- 本地 `Remote_Sampling_local` 执行时能显示或记录 latent/input 上传进度、上传速度、远端采样进度、采样耗时、output latent 下载进度、下载速度和总耗时。
- 远端 `Remote_Sampling_remote` 能把真实采样 step 进度回传给本地。
- 每个 job 都生成可审计的 `status.json`，必要时生成 `events.jsonl` 和执行后 report。
- 在远端模型、CLIP、LoRA 等资源缺失或 profile 与实际资源不匹配时，必须在上传 latent 前失败，并给出人类可执行的补齐提示和上传命令建议。
- 远端仍不得读取或保存 RGB 输入/输出图片；远端 job 和 output 目录不得出现 PNG/JPG/JPEG/WEBP。

Read first:
- `F:\TieguoDun\Remote_comfyui\remote_sampling_monitoring_task_book.md`
- `F:\TieguoDun\Remote_comfyui\plan.md`
- `F:\TieguoDun\Remote_comfyui\remote_sampling_usage.md`
- `F:\TieguoDun\Remote_comfyui\remote_sampling_workflow_conversion_rules.md`

Canonical progress file:
- `F:\TieguoDun\Remote_comfyui\remote_sampling_monitoring_task_book.md`

Relevant code:
- `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\protocol.py`
- `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\nodes\remote_sampling_local.py`
- `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\nodes\remote_sampling_remote.py`
- `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\tools\remote_sampling_job_cli.py`
- `F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py`

Execution contract:
- 把这次任务视为执行型任务，不要继续停留在方案讨论。
- 读完 canonical sources 后立即开始实现。
- 按任务书 Phase 1 到 Phase 6 推进；低风险细节自行合理决策。
- 不要在每个阶段完成后停下来请求常规确认；只有完整实现完成或遇到真实阻塞时再汇报。
- 每完成一个有意义阶段，更新 `remote_sampling_monitoring_task_book.md` 的进度台账。
- 如果修改了影响用户使用的行为，同步更新 `remote_sampling_usage.md` 和 `remote_sampling_workflow_conversion_rules.md`。
- 如果需要连接远端服务器，必须使用 `company-lab-2-server` 技能和既有脚本；远端写入范围限定在 `/home/user02/remote_ComfyUI`。
- 不要回滚用户已有改动；遇到非本任务相关的脏文件直接忽略。
- 实现后同步本地和远端 custom node 包。

Locked decisions:
- `Remote_Sampling_local` 的第一个输出必须继续保持 `LATENT`，避免破坏已有 workflow。
- preflight 默认开启；远端资源缺失时必须在上传 latent 前失败。
- 远端仍只运行模型加载、LoRA 加载和采样，不引入 VAE decode、PreviewImage 或 SaveImage。
- 监控先实现后端协议、ProgressBar 和 report；再做节点面板显示。
- 自动 profile 是正式转换路径；固定 profile 仅用于明确指定的调试或手写 workflow。

Implementation order:
1. 实现 `status.json` / `events.jsonl` 协议和读写 helper。
2. 增加上传/下载传输监控、速度统计和本地 ProgressBar。
3. 将远端采样改为可回调 step 进度的等价采样路径，并把采样进度回传给本地。
4. 增加资源 preflight：检查 UNET、CLIP、LoRA 存在性，必要时检查 size/hash，并给出补齐提示。
5. 增加执行后 report；如可行，实现 `Remote_Sampling_local` 节点面板状态显示或 report viewer。
6. 做回归验证，确认 smoke、正式质量流、至少一条真实 workflow 仍成功，且远端无图片输出。
7. 更新所有相关文档和 task book 进度台账。

Definition of done:
- `Remote_Sampling_local` 能在本地显示整体进度，并记录上传速度、下载速度、采样耗时和总耗时。
- 远端采样能产生真实 step 进度，`status.json.sampling` 包含 `step`、`steps`、`percent`、`elapsed_sec`、`sec_per_step`、`eta_sec`。
- 成功 job 含有完整 `status.json`、`job.json.local.metrics` 和可读 report。
- 缺失资源 job 在上传 latent 前失败，错误信息包含缺失资源、期望远端路径、可能本地路径和上传命令建议。
- 现有远程采样 workflow 不被破坏，至少完成一个低步数 smoke 和一个 20-30 step 正式质量流验证。
- 远端 job 目录和远端 `ComfyUI/output` 不出现与远程采样 job 相关的 PNG/JPG/JPEG/WEBP。
- 本地与远端 `ComfyUI-Remote-Sampling` 包已同步。
- `remote_sampling_monitoring_task_book.md`、`plan.md`、`remote_sampling_usage.md`、`remote_sampling_workflow_conversion_rules.md` 已更新到最新状态。

Required validation:
- `python -m py_compile` 覆盖修改过的 Python 文件。
- 本地 8188 提交至少一个最小 remote sampling smoke workflow。
- 本地 8188 提交至少一个 20-30 step 正式质量 workflow。
- 构造一个缺失 LoRA 或缺失资源 profile，确认 preflight 在上传 latent 前失败且报错可执行。
- 使用 `company-lab-2-server` 检查远端 job 目录无图片文件。
- 检查最新 job 的 `status.json`、`result.json`、`job.json.local.metrics` 字段完整。

Agent Team strategy:
- 如果当前 Codex 环境支持 subagent，可选择性并行：
  - 一个 worker 负责资源 preflight 设计与实现范围审查。
  - 一个 worker 负责前端节点面板或 report viewer 可行性调查。
  - 主会话负责协议、bridge、远端采样回调、集成和最终验证。
- 并行工作不得重叠修改同一文件；所有集成与最终验证由主会话完成。
- 如果环境不适合安全并行，以主会话本地执行为主。

Escalation rules:
- 仅在以下情况暂停并询问用户：
  - 需要破坏当前隐私边界，例如让远端读取/保存 RGB 图片。
  - 需要修改 `/home/user02` 以外的远端系统目录。
  - 需要做会破坏既有 workflow 兼容性的节点接口变更。
  - 环境、权限、依赖或远端服务出现真实阻塞，无法自行恢复。
- 如果被阻塞，只报告阻塞点、已尝试方案、需要用户做出的最小决策。

Start by:
读取 `F:\TieguoDun\Remote_comfyui\remote_sampling_monitoring_task_book.md`，将 `Execution readiness` 更新为 `executing`，然后开始 Phase 1: 状态协议与可观测性基线。
```
