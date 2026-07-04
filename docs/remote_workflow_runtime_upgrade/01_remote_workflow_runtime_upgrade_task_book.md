# Remote Workflow Runtime Upgrade Task Book

## 计划元数据

- Plan ID: `remote-workflow-runtime-upgrade`
- Version: `v1`
- Last updated: `2026-07-05 04:08 +08:00`
- Canonical progress file: `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\01_remote_workflow_runtime_upgrade_task_book.md`
- Related handoff file: none
- Current branch: `main`
- Current active phase: `Phase 8: Productization, Docs And Release`
- Execution readiness: `executing`

## 目标

把当前 `ComfyUI-Remote-Sampling` 从“远程采样自定义节点”升级为“工作流级远程运行插件”。最终用户打开一个全新的本地 workflow 后，可以点击工作流级按钮启用远程采样；系统会先确认本地 workflow 可运行，再分析 workflow、同步远端资源、对齐模型/LoRA/自定义节点、转换工作流、生成每次运行的审计 bundle，最后只把采样阶段交给远端执行。本地仍负责输入图片、VAE encode/decode 和最终图片保存；远端不得读取或保存 RGB 图片。

## 范围与约束

- In scope:
  - 工作流级 UI 入口和后端 orchestration route。
  - 本地 workflow 可运行性/完整性预检。
  - workflow analyzer：采样器、模型链、CLIP、VAE、LoRA、自定义节点、unsupported 节点。
  - resource planner：模型、LoRA、VAE、CLIP、自定义节点、Python 依赖的本地源路径、远端目标路径、hash/size、同步方式。
  - LoRA/model 相对路径镜像，优先保持与本地 `ComfyUI/models/...` 完全一致的相对目录。
  - custom node 同步与 Linux 兼容性验证：本地打包上传优先，失败后尝试 ComfyUI Manager/git fallback。
  - runtime conversion：每次运行从当前源 workflow/prompt 生成 converted prompt、remote execution plan、profile snapshot、audit 和 manifest。
  - workflow-level 进度 UI：本地检查、分析、资源同步、远端环境、自定义节点安装、转换、上传、采样、下载、本地解码。
  - 完整测试矩阵和证据治理。
- Out of scope:
  - 第一版不承诺支持所有复杂 ComfyUI 节点；不支持时必须 fail-closed。
  - 不在远端执行 VAE decode、PreviewImage、SaveImage 或任何 RGB 图片输出。
  - 不自动从不可信 URL 下载模型。
  - 不承诺 latent 不可逆或 prompt 语义不泄露。
- Constraints:
  - `Remote_Sampling_local` 第一个输出必须继续是 `LATENT`。
  - 远端写入范围限定在 `/home/user02/remote_ComfyUI`。
  - 连接远端必须使用 `company-lab-2-server` 技能和既有脚本。
  - GitHub 操作必须通过 `git-proxy-push` 的 `127.0.0.1:11809` 代理规则。
  - 不提交 `runs/`、`jobs/`、`transfer/`、模型、图片、latent、日志和密钥。
  - 所有资源同步和转换失败必须给出人类可执行的修复提示。

## 执行阶段

### Phase 0: Baseline Freeze And Architecture Preflight

- Purpose: 在大规模升级前冻结当前可用能力、已知风险、测试样本和远端环境，避免后续改动破坏已经证明有效的 runtime conversion。
- Outputs:
  - `baseline_report.md`：当前 commit、远端环境、可运行测试、已知风险。
  - 当前 clean animal runtime 测试、LoRA 测试、fixed workflow fail-closed 测试证据索引。
  - 模块边界设计：workflow controller、analyzer、resource planner、remote environment manager、runtime converter、sync engine。
- Completion criteria:
  - 当前 runtime convert-and-queue 能被复测。
  - 远端隐私边界仍成立。
  - 已明确哪些旧行为必须保留。
- Validation:
  - Unit: `py_compile` 当前 Python 文件。
  - Contract: `/remote_sampling/runtime/status` 返回版本和 capabilities。
  - Integration: 使用当前 runtime route 提交一条 4-step clean workflow。
  - Gray: 对比旧 fixed workflow 应继续上传 latent 前失败。
  - Real: 小动物 workflow 输出无白发女孩，远端无图片。
  - Zero-Short: 在干净浏览器刷新后确认 frontend extension 加载。
- Evidence:
  - `docs/remote_workflow_runtime_upgrade/evidence/phase0_baseline/`

### Phase 1: Workflow-Level Runtime Controller

- Purpose: 将正式入口从节点提升到工作流级插件控制器，统一承载启用远程运行、进度、错误和提交。
- Outputs:
  - 前端 workflow-level 面板或 toolbar 入口：`Enable Remote Workflow Runtime` / `Run With Remote Runtime`。
  - 后端 orchestration route，例如 `/remote_workflow/runtime/plan`、`/remote_workflow/runtime/run`、`/remote_workflow/runtime/status`。
  - 状态机定义：idle、local_preflight、analysis、resource_plan、sync、remote_env、convert、queue、sampling、decode、complete、failed。
  - 不再把历史 converted workflow 作为正式入口。
- Completion criteria:
  - 用户从当前画布触发 workflow-level plan/run。
  - UI 可以展示 run id、阶段、当前动作、错误、下一步修复建议。
  - 现有节点内监控面板不被破坏。
- Validation:
  - Unit: 前端 state reducer / backend status serializer。
  - Contract: route schema 覆盖 success、fatal、warning、progress event。
  - Integration: 当前画布触发 plan 生成 run bundle，不提交远端采样。
  - Gray: 旧 `Run Current Workflow` 入口仍可用或明确迁移为新入口兼容层。
  - Real: 本地 ComfyUI 8188 浏览器实测截图。
  - Zero-Short: 重启本地 ComfyUI 后 UI 入口自动加载。
- Evidence:
  - `evidence/phase1_controller/`

### Phase 2: Local Workflow Analyzer And Preflight

- Purpose: 在远端转换前证明本地 workflow 是可信源，并提取后续资源同步和转换所需的所有依赖事实。
- Outputs:
  - `workflow_analysis.json`。
  - 本地 workflow 可运行性检查：缺失模型、缺失节点、无效连接、不可序列化输入、unsupported sampler。
  - 采样段识别：KSampler、SamplerCustom、未来可扩展 sampler 类型。
  - 资源依赖图：UNET、CLIP、VAE、LoRA、ControlNet/IPAdapter 等扩展资源先标记 unsupported 或 planned。
  - 自定义节点清单：节点 class、包目录、可能的 requirements、是否远端需要。
- Completion criteria:
  - base-only workflow 分析为 0 LoRA。
  - LoRA workflow 分析出 exact LoRA 相对路径和强度。
  - 缺失本地模型或节点时阻止远端转换。
  - 不支持的复杂节点有明确 fatal/warning 分级。
- Validation:
  - Unit: 解析典型 prompt JSON 和 frontend workflow JSON fixtures。
  - Contract: `workflow_analysis.json` schema 固定并测试。
  - Integration: 分析结果能喂给 resource planner。
  - Gray: 与现有 `audit_remote_sampling_workflow.py` 结果交叉比对。
  - Real: 分析用户真实 LoRA workflow。
  - Zero-Short: 用最小 clean workflow 从空 run bundle 生成 analysis。
- Evidence:
  - `evidence/phase2_analyzer/`

### Phase 3: Resource Inventory And Sync Planner

- Purpose: 在上传 latent 前生成完整资源同步计划，确保本地和远端模型/LoRA/其他资源的相对目录对齐。
- Outputs:
  - `resources_plan.json`。
  - `resources_diff.json`：远端已存在、缺失、hash 不一致、需要上传、需要人工确认。
  - 模型路径规则：本地 `ComfyUI/models/<type>/<relative>` 映射到远端 `/home/user02/remote_ComfyUI/ComfyUI/models/<type>/<relative>`。
  - LoRA Manager 兼容策略：保留 `models/loras/...` 下的相对路径。
  - 上传命令建议和可执行 sync plan。
- Completion criteria:
  - 每个资源都有 kind、local_path、relative_path、remote_path、size、hash policy、sync action。
  - 缺失资源不会进入 workflow conversion。
  - hash 不一致资源默认 fail-closed，除非显式授权覆盖。
  - 大文件同步支持跳过已存在一致文件。
- Validation:
  - Unit: path mapping、relative-path normalization、hash planner。
  - Contract: `resources_plan.json` schema。
  - Integration: 使用 company-lab 脚本检查远端路径并生成 diff。
  - Gray: 构造远端已有/缺失/hash mismatch 三类 case。
  - Real: 对 Aella/xcn LoRA workflow 生成资源计划。
  - Zero-Short: 新 run bundle 中没有旧 generated profile 依赖。
- Evidence:
  - `evidence/phase3_resource_planner/`

### Phase 4: Remote Environment Manager

- Purpose: 让远端 ComfyUI 环境和本地 workflow 所需自定义节点对齐，并证明 Linux 下能启动或明确失败。
- Outputs:
  - `custom_nodes_plan.json`。
  - `remote_environment_report.json`。
  - 本地 custom node 打包上传机制。
  - 远端 dependency install 机制，优先读取 `requirements.txt` / `pyproject.toml`。
  - ComfyUI Manager/git fallback 策略。
  - 远端 startup/import smoke。
- Completion criteria:
  - 远端缺失自定义节点会先尝试本地打包安装。
  - 安装失败时尝试 Manager/git fallback 或给出人工修复命令。
  - Linux 不兼容节点不会被默默忽略，必须阻止转换。
  - 安装日志和失败原因进入 run bundle。
- Validation:
  - Unit: custom node package discovery、requirements parser、install command builder。
  - Contract: environment report schema。
  - Integration: 在 `/home/user02/remote_ComfyUI` 下安装/更新一个已知安全 custom node。
  - Gray: 构造缺失 requirements、安装失败、启动失败三类 case。
  - Real: 对用户真实 workflow 的 custom nodes 生成并执行环境计划。
  - Zero-Short: 远端新目录或清理后可重新完成节点同步。
- Evidence:
  - `evidence/phase4_remote_environment/`

### Phase 5: Runtime Conversion And Execution Plan

- Purpose: 基于已通过的 analysis/resource/environment 事实，生成本次专属本地 converted prompt、远端 latent-only prompt、profile snapshots 和审计链。
- Outputs:
  - `converted_local_prompt.json`。
  - `remote_execution_plan.json`。
  - `profiles/*.json`。
  - `manifest.json` 记录 source workflow hash、analysis hash、resources plan hash、environment report hash、converted prompt hash、remote prompt hash。
  - 画布可视化转换：采样器视觉上变为远程采样器。
- Completion criteria:
  - 每次运行重新转换或严格 hash cache 命中。
  - 不复用历史 converted workflow。
  - base-only workflow 远端 prompt 不含 LoRA。
  - LoRA workflow 远端 prompt 只含原始实际 LoRA。
  - forbidden image nodes 仍 fail-closed。
- Validation:
  - Unit: converter functions and manifest hashing。
  - Contract: manifest schema and audit schema。
  - Integration: analyzer -> resources -> environment -> conversion 串联。
  - Gray: 新旧 runtime conversion 输出差异可解释。
  - Real: clean animal workflow 和 LoRA workflow 各跑一次。
  - Zero-Short: 删除旧 run bundle 后仍可从当前画布生成新 bundle。
- Evidence:
  - `evidence/phase5_conversion/`

### Phase 6: Sync Engine, Progress UI And Failure Recovery

- Purpose: 将漫长的资源同步、安装、转换、远端执行过程做成可观察、可恢复、可诊断的用户体验。
- Outputs:
  - workflow-level `status.json` / `events.jsonl`。
  - UI 阶段进度条和子任务列表。
  - 上传/下载速度、文件级同步进度、远端安装日志、采样 step、总耗时。
  - resume/retry 设计：跳过已完成一致资源，重试失败资源。
  - failure report 自动生成。
- Completion criteria:
  - 用户能看到当前卡在哪个阶段、哪个资源、哪个命令。
  - 失败时有最小可执行修复建议。
  - 重新运行不会盲目重复上传已一致大文件。
  - 进度 UI 与后端事件一致。
- Validation:
  - Unit: event writer/reader、progress aggregator、retry planner。
  - Contract: status/events schema。
  - Integration: 模拟多个资源同步并验证 UI 进度。
  - Gray: 中断后重跑，验证已完成资源不重复上传。
  - Real: 上传至少一个 LoRA 文件并显示速度/ETA。
  - Zero-Short: 新用户打开 UI 能看懂当前阶段和失败原因。
- Evidence:
  - `evidence/phase6_progress_recovery/`

### Phase 7: Real Workflow Validation Matrix

- Purpose: 用真实用户场景证明系统达到预想：新 workflow 不被旧 LoRA 污染，LoRA 和自定义节点对齐后才远端执行，异常全部 fail-closed。
- Outputs:
  - 真实验证报告。
  - clean workflow、LoRA workflow、custom-node workflow、missing-resource workflow、incompatible-node workflow 的证据。
  - 远端无图片输出证明。
- Completion criteria:
  - clean animal workflow 输出不出现白发女孩，远端 LoRA count 为 0。
  - LoRA workflow 输出使用 intended LoRA，远端 LoRA 清单 exactly match。
  - custom-node workflow 要么成功等价执行，要么在转换前 fail-closed。
  - 缺失模型/LoRA/custom node 在 latent 上传前失败。
  - 所有成功 job 均有完整 bundle、manifest、audit、status、report。
- Validation:
  - Unit: validation fixtures can be loaded repeatedly。
  - Contract: report schema。
  - Integration: end-to-end local UI -> remote run -> local output。
  - Gray: old converted workflow cannot bypass new guardrails。
  - Real: at least three real workflows with screenshots/evidence.
  - Zero-Short: fresh workflow from scratch passes minimal remote runtime path.
- Evidence:
  - `evidence/phase7_real_validation/`

### Phase 8: Productization, Docs And Release

- Purpose: 把新定位、新入口、新限制、新安装方式写成可发布项目，而不是只保留本机实验脚本。
- Outputs:
  - README 重写：workflow-level plugin positioning。
  - 用户安装和配置文档。
  - resource sync/custom node sync 使用文档。
  - troubleshooting guide。
  - release readiness report。
  - commit and push。
- Completion criteria:
  - README 不再把项目只描述为 single custom node prototype。
  - 文档明确支持范围和 fail-closed 原则。
  - 所有 required validation 通过。
  - GitHub remote head 已确认。
- Validation:
  - Unit: final `py_compile`。
  - Contract: route/schema docs match implementation。
  - Integration: final smoke。
  - Gray: old entry compatibility check。
  - Real: final clean animal and LoRA real runs。
  - Zero-Short: fresh install/readme command review。
- Evidence:
  - `evidence/phase8_release/`

## 决策记录

- Verified facts:
  - 当前项目已经实现 runtime convert-and-queue，并验证过 clean animal workflow 不复用旧角色 LoRA。
  - 当前远端隐私边界可以做到远端不保存 RGB 输出图片。
  - 当前系统已有 job/bundle audit、status、events 和远端资源 preflight。
  - 当前系统尚未实现 workflow-level 资源同步、自定义节点安装和完整远端环境对齐。
- Active assumptions:
  - 本地 ComfyUI 是用户 workflow 编辑和最终图像保存的真源。
  - 用户愿意接受资源同步阶段较长，只要 UI 进度和失败提示清晰。
  - LoRA Manager 的主要要求是保持 `models/loras` 下的相对路径一致。
  - 自定义节点 Windows 到 Linux 的兼容性不能假设，必须实测。
- Locked decisions:
  - 系统定位升级为 workflow-level remote runtime plugin。
  - 正式运行不得依赖历史 converted workflow。
  - 默认每次 runtime conversion；缓存只能在严格 hash 对齐时启用。
  - 资源缺失、hash 不一致、自定义节点不兼容、远端图片节点风险都必须 fail-closed。
  - 自定义节点同步优先本地打包上传，失败后再尝试 Manager/git fallback。
  - 模型/LoRA 必须按相对目录镜像到远端。
- Open questions:
  - 第一批用于 custom-node real validation 的用户 workflow 是哪一个。
  - 是否允许系统在远端执行 `pip install` 过程中访问公网。
  - 是否需要支持 ControlNet/IPAdapter 作为第一版正式范围，还是先明确 unsupported。
  - 是否需要为超大模型同步加入断点续传或先用当前上传脚本实现最小版本。

## 关键制品与环境

- Canonical docs:
  - `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\plan-manifest.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\00_master_goal_index.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\01_remote_workflow_runtime_upgrade_task_book.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\02_testing_and_evidence_governance.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\03_goal_prompt.md`
- Important code or output artifacts:
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\__init__.py`: route registration.
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\runtime_conversion.py`: current runtime conversion service.
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\web\remote_sampling_runtime_runner.js`: current workflow-ish frontend entry.
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\web\remote_sampling_panel.js`: node progress panel to preserve.
  - `F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py`: converter baseline.
  - `F:\TieguoDun\Remote_comfyui\tools\audit_remote_sampling_workflow.py`: audit baseline.
  - `F:\TieguoDun\Remote_comfyui\tools\upload_to_company_server.py`: current upload helper.
- Required commands:
  - `python -m py_compile <modified python files>`: syntax validation.
  - `python C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py --cmd "<cmd>"`: remote checks.
  - `git -c http.proxy=http://127.0.0.1:11809 -c https.proxy=http://127.0.0.1:11809 <git network command>`: GitHub network operations.
- Environment baseline:
  - Local project root: `F:\TieguoDun\Remote_comfyui`
  - Local ComfyUI: `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI`
  - Local ComfyUI API: `http://127.0.0.1:8188`
  - Remote workspace: `/home/user02/remote_ComfyUI`
  - Remote ComfyUI: `/home/user02/remote_ComfyUI/ComfyUI`
  - Remote temporary port: `8197`
  - Current branch: `main`

## 进度台账

- Overall progress: Phase 0、Phase 1、Phase 2、Phase 3 已完成。Phase 4 已完成 custom node plan、远端环境检查、缺失包打包同步、依赖安装 dry-run/显式执行机制、远端 object_info import smoke。Phase 5 已完成 workflow-level convert route 和每次运行专属 conversion bundle。Phase 6 已完成 backend guarded `/remote_workflow/runtime/run`，包含资源 diff/sync、自定义节点 env/sync、依赖计划、import smoke、转换、queue-ready bundle。Phase 7 已完成缺失 LoRA fail-closed、真实 LoRA smoke、clean animal 20-step、clean formal 20-step 和远端无图片验证。当前进入 Phase 8：最终检查、提交推送。
- Phase 0: done
- Phase 1: done
- Phase 2: done
- Phase 3: done
- Phase 4: done for current supported scope
- Phase 5: done
- Phase 6: done for current guarded backend scope
- Phase 7: done for current validation slice
- Phase 8: done for current upgrade slice
- Validation status: Phase 0 unit/contract/integration/gray/real/Zero-Short validation passed. Phase 1 unit/contract/integration/gray/real/Zero-Short validation passed-with-boundary for plan-only controller. Phase 2 unit/contract/integration/gray/real/Zero-Short validation passed. Phase 3 unit/contract/integration/gray/real/Zero-Short validation passed. Phase 4 custom-node planning/check/sync, dependency dry-run, and remote import smoke validation passed. Phase 5 conversion-plan route validation passed for clean and LoRA workflows. Phase 6 guarded backend `/run` smoke, resource sync gray, and remote privacy validation passed. Phase 7 fail-closed, LoRA smoke, clean animal 20-step, and clean formal 20-step validation passed. Phase 8 final checks need rerun after latest changes.
- Residual risks:
  - 自定义节点跨 Windows/Linux 兼容性是最大风险。
  - 模型同步体积和耗时可能显著影响 UX。
  - 复杂 workflow 切分和 conditioning 链等价性需要逐步扩展，不能一开始承诺全覆盖。

## 下一步动作

执行最终 `py_compile`、`git diff --check`、同步远端包、git add、commit、push，并确认 GitHub remote head。

## 执行日志

- 2026-07-04 23:35 +08:00: 用户通过 `/goal` 批准计划体系并要求端到端执行；Execution readiness 更新为 `executing`，Phase 0 标记为 `in progress`。
- 2026-07-04 23:44 +08:00: Phase 0 完成。证据写入 `docs/remote_workflow_runtime_upgrade/evidence/phase0_baseline/`。`py_compile` 通过；本地 8188 runtime route 和 frontend extension 加载通过；clean animal 4-step runtime smoke 成功且远端 LoRA count 为 0；旧 fixed workflow 在上传 latent 前以 `FixedRemoteProfileRefused` 失败；远端 job/output 无 PNG/JPG/JPEG/WEBP；Playwright Zero-Short 快照确认 `Remote Sampling` 和 `Run Current Workflow` 可见。Phase 1 标记为 `in progress`。
- 2026-07-04 23:55 +08:00: Phase 1 完成。新增 `ComfyUI-Remote-Sampling/workflow_runtime.py`、`web/remote_workflow_runtime.js`，注册 `/remote_workflow/runtime/status` 和 `/remote_workflow/runtime/plan`。本地 8188 验证 `workflow-runtime-v1` status route、plan route、frontend JS 服务均通过；Playwright 新标签页显示 `Remote Workflow Runtime` 和 `Plan Current Workflow`，点击按钮生成 `workflow_runtime_20260704_235151_9011d0c2` plan bundle。旧 `/remote_sampling/runtime/status` 与旧 `Run Current Workflow` 面板仍可用。证据写入 `docs/remote_workflow_runtime_upgrade/evidence/phase1_controller/`。Phase 2 标记为 `in progress`。
- 2026-07-05 00:05 +08:00: Phase 2 完成。新增 `ComfyUI-Remote-Sampling/workflow_analyzer.py`，`/remote_workflow/runtime/plan` 输出升级为 `workflow-analysis-v1`。本地 fixture 验证 base workflow 资源齐全且 LoRA 为空；真实 LoRA workflow 解析出 Aella/xcn 两个 LoRA、强度和相对路径；缺失 LoRA route 返回 HTTP 400 和 `LocalResourceMissing`；Playwright 点击当前复杂 workflow 时 `ModelSamplingAuraFlow` 被标记为 `UnsupportedModelChainNode` fatal，未提交采样。证据写入 `docs/remote_workflow_runtime_upgrade/evidence/phase2_analyzer/`。Phase 3 标记为 `in progress`。
- 2026-07-05 00:14 +08:00: Phase 3 完成。新增 `ComfyUI-Remote-Sampling/resource_planner.py` 和 `tools/check_remote_resource_plan.py`。`/remote_workflow/runtime/plan` 生成 `resources-plan-v1` 和 `resources_plan_sha256`；LoRA workflow 的 UNET、CLIP、VAE、两个 LoRA 均映射到远端相同相对目录。`check_remote_resource_plan.py` 对 route-generated plan 写入 `resources_diff.json`，真实远端 5 个资源全部 `ready`；synthetic remote-missing 和 size-mismatch case 分别返回 `upload_required` 与 `size_mismatch`。证据写入 `docs/remote_workflow_runtime_upgrade/evidence/phase3_resource_planner/`。Phase 4 标记为 `in progress`。
- 2026-07-05 00:30 +08:00: Phase 4 部分完成。新增 `ComfyUI-Remote-Sampling/custom_node_planner.py`、`tools/check_remote_custom_nodes_plan.py`、`tools/sync_remote_custom_nodes.py`。`/remote_workflow/runtime/plan` 生成 `custom_nodes_plan.json` 并返回 `stage: remote_env`；真实 LoRA workflow 将 `Lora Loader (LoraManager)` 映射到 `comfyui-lora-manager`，将 `WeiLinPromptUIWithoutLora` 映射到 `WeiLin-Comfyui-Tools`。远端环境报告显示两个真实包均 `ready_for_import_smoke`；synthetic missing/incomplete/sync 灰度测试通过。证据写入 `docs/remote_workflow_runtime_upgrade/evidence/phase4_remote_environment/`。
- 2026-07-05 00:35 +08:00: Phase 5 conversion-plan route 部分完成。新增 `/remote_workflow/runtime/convert` 和 `create_workflow_runtime_conversion()`；每次请求先从当前源 prompt 生成 workflow-level plan，再生成本次专属 `converted_local_prompt.json`、`remote_execution_plan.json` 和 manifest hash。clean workflow 验证 profile LoRA count 为 0；真实 LoRA workflow 验证 profile 只包含 Aella/xcn 两个当前源 workflow LoRA。前端新增 `Convert` 按钮，Playwright 快照/截图已归档。证据写入 `docs/remote_workflow_runtime_upgrade/evidence/phase5_conversion/`。
- 2026-07-05 00:42 +08:00: Phase 6 guarded run smoke 部分完成。前端新增 `Run Guarded`，流程为当前画布 prompt -> `/remote_workflow/runtime/convert` -> `/prompt` queue。低步数 clean workflow 成功完成，prompt id `1bbf6eb8-a187-480d-8e37-baae572dfbec`，本地 job `remote_sampling_20260705_003734_07f1b496_phase6_guarded_smoke_20260705_003730_500` 记录完整 upload/sampling/download metrics；远端 job/output 无 PNG/JPG/JPEG/WEBP，8197 和 locks 清空。证据写入 `docs/remote_workflow_runtime_upgrade/evidence/phase6_progress_recovery/`。
- 2026-07-05 00:50 +08:00: Phase 7 真实验证部分完成。缺失 LoRA workflow 在 `/remote_workflow/runtime/convert` 阶段 HTTP 400 fail-closed，未创建 job；真实 LoRA workflow guarded smoke 成功，profile 只含 Aella/xcn，远端 preflight 清单精确匹配；clean 20-step guarded formal run 成功且 profile LoRA count 为 0；Phase 7 成功 job 的远端 job/output 均无 PNG/JPG/JPEG/WEBP。证据写入 `docs/remote_workflow_runtime_upgrade/evidence/phase7_real_validation/`。
- 2026-07-05 00:56 +08:00: Phase 8 当前升级切片完成。README、usage、conversion rules 更新为 workflow-level plugin 定位；`.gitignore` 排除 Playwright MCP 临时目录；本地和远端 `ComfyUI-Remote-Sampling` 包已同步；最终 `py_compile` 和 `git diff --check` 通过。证据写入 `docs/remote_workflow_runtime_upgrade/evidence/phase8_release/`。
- 2026-07-05 04:08 +08:00: 继续补齐目标缺口。新增 `tools/sync_remote_resources.py`、`tools/remote_custom_node_import_smoke.py`、`tools/install_remote_custom_node_dependencies.py`；新增 `/remote_workflow/runtime/run` guarded backend path，前端 `Run Guarded` 改为调用该 route 后再 queue。真实 smoke `guarded_v2b_smoke_20260705_034610` 成功，manifest 含 source/analysis/resources diff/env/conversion/status hash；真实 LoRA guarded prepare `workflow_runtime_20260705_040251_7f49bf25` 含 dependency dry-run hash 和 import smoke hash；缺失 LoRA 在 `/run` 阶段 HTTP 400 且未创建 job；clean animal 20-step `guarded_clean_animal20_20260705_035631` 成功，LoRA count 为 0，输出为红熊猫且远端无图片输出。
