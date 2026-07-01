## 计划元数据
- Plan ID: remote-sampling-completion-goal
- Version: v1
- Last updated: 2026-07-01 00:00 Asia/Shanghai
- Canonical progress file: F:\TieguoDun\Remote_comfyui\remote_sampling_custom_node_plan.md
- Supporting progress file: F:\TieguoDun\Remote_comfyui\plan.md
- Goal prompt file: F:\TieguoDun\Remote_comfyui\remote_sampling_completion_goal.md
- Current branch: not applicable
- Current active phase: complete
- Execution readiness: executing

## 长程 Goal 提示词
你是 Codex，负责自主推进 `F:\TieguoDun\Remote_comfyui` 项目直到 Remote ComfyUI 远程采样器达到可长期使用状态。最终目标是：本地 ComfyUI 执行输入图片读取、VAEEncode、conditioning 构造、工作流中间控制和最终 VAEDecode/SaveImage；远端 Linux ComfyUI 只作为采样算力后端，接收 latent/conditioning/采样参数，加载远端模型执行采样，并返回 output latent。远端不得生成输入图片或输出图片文件。

继续工作前必须先读取并遵守：
- `F:\TieguoDun\Remote_comfyui\remote_sampling_custom_node_plan.md`
- `F:\TieguoDun\Remote_comfyui\plan.md`
- `F:\TieguoDun\Remote_comfyui\remote_sampling_completion_goal.md`

连接远端服务器时必须使用 `company-lab-2-server` skill 的规则和命令，只在 `/home/user02` 下创建、修改、删除项目文件。不得设置 passwordless SSH，不得修改 `/etc`、`/usr`、`/var`、`/opt`、`/root`、Docker daemon 或系统包。远端 ComfyUI 默认只监听 `127.0.0.1`。

执行策略：
- 优先推进可验证的最小闭环，不做大而空的重构。
- 每完成一个阶段，更新 `remote_sampling_custom_node_plan.md` 和必要时更新 `plan.md`。
- 所有代码改动用 `apply_patch`，不要用 shell 重写源码文件。
- 每次运行 ComfyUI 临时服务后都要检查端口并清理，除非该服务被明确纳入常驻/tmux 约定。
- 远端验证必须确认 job 目录只包含 tensor/job/result/prompt 等中间文件，不应出现 PNG/JPG/JPEG/WEBP 输入或输出图片。

## 总目标拆解
### Phase G1: 远端服务运行方式固化
- Purpose: 把远端 ComfyUI 的启动、停止、状态、日志查看整理为可复用工具，避免每次由 bridge 随机拉起临时进程。
- Outputs:
  - 本地管理脚本，例如 `tools/remote_comfy_service.py`。
  - 远端 tmux session 约定，例如 `remote-comfyui-8197`。
  - 文档中的常驻/临时模式说明。
- Completion criteria:
  - 能执行 `status/start/stop/logs`。
  - 服务只监听 `127.0.0.1:8197`。
  - 重复 start 不会启动多个重复实例。
  - stop 后 `8197` 无监听。
- Validation:
  - 运行 status/start/status/logs/stop/status。
  - 远端 `/object_info` 能看到 `Remote_Sampling_remote`。
- Evidence:
  - 已实现本地管理脚本：`F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py`。
  - 语法检查通过：`python -m py_compile tools\remote_comfy_service.py`。
  - `status` 初始验证通过：tmux session `remote-comfyui-8197` 不存在，`127.0.0.1:8197` 无监听。
  - `start` 验证通过：远端 tmux session 启动，`127.0.0.1:8197` 监听，`/object_info` 返回 `819` 个节点，`Remote_Sampling_remote` 可见。
  - `logs` 验证通过：可读取 tmux pane 日志，显示 ComfyUI 已启动并监听 `http://127.0.0.1:8197`。
  - `stop` 验证通过：tmux session 被停止，`remaining_listeners` 为空。
  - stop 后二次 `status` 验证通过：tmux 不在，`8197` 无监听。

### Phase G2: 本地 WebUI 使用就绪
- Purpose: 让用户平时使用的本地 `127.0.0.1:8188` 加载 `Remote_Sampling_local`，避免只能用临时 `8198`。
- Outputs:
  - 本地 `8188` 节点加载状态验证。
  - 如果需要，安全地重启本地 ComfyUI 或给出明确人工重启步骤。
- Completion criteria:
  - `http://127.0.0.1:8188/object_info` 中存在 `Remote_Sampling_local`。
  - WebUI 能直接插入或运行 `Remote_Sampling_local`。
- Validation:
  - 通过 API 查询 `Remote_Sampling_local`。
  - 使用 `8188` 跑一个 512x768 / 2 steps 的 remote sampling smoke。
- Evidence:
  - 已重启本地常用 `127.0.0.1:8188`，重新加载 custom node。
  - `/object_info` 验证通过：节点总数 `2190`，`Remote_Sampling_local` 可见。
  - 使用 `8188` 完成 remote sampling smoke：
    - API prompt: `F:\TieguoDun\Remote_comfyui\workflows\runs\remote_sampling_g2_8188_smoke_20260701_api.json`
    - 本地 job: `F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260701_001311_7b244e39_g2_8188_smoke_500`
    - 远端 job: `/home/user02/remote_ComfyUI/jobs/remote_sampling_20260701_001311_7b244e39_g2_8188_smoke_500`
    - 本地输出图片: `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\g2_8188_smoke_20260701_00001_.png`
    - 远端输出目录未发现匹配图片文件。

### Phase G3: 真实工作流完整尺寸验证
- Purpose: 把已通过 reduced smoke 的 `ComfyUI_00042` 转换版提升到真实尺寸参数验证。
- Outputs:
  - 完整尺寸 API prompt。
  - 本地最终图片。
  - 本地和远端 job 证据。
- Completion criteria:
  - 使用真实参数 `1216x1920`、`30 steps`、原始 prompt/seed/sampler/scheduler/cfg。
  - 远端只产生 job tensor/result/prompt 文件，不产生图片。
  - 本地完成最终 VAEDecode/SaveImage。
- Validation:
  - 检查本地输出图片存在。
  - 检查远端 job 文件和 prompt class list。
  - 检查远端输出目录无匹配图片文件。
- Evidence:
  - 完整尺寸真实转换 workflow 已通过：
    - API prompt: `F:\TieguoDun\Remote_comfyui\workflows\runs\ComfyUI_00042_remote_sampling_converted_full_20260701_api.json`
    - 参数：`1216x1920`、`30 steps`、seed `664928445236589`、cfg `5.2`、sampler `seeds_2`、scheduler `simple`、denoise `1.0`
    - 本地 job: `F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260701_001457_4a139116_real00042_full_19`
    - 远端 job: `/home/user02/remote_ComfyUI/jobs/remote_sampling_20260701_001457_4a139116_real00042_full_19`
    - 本地输出图片: `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\real00042_full_20260701_00001_.png`
    - 远端 prompt class list：`UNETLoader`、`CLIPLoader`、`LoraLoader`、`LoraLoader`、`Remote_Sampling_remote`
    - 远端 forbidden image nodes：空。
    - 远端输出目录未发现匹配图片文件。

### Phase G4: Metadata 与审计增强
- Purpose: 让每次 remote sampling job 都能被追踪、复现和审计。
- Outputs:
  - `job.json/result.json` 增强。
  - job 文件 SHA256、prompt class list、本地输出路径记录。
  - 可选 job index 或 run summary。
- Completion criteria:
  - 每个 job 能明确回答：用了哪个 profile、哪些模型和 LoRA、采样参数、远端 prompt 路径、本地输出路径、各关键文件 SHA256。
- Validation:
  - 新 smoke job 的 `job.json/result.json` 包含新增字段。
  - 本地和远端关键文件 SHA256 可比对。
- Evidence:
  - 已增强代码：
    - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\protocol.py`
    - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\nodes\remote_sampling_local.py`
    - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\nodes\remote_sampling_remote.py`
    - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\tools\remote_sampling_job_cli.py`
  - `result.json` 已记录 `output.pt` size/SHA256。
  - `job.json.remote` 已记录 prompt class list 和 forbidden image nodes。
  - `job.json.local.files` 已记录 `inputs.pt/output.pt/result.json` 的 size/SHA256。
  - 最终审计 smoke 已通过：
    - API prompt: `F:\TieguoDun\Remote_comfyui\workflows\runs\remote_sampling_g4_audit_final_20260701_api.json`
    - 本地 job: `F:\TieguoDun\Remote_comfyui\jobs\remote_sampling_20260701_002701_c638f4f7_g4_audit_final_500`
    - 远端 job: `/home/user02/remote_ComfyUI/jobs/remote_sampling_20260701_002701_c638f4f7_g4_audit_final_500`
    - 本地输出图片: `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\g4_audit_final_20260701_00001_.png`

### Phase G5: 复杂工作流边界与转换规则
- Purpose: 明确第一版支持范围，避免用户误以为任意 ComfyUI 图都能无损转换。
- Outputs:
  - 转换规则文档。
  - 支持/不支持节点清单。
  - 已知风险：conditioning 泄露、latent 可逆性、LoRA-patched CLIP 一致性。
- Completion criteria:
  - 文档能指导后续把普通 `KSampler` 工作流改为 remote sampling 工作流。
  - 对 ControlNet/IPAdapter/AnimateDiff/自定义 conditioning 节点等明确标注当前策略。
- Validation:
  - 文档和转换脚本行为一致。
  - 对现有 `ComfyUI_00042` 例子给出转换前后说明。
- Evidence:
  - 已新增转换规则文档：`F:\TieguoDun\Remote_comfyui\remote_sampling_workflow_conversion_rules.md`。
  - 文档记录了支持范围、不支持范围、转换命令、KSampler 替换规则、LoRA clip 绕回规则、远端 profile 规则、隐私边界和验证要求。

### Phase G6: 收尾交付
- Purpose: 把项目状态整理到可交给用户长期使用的形态。
- Outputs:
  - 更新后的 `remote_sampling_custom_node_plan.md`。
  - 更新后的 `plan.md`。
  - 简洁使用说明。
  - 清理临时服务，确认远端无残留图片输出。
- Completion criteria:
  - 用户可以按文档启动远端服务、在本地 WebUI 使用 remote sampler、运行真实工作流。
  - 所有验证证据路径写入计划文档。
- Validation:
  - 端口检查：远端 8197 状态符合预期，本地无临时 8198 残留。
  - 文件检查：远端 job 目录无图片文件，远端 output 无匹配图片文件。
- Evidence:
  - 已新增使用说明：`F:\TieguoDun\Remote_comfyui\remote_sampling_usage.md`。
  - 最终清理已完成：`python tools\remote_comfy_service.py stop` 返回 `remaining_listeners: []`。
  - 本地 `8188` 最终状态验证通过：`Remote_Sampling_local` 可见，节点总数 `2190`。
  - 远端最终检查通过：
    - `/home/user02/remote_ComfyUI/jobs/remote_sampling_20260701_001311_7b244e39_g2_8188_smoke_500` 无图片文件。
    - `/home/user02/remote_ComfyUI/jobs/remote_sampling_20260701_001457_4a139116_real00042_full_19` 无图片文件。
    - `/home/user02/remote_ComfyUI/jobs/remote_sampling_20260701_002701_c638f4f7_g4_audit_final_500` 无图片文件。
    - 远端 `ComfyUI/output` 未发现以上 job 的匹配图片文件。
    - `127.0.0.1:8197` 无监听。

## 决策记录
- Verified facts:
  - 自定义节点核心抽象已跑通。
  - 单采样器、图生图 clean latent、双采样器、最小自动转换、外置 profile、metadata 初版、真实 workflow reduced smoke 已通过。
  - 远端模型已归位到 `/home/user02/remote_ComfyUI/ComfyUI/models`。
- Active assumptions:
  - 本地和远端当前 ComfyUI/PyTorch 版本下，基础 `CONDITIONING` 可通过 `.pt` 可靠序列化。
  - 第一版仍采用 profile-based remote sampling。
- Locked decisions:
  - 本地 `Remote_Sampling_local` 不要求 `MODEL` 输入，避免本地加载 diffusion model。
  - 远端只做 sampling backend，不做图片输入/输出。
  - 第一版不宣称强隐私；latent 和 conditioning 仍可能泄露信息。
- Open questions:
  - 本地常用 `8188` 是否可由 Codex 安全重启，还是需要用户手动重启。
  - 完整尺寸真实转换 workflow 的耗时和显存是否稳定。
  - 复杂 conditioning 节点的序列化兼容边界。

## 关键制品与环境
- Canonical docs:
  - `F:\TieguoDun\Remote_comfyui\remote_sampling_custom_node_plan.md`
  - `F:\TieguoDun\Remote_comfyui\plan.md`
  - `F:\TieguoDun\Remote_comfyui\remote_sampling_completion_goal.md`
  - `F:\TieguoDun\Remote_comfyui\remote_sampling_workflow_conversion_rules.md`
  - `F:\TieguoDun\Remote_comfyui\remote_sampling_usage.md`
- Important code or output artifacts:
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling`
  - `F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py`
  - `F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py`
  - `F:\TieguoDun\Remote_comfyui\workflows\runs\ComfyUI_00042_remote_sampling_converted_20260630_api.json`
  - `F:\TieguoDun\Remote_comfyui\jobs`
- Required commands:
  - `python C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py --cmd "<cmd>"`
  - `python F:\TieguoDun\Remote_comfyui\tools\upload_to_company_server.py "<local>=<remote>"`
  - `python F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py status|start|stop|logs`
  - `python -m py_compile <files>`
- Environment baseline:
  - Local: Windows, workspace `F:\TieguoDun\Remote_comfyui`, local ComfyUI usually on `127.0.0.1:8188`.
  - Remote: `/home/user02/remote_ComfyUI`, Ubuntu 24.04 aarch64, NVIDIA GB10, ComfyUI 0.26.0, PyTorch `2.12.1+cu130`.

## 进度台账
- Overall progress: Goal 已完成；远端服务管理、本地 8188 加载、真实工作流完整尺寸、metadata 审计、转换规则文档、最终使用说明和清理检查均已完成。
- Phase G1: done
- Phase G2: done
- Phase G3: done
- Phase G4: done
- Phase G5: done
- Phase G6: done
- Validation status: 全部 goal 阶段验证通过。远端 `8197` 已停止；本地 `8188` 可用且 `Remote_Sampling_local` 可见；关键远端 job/output 均无图片产物。
- Residual risks:
  - 后续更复杂 conditioning 节点仍可能有 `.pt` 序列化兼容风险。
  - `.pt` 序列化是受信任内部协议，不适合开放给不可信输入。

## 下一步动作
Goal 已完成。后续若继续扩展，应从 `remote_sampling_workflow_conversion_rules.md` 的复杂 conditioning 边界开始。
