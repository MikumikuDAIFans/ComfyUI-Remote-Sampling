# Remote Sampling 下一阶段升级长程任务书

## 计划元数据
- Plan ID: remote-sampling-next-upgrade-20260708
- Version: v1
- Last updated: 2026-07-08 18:24 Asia/Shanghai
- Canonical progress file: `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_next_upgrade_task_book.md`
- Related handoff file: none
- Current branch: `main`
- Current active phase: complete
- Execution readiness: executing

## 目标

把 `ComfyUI-Remote-Sampling` 从当前“可用的工作流级远程采样插件”升级为更稳定、更可诊断、更适合公开使用的工程化系统。最终状态要求：远端连接、资源同步、工作流转换、采样执行、状态监控、测试矩阵和用户文档形成闭环；系统能在复杂 workflow、缺失 LoRA、自定义节点同步、SSH 抖动和采样器兼容性风险下给出可靠行为和明确诊断。

## 范围与约束

- In scope:
  - 统一远端 SSH/session/SFTP/stream upload 管理。
  - 修复采样期间 status/events 读取不走重连机制的问题。
  - 增强工作流级资源检查和资源同步的 retry、resume 和结构化错误。
  - 消除测试对真实 `profiles/generated/` 目录的副作用。
  - 建立采样器本地/远端等价性测试矩阵。
  - 完善前端运行历史、错误摘要和 job/report 快捷入口。
  - 强化自定义节点同步和 Linux 依赖检测。
  - 补充公开仓库安装、排障和架构文档。
  - 全面单元测试、集成测试、远端实测和隐私边界验证。
- Out of scope:
  - 不改变核心隐私边界：远端仍不得读取或保存 RGB 输入/输出图片。
  - 不把 VAE decode、PreviewImage、SaveImage 引入远端采样 workflow。
  - 不强制替换用户采样器；只做风险提示、等价性验证和可选建议。
  - 不修改 `/home/user02` 以外的远端系统目录。
  - 不提交模型、图片、job、run、latent、secret、真实凭据。
- Constraints:
  - `Remote_Sampling_local` 第一个输出必须保持 `LATENT`。
  - 日常使用路径保持：`Check & Sync -> Convert Canvas -> ComfyUI 原生运行按钮`。
  - GitHub 网络操作必须使用 `git-proxy-push` 技能和 `127.0.0.1:11809` 代理。
  - 远端操作必须使用 `company-lab-2-server` 技能；写入范围限定在 `/home/user02/remote_ComfyUI`。
  - 需要兼容 Windows 本地 ComfyUI 与 Linux 远端 ComfyUI。
  - Windows/PowerShell 中文路径输出可能乱码，验证中文路径时使用 UTF-8 JSON 或 unicode escape。

## 执行阶段

### Phase 1: 远端会话管理与传输可靠性统一
- Purpose: 消除当前远端连接能力分散在 `server_exec.py`、Paramiko SFTP、stream uploader、job CLI 和资源 checker 中导致的偶发失败和重复实现。
- Outputs:
  - 新增或重构统一模块，例如 `ComfyUI-Remote-Sampling/remote_session.py` 或 `tools/remote_session.py`。
  - 提供统一接口：远端命令执行、SFTP stat/get/put、stream upload、重连、retry/backoff、keepalive、远端路径 sandbox 校验。
  - `remote_sampling_job_cli.py` 的 status/events 轮询改为可重连读取。
  - `check_remote_resource_plan.py`、`check_remote_custom_nodes_plan.py`、`sync_remote_resources.py` 逐步迁移到统一 session。
- Completion criteria:
  - 采样期间 SFTP 断线不会导致“远端已完成、本地误报失败”。
  - 工作流级资源检查遇到临时 tunnel/SSH/banner 错误时能自动重试并记录结构化错误。
  - 所有远端写入仍被限制在 `/home/user02/remote_ComfyUI`。
- Validation:
  - 单元测试覆盖 session retry、远端路径逃逸拒绝、上传续传、完整 `.uploading` rename。
  - 构造 mock/临时断线场景，确认 status/events 轮询能恢复。
  - 远端实测一次 20-step anima workflow，确认 job 成功且 report 完整。
  - 远端隐私检查：job 目录和 `ComfyUI/output` 无 PNG/JPG/JPEG/WEBP。
- Evidence:
  - 新增测试文件和通过日志。
  - 最新成功 job 的 `status.json`、`events.jsonl`、`remote_sampling_report.txt`。
  - 远端无图片输出的命令结果。

### Phase 2: 资源同步队列与可恢复状态
- Purpose: 让模型、LoRA、VAE 和其他资源同步具备可恢复、可审计和可解释能力。
- Outputs:
  - `resources_sync_report.json` 增加 per-resource 状态：`pending`、`uploading`、`uploaded`、`verified`、`failed`。
  - 支持中断后再次 `Check & Sync` 自动恢复未完成资源。
  - 小文件默认 SHA256；大文件支持配置化 hash 策略：`size_only`、`sha256_on_demand`、`sha256_required`。
  - 上传失败错误中包含本地路径、远端目标路径、已上传字节、恢复建议。
- Completion criteria:
  - 缺失 LoRA 能自动同步到镜像相对目录。
  - 传输中断后重跑不会重复上传已完整文件。
  - size mismatch 默认 fail-closed，只有明确参数允许时才覆盖。
- Validation:
  - 单元测试覆盖资源 diff 分类、sync report 状态机、hash 策略、中文路径 unicode 保存。
  - 实测使用缺失 LoRA：`Anima/画风/nnmbpx_v1_epoch22.safetensors` 或等效小 LoRA。
  - 实测中断/续传：构造 `.uploading` 部分文件后重跑 sync。
  - SHA256 对齐验证至少覆盖一个 LoRA。
- Evidence:
  - `resources_diff.json`、`resources_sync_report.json`。
  - 本地/远端 SHA256 输出。
  - 成功出图路径和 job report。

### Phase 3: 工作流转换与采样器等价性测试矩阵
- Purpose: 系统化验证本地 KSampler 与远端 Remote_Sampling 在不同采样器组合下的等价性或风险边界。
- Outputs:
  - 新增测试工具，例如 `tools/run_sampler_parity_matrix.py`。
  - 建立采样器矩阵配置：`euler/normal`、`dpmpp_2m/normal`、`res_multistep/simple`、`seeds_2/simple` 等。
  - 输出本地/远端对照报告，包含 prompt sha、profile sha、seed、采样器、图像路径、latent hash 或图像相似度指标。
  - 前端和 report 中展示采样器 parity risk warning。
- Completion criteria:
  - 至少一个已验证等价组合被标记为 recommended，例如 `euler/normal`。
  - 已知不稳定组合保留语义但明确 warning，例如 `seeds_2/simple`。
  - 每次转换都能证明 remote prompt 是从当前 workflow 派生，而非旧 workflow。
- Validation:
  - 单元测试覆盖 profile hash、remote prompt hash、风险 warning、model patch 链路。
  - 实测至少两组采样器：一个 recommended、一个 risk warning。
  - 本地/远端对照图或 latent hash 留证。
- Evidence:
  - parity matrix JSON/Markdown 报告。
  - 本地/远端输出图路径。
  - 最新 conversion manifest。

### Phase 4: 前端运行历史与诊断体验
- Purpose: 提升用户在 ComfyUI 前端中的可观察性和排障效率。
- Outputs:
  - 前端面板新增 recent runs/jobs 列表。
  - 最新 job/report/status 快捷打开或复制路径。
  - 错误摘要复制按钮。
  - `Check & Sync`、`Convert Canvas`、原生队列执行之间的状态关联展示。
  - 面板继续支持拖动、隐藏、非遮挡式使用。
- Completion criteria:
  - 用户能在前端看到最新 workflow runtime id、job id、阶段、耗时、失败原因。
  - 不需要重新点击详情页才能看到关键状态更新。
  - UI 不遮挡主要工作区，节点面板内布局不重叠。
- Validation:
  - Playwright 或浏览器自动化截图覆盖桌面视口。
  - 实测一次成功 job 和一次故意失败 job，确认错误摘要可见。
  - 检查 UI 文本不重叠，按钮不冲突。
- Evidence:
  - 截图文件。
  - 前端控制台无关键错误。
  - 对应 run/job 的 JSON 状态。

### Phase 5: 自定义节点同步与远端环境管理
- Purpose: 让复杂 workflow 的自定义节点依赖更可靠地在远端对齐。
- Outputs:
  - 自定义节点包检测增强：本地包路径、入口文件、依赖文件、requirements、可能的系统依赖。
  - 优先打包本地 custom node 上传；失败时生成 ComfyUI Manager fallback 计划。
  - 远端 import smoke test 和缺失依赖诊断。
  - 对没有自定义节点依赖的 workflow 直接跳过远端 custom node 检查，减少无意义 tunnel 风险。
- Completion criteria:
  - 无自定义节点 workflow 不再执行不必要的 custom-node 远端检查。
  - 有自定义节点 workflow 能生成明确同步计划和失败提示。
  - 远端环境报告能区分“缺包”“导入失败”“Python 依赖缺失”“系统依赖缺失”。
- Validation:
  - 单元测试覆盖 no-custom-node short circuit、ambiguous package fail-closed、requirements 探测。
  - 构造一个简单自定义节点包，实测打包上传和 import smoke。
  - 构造缺依赖节点，确认错误提示可执行。
- Evidence:
  - `remote_environment_report.json`。
  - import smoke report。
  - 前端/报告中的诊断摘要。

### Phase 6: 公开仓库文档、安装流程与发布准备
- Purpose: 让项目从个人实验环境走向可复用公开项目。
- Outputs:
  - `INSTALL.md`：本地 Windows、远端 Linux、环境变量、SSH 配置、ComfyUI custom_nodes 安装。
  - `TROUBLESHOOTING.md`：常见错误、资源缺失、SSH 失败、中文路径、采样器不一致、远端隐私检查。
  - `ARCHITECTURE.md`：模块架构、数据流、隐私边界、job/run 文件结构。
  - README 精简为入口文档，链接上述文档。
  - `.env.example` 与配置说明同步。
- Completion criteria:
  - 新用户可以按文档理解系统当前工作流程。
  - 所有硬编码路径都有环境变量替代或注释说明。
  - 文档不包含真实凭据、模型文件、私有图片或 job 产物。
- Validation:
  - 文档链接检查。
  - secret scan。
  - 从干净 clone 视角检查安装步骤是否自洽。
- Evidence:
  - 新增/更新文档。
  - secret scan 输出。
  - 最终 `git status --short` 干净。

### Phase 7: 端到端回归、实测与发布
- Purpose: 在合并所有升级后执行完整质量门禁，确保系统功能、隐私边界和文档一致。
- Outputs:
  - 回归测试报告。
  - 至少两条真实 workflow 实测记录。
  - 最新远端隐私检查记录。
  - 最终 commit 和 push。
- Completion criteria:
  - `python -m py_compile` 覆盖所有修改过的 Python 文件。
  - `python -m unittest discover -s tests -p test_*.py -v` 全部通过。
  - 本地 ComfyUI 8188 至少执行：
    - 一个最小 anima smoke workflow。
    - 一个缺失 LoRA 自动同步 workflow。
    - 一个 20-step 推荐采样器质量 workflow。
    - 一个失败 preflight 场景，确认不会上传 latent。
  - 远端 job 目录和远端 `ComfyUI/output` 无相关 PNG/JPG/JPEG/WEBP。
  - GitHub main 推送成功并验证远端 head。
- Validation:
  - 本地测试命令输出。
  - ComfyUI API history 成功记录。
  - 输出图截图或路径。
  - 远端隐私检查命令输出。
  - `git ls-remote origin refs/heads/main`。
- Evidence:
  - `docs/reports/` 下的最终回归报告。
  - 最新 commit hash。
  - 相关 job/run 路径。

## 决策记录

- Verified facts:
  - 当前项目最新推送提交为 `444c4cd Improve workflow runtime sync and diagnostics`。
  - 当前系统日常使用路径是 `Check & Sync -> Convert Canvas -> ComfyUI 原生运行按钮`。
  - `Remote_Sampling_local` 第一个输出必须保持 `LATENT`。
  - anima + `euler/normal` 已实测可获得本地/远端视觉一致结果。
  - `seeds_2/simple` 已实测存在本地/远端同 seed 结果不一致风险。
  - 缺失 LoRA `Anima/画风/nnmbpx_v1_epoch22.safetensors` 已实测能同步并远程采样成功。
  - 远端真实中文目录可用；PowerShell/GBK 输出可能把 `画风` 显示为乱码，需用 unicode escape 验证。
- Active assumptions:
  - 远端服务器仍通过 `company-lab-2-server` 技能访问。
  - 本地 ComfyUI API 端口仍为 `8188`。
  - 远端临时 ComfyUI 采样端口仍优先使用 `8197`，并通过 lock 串行化。
  - 项目会继续公开托管在 GitHub `MikumikuDAIFans/ComfyUI-Remote-Sampling`。
- Locked decisions:
  - 不恢复 `Run Guarded` 作为日常入口；最终运行交给 ComfyUI 原生 Queue/Run。
  - 资源相对路径必须镜像本地 `ComfyUI/models` 目录结构。
  - 远端只执行模型加载、LoRA 加载、model patch 和 latent 采样。
  - 自动 profile 是正式路径；固定 profile 只用于明确调试。
  - 采样器风险以 warning 和测试矩阵表达，不自动改写用户采样器。
- Open questions:
  - 是否需要支持多远端、多 GPU 或并发 job 调度。
  - 是否需要为非公司服务器提供完全通用 SSH 配置向导。
  - 是否需要引入图像相似度指标，还是先使用 latent hash 与人工截图对照。
  - 自定义节点 Linux 依赖安装是否允许调用系统包管理器，还是仅允许 Python venv 层安装。

## 关键制品与环境

- Canonical docs:
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_next_upgrade_task_book.md`: 本任务书。
  - `F:\TieguoDun\Remote_comfyui\docs\current_project_workflow.md`: 当前项目工作流程说明。
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_usage.md`: 当前使用说明。
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_conversion_rules.md`: 转换规则。
- Important code or output artifacts:
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\tools\remote_sampling_job_cli.py`: job 传输、远端采样提交、状态下载。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\workflow_runtime.py`: 工作流级 plan/sync/convert/run 后端。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\web\remote_workflow_runtime.js`: 前端面板。
  - `F:\TieguoDun\Remote_comfyui\tools\sync_remote_resources.py`: 资源同步入口。
  - `F:\TieguoDun\Remote_comfyui\tools\upload_to_company_server_stream.py`: 流式上传。
  - `F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py`: API prompt 转换器。
  - `F:\TieguoDun\Remote_comfyui\tests\`: 单元测试目录。
- Required commands:
  - `python -m py_compile <modified python files>`: Python 编译检查。
  - `python -m unittest discover -s tests -p test_*.py -v`: 单元测试。
  - `python C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py --cmd "<cmd>"`: 远端命令。
  - `git -c http.proxy=http://127.0.0.1:11809 -c https.proxy=http://127.0.0.1:11809 push origin main`: GitHub 推送。
- Environment baseline:
  - 本地 Windows，项目根目录 `F:\TieguoDun\Remote_comfyui`。
  - 本地 ComfyUI portable 根目录 `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI`。
  - 远端工作区 `/home/user02/remote_ComfyUI`。
  - 远端 ComfyUI 根目录 `/home/user02/remote_ComfyUI/ComfyUI`。
  - 远端不得写入 `/home/user02` 以外的系统目录，除非用户明确批准。

## 进度台账

- Overall progress: Phase 1 到 Phase 7 已完成并通过验证。最终回归报告见 `docs/reports/phase7_regression_report_20260708.md`。剩余动作是提交并推送本次改动。
- Phase 1: done
- Phase 2: done
- Phase 3: done
- Phase 4: done
- Phase 5: done
- Phase 6: done
- Phase 7: done
- Validation status:
  - 已有基础验证：最新提交前 `py_compile` 和 8 个单元测试通过。
  - Phase 1 本轮验证：`python -m py_compile ComfyUI-Remote-Sampling/remote_session.py ComfyUI-Remote-Sampling/tools/remote_sampling_job_cli.py tools/check_remote_resource_plan.py tools/check_remote_custom_nodes_plan.py tests/test_remote_session_phase1.py` 通过。
  - Phase 1 本轮验证：`python -m unittest discover -s tests -p test_*.py -v` 通过，当前 18 个测试全部 OK。
  - Phase 1 本轮验证：`remote_sampling_job_cli.py --help`、`check_remote_resource_plan.py --help`、`check_remote_custom_nodes_plan.py --help` 均可正常导入和显示帮助。
  - Phase 1 本轮实测发现：首次 20-step anima workflow 在远端采样状态轮询时读到非完整 `status.json`，报 `JSONDecodeError: Extra data`；已通过 JSON 原子写入和读取容错修复。
  - Phase 1 本轮实测发现：第二次 20-step anima workflow 在 latent 上传阶段遭遇 tunnel 断开，错误文本为 `Unable to connect to port ...`；已纳入 retryable marker 并补充单元测试。
  - Phase 1 本轮实测发现：同步 custom node zip 时，stream uploader 曾把大小不同的最终 zip 当作续传基础 append，导致 `zipfile.BadZipFile`；已改为只续传 `.uploading`，最终文件 size mismatch 时删除重传，并补充单元测试。
  - Phase 1 远端通道状态：`company-lab` jump host 曾短暂超时，后续 `server_exec.py --cmd 'echo server_ok'` 恢复成功。
  - Phase 1 远端实测：`workflow_runtime_20260708_105214_28171948` 成功转换当前 prompt；ComfyUI prompt `132c0a18-6759-42bb-be1d-53c0bfa867e6` 成功；job `remote_sampling_20260708_105218_baf3a0d6_workflow_workflow_runtime_20260708_105214_28171948_500` 完成。
  - Phase 1 job 关键指标：upload `299066` bytes、download `394786` bytes、sampling `20/20`、sampling elapsed `5.456s`、total elapsed `80.284s`。
  - Phase 1 本地输出图：`F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\phase1_session_retry_anima4_20260708_00001_.png`。
  - Phase 1 隐私检查：远端 job 目录只包含 `events.jsonl`、`inputs.pt`、`job.json`、`output.pt`、`remote_sampling_report.txt`、`result.json`、`status.json`；远端 job 目录和最近 20 分钟远端 `ComfyUI/output` 均未发现 PNG/JPG/JPEG/WEBP。
  - 已有实测证据：anima base、缺失 LoRA 同步、远程采样、本地 decode/save 成功。
  - Phase 2 本轮代码进展：`sync_remote_resources.py --help` 已显示 `--hash-strategy {size_only,sha256_on_demand,sha256_required}`、`--server-exec` 和 `--remote-base`。
  - Phase 2 本轮验证：`python -m unittest discover -s tests -p test_*.py -v` 通过，当前 20 个测试全部 OK。
  - Phase 2 本轮验证：新增测试覆盖资源同步失败报告、上传命令 retry、远端路径逃逸拒绝、最终文件 size mismatch 删除重传、sha256sum 输出解析、`sha256_required` 成功验证。
  - Phase 2 真实同步探针：本地临时资源 `transfer\phase2_sync_probe\codex_phase2_probe.safetensors`，远端目标 `/home/user02/remote_ComfyUI/tmp/phase2_sync_probe/codex_phase2_probe.safetensors`。
  - Phase 2 续传证据：远端预置 `.uploading` 为 `2112` bytes，`resources_sync_report.json` 记录从 `2112/135172` bytes 续传到 `135172/135172` bytes。
  - Phase 2 SHA256 证据：本地和远端 SHA256 均为 `b32892290ac23ac5295a67972c39e67ac33ff7d08b91141559b001bff2ac849b`，`sha256_verified: true`，远端 `.uploading` 已清理。
  - Phase 2 工作流级缺失 LoRA 验证：远端 `/home/user02/remote_ComfyUI/ComfyUI/models/loras/Anima/画风/nnmbpx_v1_epoch22.safetensors` 临时移到 `.phase2bak` 后，`/remote_workflow/runtime/run` 自动同步并恢复原路径。
  - Phase 2 LoRA 同步 run：`workflow_runtime_20260708_110721_a20a05b3`；`resources_sync_report.json` 记录 `uploaded: 1`、`failed: 0`、`sha256_verified: 1`、`bytes: 91851152`。
  - Phase 2 LoRA SHA256：本地与远端均为 `bdbcb25cac7dbf5bdbc15b09dc89d1916385829c035a419570306db0b2b17106`。
  - Phase 2 同步后出图：ComfyUI prompt `eb77edf9-bb33-4ad4-af9d-621764bcba09` 成功；job `remote_sampling_20260708_111511_1294bfc8_workflow_workflow_runtime_20260708_110721_a20a05b3_500` 完成；本地输出图 `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\output\remote_sampling_node\phase2_missing_lora_nnmbpx_guarded_20260708_00001_.png`。
  - Phase 2 隐私检查：远端 job 目录和最近 20 分钟远端 `ComfyUI/output` 均未发现 PNG/JPG/JPEG/WEBP；远端临时 `.phase2bak` 已删除。
  - Phase 3 代码进展：新增 `tools/run_sampler_parity_matrix.py`，新增 `tests/test_sampler_parity_matrix.py`。
  - Phase 3 本轮验证：`python -m unittest discover -s tests -p test_*.py -v` 通过，当前 24 个测试全部 OK。
  - Phase 3 矩阵报告：`runs\sampler_parity_matrix_20260708_phase3.json` 和 `runs\sampler_parity_matrix_20260708_phase3.md`。
  - Phase 3 recommended 组合：`euler/normal`，本地 prompt `2003b11d-6977-42ed-9039-dc344d9968c3` 成功，远端 run `workflow_runtime_20260708_112058_5ac9197f`、prompt `f5448d09-1add-4a8d-836f-6b615de06fb0` 成功。
  - Phase 3 risk warning 组合：`seeds_2/simple`，本地 prompt `6afa3183-cc44-4209-b799-85d0c2842371` 成功，远端 run `workflow_runtime_20260708_112258_10659bfe`、prompt `d925c378-6f7d-4708-9ab5-afcbb665b8be` 成功。
  - Phase 3 输出图：`remote_sampling_parity\euler_normal_local_00001_.png`、`remote_sampling_parity\euler_normal_remote_00001_.png`、`remote_sampling_parity\seeds_2_simple_local_00001_.png`、`remote_sampling_parity\seeds_2_simple_remote_00001_.png`。
  - Phase 3 远端隐私检查：远端 jobs `remote_sampling_20260708_112122_a36c3b36_workflow_workflow_runtime_20260708_112058_5ac9197f_500` 和 `remote_sampling_20260708_112324_94f18be6_workflow_workflow_runtime_20260708_112258_10659bfe_500` 只含 `pt/json/jsonl/txt`，最近 20 分钟远端 `ComfyUI/output` 未发现 PNG/JPG/JPEG/WEBP。
  - Phase 4 本轮验证：`python -m py_compile ComfyUI-Remote-Sampling/workflow_runtime.py ComfyUI-Remote-Sampling/__init__.py` 通过。
  - Phase 4 本轮验证：`python -m unittest discover -s tests -p test_*.py -v` 通过，当前 25 个测试全部 OK。
  - Phase 4 本轮验证：本地 ComfyUI 8188 重启后 `/remote_workflow/runtime/recent?project_root=F:\TieguoDun\Remote_comfyui&limit=3` 返回 `ok=true`，最近 run 汇总包含 `workflow_status`、`workflow_report`、`run_dir` 等字段。
  - Phase 4 本轮验证：构造无效 `/remote_workflow/runtime/plan` payload，生成失败 run `workflow_runtime_20260708_113406_6e132940`，前端 Recent Runs 显示 `failed` 和错误摘要 `payload.prompt must be a ComfyUI API prompt object.`。
  - Phase 4 截图证据：`F:\TieguoDun\Remote_comfyui\remote-workflow-runtime-phase4-recent-runs.png` 和 `F:\TieguoDun\Remote_comfyui\remote-workflow-runtime-phase4-failed-run.png`。
  - Phase 5 本轮验证：`python -m py_compile tools/remote_custom_node_import_smoke.py tools/sync_remote_custom_nodes.py tools/check_remote_custom_nodes_plan.py ComfyUI-Remote-Sampling/workflow_runtime.py tests/test_post_review_hardening.py` 通过。
  - Phase 5 本轮验证：`python -m unittest discover -s tests -p test_*.py -v` 通过，当前 29 个测试全部 OK。
  - Phase 5 no-custom 实测：本地 ComfyUI 8188 使用核心节点 anima prompt 执行 `/remote_workflow/runtime/plan` + `/remote_workflow/runtime/run`，run `workflow_runtime_20260708_114325_38325b75` 返回 `remote_environment_short_circuit: true`、`remote_environment_ready: true`。
  - Phase 5 no-custom 证据：`remote_environment_report.json`、`remote_custom_node_dependency_install.json`、`remote_custom_node_import_smoke.json` 均 `skipped: true`，未生成 `custom_nodes_sync_report.json`。
  - Phase 5 单元覆盖：空 custom node plan 不调用远端工具；空 remote checker 不调用 server_exec；空 import smoke 不加载远端服务；本地包缺失的 custom node sync 会写出 `fatal` 报告和 fallback 提示。
  - Phase 6 文档进展：新增 `INSTALL.md`、`ARCHITECTURE.md`、`TROUBLESHOOTING.md`，README `Usage` 已链接三份公开文档。
  - Phase 6 文档验证：`INSTALL.md`、`ARCHITECTURE.md`、`TROUBLESHOOTING.md`、`docs/remote_sampling_usage.md`、`docs/remote_sampling_workflow_conversion_rules.md`、`docs/plan.md` 均存在。
  - Phase 6 secret scan：扫描 README、三份公开文档、`.env.example`、主要 Python 文件，未发现真实凭据；命中项均为 `password`/`token` 字段名或 owner token 配置说明。
  - Phase 7 本轮验证：`python -m py_compile` 覆盖本轮修改 Python 文件通过。
  - Phase 7 本轮验证：`python -m unittest discover -s tests -p test_*.py -v` 通过，当前 29 个测试全部 OK。
  - Phase 7 远端同步阻塞：尝试通过 `tools/sync_remote_custom_nodes.py` 同步 `ComfyUI-Remote-Sampling` 到远端时，`upload_to_company_server.py` 和 `upload_to_company_server_stream.py` 均连续报 `Error reading SSH protocol banner`。
  - Phase 7 远端连通性阻塞：直接执行 `python C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py --cmd "echo server_ok"` 仍报 `Error reading SSH protocol banner` / `No existing session`。当前阻塞在公司服务器 SSH/tunnel 层，不是项目代码层。
  - Phase 7 远端恢复：后续 `server_exec.py --cmd "echo server_ok"` 成功返回 `server_ok`，跳板 `ssh company-lab "cmd /c hostname & whoami"` 成功。
  - Phase 7 远端同步：`tools/sync_remote_custom_nodes.py transfer\phase7_remote_custom_node_plan.json --package ComfyUI-Remote-Sampling` 成功，`transfer\phase7_remote_custom_node_sync_report.json` 记录 `synced: 1`、`failed: 0`。
  - Phase 7 远端编译：远端 `.venv/bin/python -m py_compile` 覆盖远端 `__init__.py`、`workflow_runtime.py`、`remote_session.py`、`tools/remote_sampling_job_cli.py` 通过。
  - Phase 7 20-step 推荐采样器实测：run `workflow_runtime_20260708_181456_d22501a9`，prompt `c420d59c-a20e-4a48-b05b-440262ce9da3`，job `remote_sampling_20260708_181508_6df7a076_workflow_workflow_runtime_20260708_181456_d22501a9_500`，`euler/normal`，20 steps，成功输出 `phase7_euler_normal_20step_20260708_00001_.png`。
  - Phase 7 job 审计：最新 job 含 `status.json`、`events.jsonl`、`result.json`、`remote_sampling_report.txt`、`job.json`；sampling `20/20`，total elapsed `81.395s`。
  - Phase 7 缺失资源 preflight：job `phase7_missing_lora_preflight_20260708` 使用缺失 LoRA profile 失败于 preflight；远端无对应 job 文件且无 `inputs.pt`，证明 latent 上传前失败。
  - Phase 7 LoRA SHA256：`Anima/画风/nnmbpx_v1_epoch22.safetensors` 本地/远端 SHA256 均为 `bdbcb25cac7dbf5bdbc15b09dc89d1916385829c035a419570306db0b2b17106`。
  - Phase 7 远端隐私检查：最新远端 job 目录无 PNG/JPG/JPEG/WEBP，最近远端 `ComfyUI/output` 图片搜索为空。
  - Phase 7 最终验证：`python -m py_compile` 覆盖本轮修改 Python 文件通过；`python -m unittest discover -s tests -p test_*.py -v` 通过，当前 29 个测试全部 OK。
  - Phase 7 secret scan：未发现真实凭据、模型文件、图片、job/run 产物进入 git；`risk-warning` 的 `sk-w` 是误报。
- Residual risks:
  - 远端 SSH tunnel 仍可能偶发抖动，但 Phase 1 已具备 retry、tunnel restart 和失败报告基线。
  - 采样器等价性覆盖不足。
  - 自定义节点同步仍未自动解决 Linux 系统级依赖；当前策略是 dry-run dependency plan、import smoke 诊断和人工/ComfyUI Manager fallback。
  - Phase 4 截图验证时 ComfyUI 控制台存在用户 CSS、Impact-Pack、pysssss 等既有扩展的 404/preloadError；未发现新增 recent API 或 Remote Workflow Runtime JS 的关键错误。
  - 采样器等价性矩阵仍只覆盖少量组合；后续可扩展更多 sampler/scheduler。

## 下一步动作

提交并推送本次升级。推送后用 `git ls-remote origin refs/heads/main` 验证 GitHub main head。
