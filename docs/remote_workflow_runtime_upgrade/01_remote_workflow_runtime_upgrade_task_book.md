# Remote Workflow Runtime Upgrade Task Book

## 计划元数据

- Plan ID: `remote-workflow-runtime-upgrade`
- Version: `v2`
- Last updated: `2026-07-05 13:10 +08:00`
- Canonical progress file: `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\01_remote_workflow_runtime_upgrade_task_book.md`
- Related handoff file: none
- Current branch: `main`
- Current active phase: `Phase 9: Productization, Release And Maintenance`
- Execution readiness: `executing`

## Task Routing Decision

- Task type: `new-feature + architecture-upgrade + release-readiness`
- Scale mode: `Full`
- Selected path: `00 route -> 01 requirements -> 02 current-state review -> 03 technical design -> 04 construction plan -> 09 feature delivery -> 06 evidence testing -> 10 review -> 11 release -> 12 maintenance`
- Required branch skills: `project-lifecycle-workflow`, `construction-plan-system`, `long-task-planner` for ongoing progress updates.
- Requires construction plan: `yes, now normalized under this plan directory`
- Requires real test: `yes`
- Requires release gate: `yes`
- Risks:
  - Workflow conversion equivalence is the highest product risk; stale converted workflows or stale remote profiles must never be accepted silently.
  - Remote custom node Linux compatibility cannot be assumed from a working Windows local workflow.
  - Model and LoRA synchronization may involve very large files and long transfer times; progress and resumability are product requirements, not polish.
  - Privacy boundary must remain strict: remote sampling may receive latents and conditioning/model resources, but not RGB input/output images.
- Next action: review this v2 task system, then approve it for execution or request edits.
- Construction plan normalization: complete on `2026-07-05 13:20 +08:00`; new governance files are indexed in `plan-manifest.md`.

## 目标

把当前 `ComfyUI-Remote-Sampling` 正式升级为“工作流级远程运行插件”，而不是仅依赖一个远程采样节点。最终用户打开一个全新的本地 ComfyUI workflow 后，可以从工作流级 UI 点击 `Enable Remote Workflow Runtime` / `Run With Remote Runtime`。系统必须先证明本地 workflow 是可信源，再分析 workflow、生成资源计划、同步模型/LoRA/自定义节点、验证远端 Linux 环境、执行每次运行的 fresh conversion、生成审计 bundle，最后只把采样阶段交给远端执行。本地仍负责 RGB 输入、VAE encode/decode、最终图片保存和 WebUI 编辑；远端不得读取或保存 RGB 输入/输出图片。

最终体验必须满足：

- 新 workflow 不需要用户手工准备远端 latent-only workflow。
- 每次正式运行都从当前本地 workflow 生成远端执行计划；旧 converted workflow 不能绕过 guard。
- 工作流中启用的 LoRA、模型和自定义节点必须被识别、同步、校验，并保持本地/远端相对路径对齐。
- 不支持、缺失、不兼容或不可信的部分必须在 latent 上传前 fail-closed，并给出人类可执行的修复建议。
- 漫长的同步、安装、转换、上传、采样、下载过程必须有清晰 UI 进度和可追溯文件证据。

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
  - workflow-level status/events/report 文件和前端轮询显示。
  - hash identity / cache policy：允许严格命中缓存，但任何 source/resource/environment mismatch 都必须重新转换或失败。
  - review、release readiness、maintenance regression matrix。
  - 完整测试矩阵和证据治理。
- Out of scope:
  - 第一版不承诺支持所有复杂 ComfyUI 节点；不支持时必须 fail-closed。
  - 不在远端执行 VAE decode、PreviewImage、SaveImage 或任何 RGB 图片输出。
  - 不自动从不可信 URL 下载模型。
  - 不承诺 latent 不可逆或 prompt 语义不泄露。
  - 第一版不承诺全自动解决所有 custom node 的 Linux 编译依赖；可以生成明确的人工修复报告。
- Constraints:
  - `Remote_Sampling_local` 第一个输出必须继续是 `LATENT`。
  - 远端写入范围限定在 `/home/user02/remote_ComfyUI`。
  - 连接远端必须使用 `company-lab-2-server` 技能和既有脚本。
  - GitHub 操作必须通过 `git-proxy-push` 的 `127.0.0.1:11809` 代理规则。
  - 不提交 `runs/`、`jobs/`、`transfer/`、模型、图片、latent、日志和密钥。
  - 所有资源同步和转换失败必须给出人类可执行的修复提示。
  - 若需要远端执行 `pip install` 或 Manager/git fallback，必须记录命令、来源、日志和失败原因；未知来源代码不得静默执行。

## 生命周期 Gate

| Gate ID | 名称 | 通过证据 | 状态 |
|---|---|---|---|
| DEV-GATE-00 | 任务类型明确 | 本文 `Task Routing Decision` | pass |
| DEV-GATE-01 | 需求可验收 | 本文目标、范围、最终体验、完成定义 | pass-with-boundary |
| DEV-GATE-02 | 现状可信 | v1 执行日志、README、现有代码和证据目录 | pass-with-boundary |
| DEV-GATE-03 | 技术方案可执行 | v2 阶段体系、模块边界、状态机、错误模型 | drafting |
| DEV-GATE-04 | 计划可施工 | task book、testing governance、goal prompt、preflight governance、target plans、phase matrix、start checklists、MVP probes、readiness review | pass-with-boundary |
| DEV-GATE-05 | 开发改动可控 | 每阶段 change batch、py_compile、diff check | pass |
| DEV-GATE-06 | 测试证据充分 | Unit/Contract/Integration/Gray/Real/Zero-Short 证据 | pass-with-boundary |
| DEV-GATE-10 | Review 无阻塞 | review report，P0/P1 关闭或授权延期 | pass-with-boundary |
| DEV-GATE-11 | 可发布/可交付 | release readiness、commit、push、remote head | pass-with-boundary |
| DEV-GATE-12 | 可维护 | regression matrix、known limitations、next issues | pass-with-boundary |

## V2 施工阶段总览

以下 v2 阶段是后续执行的 canonical plan。下方保留的 v1 执行日志和证据只能作为 baseline，不能替代 v2 Gate。

| Phase | 名称 | 目标 | 必过测试 |
|---|---|---|---|
| 0 | Plan Approval And Baseline Re-Freeze | 冻结当前可用能力、重新确认 v2 目标与风险 | py_compile、status routes、clean smoke、远端无图 |
| 1 | Workflow-Level Product Shell | 建立真正的 workflow-level UI/后端入口和状态机 | UI load、route contract、plan/run bundle |
| 2 | Source Workflow Validity And Analysis | 证明本地 workflow 是可信源，提取模型/LoRA/custom node 依赖 | fixture、真实 LoRA、缺失资源 fail |
| 3 | Resource Sync And Path Mirror | 模型/LoRA/VAE/CLIP 等资源按相对路径对齐远端 | path/hash、remote diff、large-file skip |
| 4 | Custom Node Environment Manager | 打包/同步/安装/导入验证远端 custom nodes | package sync、dependency plan、import smoke |
| 5 | Fresh Conversion And Identity Guard | 每次从当前 workflow 转换，拒绝陈旧 profile/workflow | source hash、profile hash、LoRA exact match |
| 6 | Orchestration, Progress And Recovery | 让同步、安装、转换、采样全程可观察可恢复 | events/status、UI progress、resume/retry |
| 7 | Privacy And Fail-Closed Hardening | 系统性防止远端图片输出和 latent 前错误漏过 | forbidden nodes、remote no-image、pre-upload fail |
| 8 | Real Workflow Validation Matrix | 用真实 clean/LoRA/custom-node/异常 workflow 证明产品可靠 | clean animal、LoRA exact、custom node、missing/incompatible |
| 9 | Productization, Release And Maintenance | 文档、review、提交推送、维护矩阵 | final smoke、review、commit/push、remote head |

## V2 执行阶段详情

### Phase 0: Plan Approval And Baseline Re-Freeze

- Purpose: 在下一轮大规模升级前重新冻结当前 commit、远端环境、可运行路径、已知缺口和回滚点。
- Outputs:
  - `baseline_report.md`
  - 当前 local/remote package version、Git commit、remote head、ComfyUI 8188/8197 状态。
  - v1 已通过证据索引，标注哪些证据可继承、哪些必须重测。
- Completion criteria:
  - 当前 clean runtime smoke 可复测。
  - 远端 job/output 目录无 runtime PNG/JPG/JPEG/WEBP。
  - v2 计划由用户批准后，`Execution readiness` 更新为 `approved for execution` 或 `executing`。
- Validation:
  - Unit: `python -m py_compile` 覆盖当前 Python 文件。
  - Contract: `/remote_sampling/status`、`/remote_workflow/runtime/status` 返回版本/capabilities。
  - Integration: 4-step clean smoke 从本地 8188 到远端采样再本地 decode。
  - Gray: 已知旧 converted workflow/fixed profile 不能绕过 guard。
  - Real: clean animal 输出无白发女孩。
  - Zero-Short: 重启本地 ComfyUI 后 workflow-level JS 自动加载。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase0_baseline/`

### Phase 1: Workflow-Level Product Shell

- Purpose: 将用户入口明确提升为 workflow-level plugin，而不是要求用户手工放置远程采样节点。
- Outputs:
  - `Enable Remote Workflow Runtime` / `Run With Remote Runtime` UI 入口。
  - 后端 route：plan、prepare/run、status/events/report、cancel/retry 若可行。
  - workflow-level 状态机：local_preflight、analysis、resource_plan、resource_sync、custom_node_sync、remote_env、convert、queue、sampling、download、decode、complete、failed。
  - UI 显示 run id、阶段、当前任务、耗时、失败建议和证据路径。
- Completion criteria:
  - 从全新本地 workflow 当前画布触发 plan/run，不依赖旧 converted workflow 文件。
  - UI 可以在后端长任务执行期间持续更新阶段状态，而不是等待 fetch 完成后一次性刷新。
  - 节点内 `Remote_Sampling_local` 面板保持兼容，不破坏第一个 `LATENT` 输出。
- Validation:
  - Unit: 状态聚合和前端渲染函数。
  - Contract: route schema 覆盖 success、warning、fatal、progress event、repair hint。
  - Integration: 当前画布生成 run bundle 但不 queue。
  - Gray: 旧节点路径仍可用于调试或明确标记为 legacy。
  - Real: 浏览器截图证明 UI 入口和阶段进度。
  - Zero-Short: 清空浏览器缓存/重启 ComfyUI 后 UI 正常加载。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase1_controller/`

### Phase 2: Source Workflow Validity And Analysis

- Purpose: 在任何远端动作前证明本地 workflow 是唯一可信源，并提取完整依赖事实。
- Outputs:
  - `source_workflow.json`、`source_prompt.json`、`workflow_analysis.json`。
  - 本地缺失模型、缺失节点、断链、unsupported sampler、forbidden remote image node 的 fatal/warning 分级。
  - 采样器、模型链、CLIP/VAE、LoRA、ControlNet/IPAdapter/其他扩展资源的识别策略。
- Completion criteria:
  - base-only workflow 分析结果 LoRA count 为 0。
  - LoRA workflow 精确记录 LoRA 相对路径、strength_model、strength_clip、节点来源。
  - 缺失本地资源或 unsupported conversion 不会进入 resource sync。
- Validation:
  - Unit: prompt/workflow fixtures。
  - Contract: `workflow_analysis.json` schema。
  - Integration: analysis 可直接驱动 resource/custom-node planner。
  - Gray: 与旧 audit 工具结果交叉比对。
  - Real: 用户真实 LoRA workflow 分析。
  - Zero-Short: 新建最小 clean workflow 可生成干净 analysis。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase2_analyzer/`

### Phase 3: Resource Sync And Path Mirror

- Purpose: 让模型、LoRA、VAE、CLIP 等资源在本地/远端以相同相对目录对齐，并避免重复传输大文件。
- Outputs:
  - `resources_plan.json`、`resources_diff.json`、`resource_sync_report.json`。
  - 路径映射规则：`local ComfyUI/models/<kind>/<relative>` -> `remote /home/user02/remote_ComfyUI/ComfyUI/models/<kind>/<relative>`。
  - size/hash policy、skip/reupload/fail/manual actions。
  - 人类可执行的上传命令建议。
- Completion criteria:
  - 每个资源都有 local path、relative path、remote path、size、hash、sync action。
  - 远端缺失资源默认自动同步或在 latent 上传前失败。
  - hash/size mismatch 默认 fail-closed，除非用户明确授权覆盖。
  - LoRA Manager 管理的 LoRA 目录结构被保持。
- Validation:
  - Unit: path normalization、hash、diff planner。
  - Contract: resources schema。
  - Integration: company-lab 远端 diff 和 sync。
  - Gray: 已存在、缺失、size mismatch、hash mismatch 四类 case。
  - Real: 至少一个真实 LoRA 文件同步并记录速度/耗时。
  - Zero-Short: 删除旧 profile/cache 后仍由当前 workflow 生成资源计划。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase3_resource_planner/`

### Phase 4: Custom Node Environment Manager

- Purpose: 自动或半自动让远端 Linux ComfyUI 具备当前 workflow 需要的 custom nodes，并证明可 import。
- Outputs:
  - `custom_nodes_plan.json`、`dependency_plan.json`、`remote_environment_report.json`、`import_smoke_report.json`。
  - 本地 custom node 打包上传和远端解包机制。
  - dependency install dry-run/execute 机制。
  - ComfyUI Manager/git fallback 的报告化实现；未知来源或高风险安装必须要求明确授权。
- Completion criteria:
  - 远端缺失 custom node 先尝试本地打包同步。
  - 依赖安装命令、来源、日志和失败原因进入 bundle。
  - 远端 `object_info` import smoke 找不到目标 class 时 fail-closed。
  - Windows-only 或 Linux 不兼容节点不会被静默跳过。
- Validation:
  - Unit: custom node discovery、package builder、requirements parser。
  - Contract: custom/env report schema。
  - Integration: 同步一个真实 custom node 到远端并启动 import smoke。
  - Gray: 缺失包、缺失依赖、导入失败、启动失败。
  - Real: 用户真实 custom-node workflow 成功或 fail-closed。
  - Zero-Short: 清理远端目标包后可重新同步。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase4_remote_environment/`

### Phase 5: Fresh Conversion And Identity Guard

- Purpose: 确保每次运行的远端执行计划都来自当前本地 workflow，彻底消灭旧 workflow/旧 LoRA/profile 污染。
- Outputs:
  - `converted_local_prompt.json`、`remote_execution_plan.json`、`profiles/*.json`、`manifest.json`。
  - source workflow/prompt hash、analysis hash、resource plan hash、environment report hash、profile hash、remote prompt hash。
  - strict cache identity：只有 source/resource/environment/converter version 全部命中才允许 cache；否则重新转换。
- Completion criteria:
  - 正式 run 默认 fresh conversion。
  - base-only workflow 的 remote profile LoRA count 为 0。
  - LoRA workflow 的 remote profile LoRA list exactly match 当前本地 workflow。
  - forbidden image nodes、unsupported sampler、自定义采样链不明时 fail-closed。
- Validation:
  - Unit: converter、manifest hash、cache key。
  - Contract: manifest schema。
  - Integration: analyzer -> resource -> env -> conversion 全链路。
  - Gray: 人为放入旧 converted workflow/profile，系统拒绝或重建。
  - Real: clean animal 与 LoRA workflow 各完成一次 conversion/run。
  - Zero-Short: 删除所有旧 run bundle 后仍可从当前画布运行。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase5_conversion/`

### Phase 6: Orchestration, Progress And Recovery

- Purpose: 把漫长流程做成可观察、可恢复、可诊断的工作流级运行体验。
- Outputs:
  - workflow-level `workflow_status.json`、`workflow_events.jsonl`、`workflow_runtime_report.txt`。
  - 前端实时进度：本地预检、分析、资源同步、custom node 同步、依赖安装、import smoke、转换、上传、采样、下载、解码。
  - cancel/retry/resume 设计；已一致资源跳过重复上传。
  - 失败报告包含 stage、error code、repair hints、是否已上传 latent。
- Completion criteria:
  - UI 不再只在详情参数或请求结束后更新；阶段状态应实时或准实时刷新。
  - 资源同步速度、采样进度、下载速度、总耗时都有明确显示。
  - 中断后重新运行不会盲目重复上传已一致资源。
  - 所有失败都有可读 report 和下一步建议。
- Validation:
  - Unit: event writer/reader、progress aggregator、retry planner。
  - Contract: status/events schema。
  - Integration: 模拟多文件 sync 并验证 UI 进度。
  - Gray: 中断/失败后重跑，验证 skip/resume。
  - Real: 上传至少一个 LoRA 并截图 UI 速度/ETA。
  - Zero-Short: 新用户打开 UI 可理解当前阶段和失败原因。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase6_progress_recovery/`

### Phase 7: Privacy And Fail-Closed Hardening

- Purpose: 将隐私边界和异常防御从“约定”变成可测试的系统约束。
- Outputs:
  - forbidden remote node list and tests。
  - pre-upload failure tests for missing model/LoRA/custom node/environment。
  - remote no-image scanner。
  - privacy boundary report。
- Completion criteria:
  - 远端 workflow 不包含 VAE decode、PreviewImage、SaveImage 或 RGB image input/output 节点。
  - 缺失资源、自定义节点不兼容、hash mismatch 在 latent 上传前失败。
  - 每次真实 run 后检查远端 job 目录和远端 `ComfyUI/output`。
  - 任何隐私边界削弱都必须阻塞并询问用户。
- Validation:
  - Unit: forbidden node detector。
  - Contract: privacy report schema。
  - Integration: guarded run pre-upload failure。
  - Gray: 故意注入 forbidden node，确认 fail-closed。
  - Real: 成功 run 后远端无图片。
  - Zero-Short: 最小 workflow 也执行同样 privacy scan。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase7_privacy_fail_closed/`

### Phase 8: Real Workflow Validation Matrix

- Purpose: 用真实工作流证明系统达到用户预想，而不是只通过合成 fixture。
- Outputs:
  - `real_validation_report.md`
  - clean animal、real LoRA、custom-node、missing-resource、incompatible-node、old-workflow-bypass 六类证据。
  - 截图、prompt id、job id、run bundle id、hash chain、remote no-image output。
- Completion criteria:
  - clean animal workflow 输出不出现白发女孩，remote LoRA count 为 0。
  - LoRA workflow remote LoRA list exactly match 当前本地 workflow。
  - custom-node workflow 成功或在 latent 上传前 fail-closed。
  - 旧 converted workflow/profile 不能污染新 workflow。
  - 所有成功 job 有完整 audit bundle。
- Validation:
  - Unit: validation fixtures reload。
  - Contract: validation report schema。
  - Integration: local UI -> remote guarded run -> local decode/save。
  - Gray: old converted workflow bypass attempt。
  - Real: 至少三条真实 workflow，含截图证据。
  - Zero-Short: 从全新 workflow 开始完成一次远程运行。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase8_real_validation/`

### Phase 9: Productization, Release And Maintenance

- Purpose: 把系统作为可公开维护的 workflow-level plugin 交付，而不是本机实验工程。
- Outputs:
  - README、usage、conversion rules、troubleshooting、limitations、release readiness。
  - review report、test execution report、maintenance/regression matrix。
  - commit、push、GitHub remote head verification。
- Completion criteria:
  - 文档明确项目定位为 workflow-level remote runtime plugin。
  - 安装、配置、资源同步、自定义节点同步、失败修复路径清楚。
  - P0/P1 review findings 关闭或用户授权延期。
  - GitHub main 分支 head 与本地 commit 一致。
- Validation:
  - Unit: final `py_compile`。
  - Contract: docs match route/schema。
  - Integration: final guarded smoke。
  - Gray: legacy/debug entry compatibility。
  - Real: final clean animal + LoRA + custom-node matrix。
  - Zero-Short: fresh install/readme command review。
- Evidence: `docs/remote_workflow_runtime_upgrade/evidence/phase9_release/`

## V1 基线阶段详情（保留证据，不作为 V2 完成状态）

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

### Legacy Phase 7: Real Workflow Validation Matrix

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

### Legacy Phase 8: Productization, Docs And Release

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

- Overall progress: v2 长程任务体系已建立并进入执行。v1 已实现并验证的 guarded runtime 能力作为 baseline 继承；本轮已补齐 workflow-level status/events/report helper、run_status route、client_event 写回 route、前端 plan-first polling 和 queue-after history aggregation。Phase 1/Phase 6 的准备、queue、sampling、complete 关键状态现在都能进入 workflow-level bundle；Phase 7 stale workflow/profile bypass、missing resource fail-closed、remote profile forbidden image gate 均已通过验证。仍需继续扩展完整真实 workflow matrix、custom-node/incompatible cases 和 release gate。
- Phase 0 Plan Approval And Baseline Re-Freeze: pass
- Phase 1 Workflow-Level Product Shell: pass-with-followup
- Phase 2 Source Workflow Validity And Analysis: pass-with-boundary
- Phase 3 Resource Sync And Path Mirror: pass-with-boundary
- Phase 4 Custom Node Environment Manager: in progress
- Phase 5 Fresh Conversion And Identity Guard: pass-with-followup
- Phase 6 Orchestration, Progress And Recovery: in progress
- Phase 7 Privacy And Fail-Closed Hardening: in progress
- Phase 8 Real Workflow Validation Matrix: pass-with-boundary
- Phase 9 Productization, Release And Maintenance: pass-with-boundary
- Validation status: v1 evidence exists and may be reused as baseline only after Phase 0 re-freeze. v2 Phase 1/Phase 6 backend contract、local UI、真实低步数 guarded smoke 均通过：`py_compile`、`node --check`、`git diff --check` 通过；plan-only probe 生成 `workflow_status.json`、`workflow_events.jsonl`、`workflow_runtime_report.txt` 并在 manifest 中写入 events/report hash；本地 ComfyUI 8188 已加载 `run_status` 和 `client_event` routes，workflow-level 面板截图和 fail-closed UI 截图已归档；远端包已同步；真实 run `workflow_runtime_20260705_121532_7fd71d73` / prompt `c125bf4d-bcdf-414a-b825-8256fe572499` 成功，底层 job 4/4 step 完成，`client_event` 将 upload/sampling/download 指标写回 workflow status/events/report，远端 job/output 无图片。Phase 7 stale bypass route-level probe 通过：旧 clean plan run_id 搭配不同 LoRA prompt 返回 HTTP 400 / `SourcePromptHashMismatch`，未创建 `resources_diff.json` 或 `converted_local_prompt.json`。Phase 7 missing resource probe 通过：缺失 UNET 返回 HTTP 400 / `LocalResourceMissing`，未创建 `resources_diff.json`、`converted_local_prompt.json` 或底层 job。Phase 7 remote profile privacy gate 通过：clean workflow 的 remote profile class list 为 `UNETLoader/CLIPLoader/Remote_Sampling_remote` 且 forbidden count 0；synthetic malicious profile 中 `VAEDecode/SaveImage` 被识别。
- Residual risks:
  - 自定义节点跨 Windows/Linux 兼容性是最大风险。
  - 模型同步体积和耗时可能显著影响 UX。
  - 复杂 workflow 切分和 conditioning 链等价性需要逐步扩展，不能一开始承诺全覆盖。

## 下一步动作

当前 release gate 已通过当前支持范围的验证。下一步是进入后续维护路线：通用 SSH backend、超大资源断点续传、cancel/retry UI 和更多复杂 workflow fixture。

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
- 2026-07-05 04:16 +08:00: v2 计划体系进入执行。当前优先缺口为 workflow-level 长任务可观测性：为 `/remote_workflow/runtime/run` 的本地预检、资源检查/同步、自定义节点检查/同步、依赖计划、import smoke、转换和 queue-ready 阶段补齐 `workflow_status.json`、`workflow_events.jsonl`、report 和前端轮询读取入口。
- 2026-07-05 04:24 +08:00: Phase 1/Phase 6 可观测性基础完成一轮实现。新增 workflow-level status/events/report helper、manifest observability hash、`/remote_workflow/runtime/run_status` route、existing-plan guarded run 复用路径；前端 `Run Guarded` 改为先 `/plan` 获取 `run_id`，轮询 `run_status`，再调用 `/run` 复用该 plan 并 queue converted prompt。验证：`py_compile`、`node --check`、`git diff --check` 通过；plan-only contract probe `workflow_runtime_20260705_042216_2f9bf94b` 生成 4 条 events、report 和 manifest events/report hash。证据见 `evidence/phase6_progress_recovery/workflow-status-events-contract-20260705.md`。
- 2026-07-05 04:28 +08:00: 本地 UI 验证完成。更新后的 custom node 已同步到本地 ComfyUI 并重启 8188；API readiness 返回 `ready 2361 True True True`，确认 `workflow_run_status_route=True`。Playwright 截图 `workflow-runtime-panel-20260705.png` 和 `workflow-runtime-guarded-status-20260705.png` 已归档。当前 AuraFlow 画布触发 `Run Guarded` 后 fail-closed，生成 run `workflow_runtime_20260705_042623_165ae28d`，含 4 条 workflow events、report、manifest events/report hash，未进入远端采样。
- 2026-07-05 04:34 +08:00: 远端同步和真实 smoke 通过。当前 `ComfyUI-Remote-Sampling` 包已同步到远端 `/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/ComfyUI-Remote-Sampling`，grep 确认包含 `run_status` route。低步数 clean guarded run `workflow_runtime_20260705_042940_2e199900` 成功，prompt id `1ae17b5e-8c90-446e-86a6-25ef051c62e8`，底层 job `remote_sampling_20260705_043003_c7affb69_workflow_status_real_smoke_20260705_0430_500` 上传 257978 bytes、采样 4/4、下载 394786 bytes。workflow bundle 含 15 条 events、report、status/events/report hash；远端 job 目录和远端 `ComfyUI/output` 无 PNG/JPG/JPEG/WEBP，8197 无监听，locks 清空。残余缺口：workflow-level status 当前停在 `queue`，queue 后采样/下载/完成仍需要从 prompt/job 进度聚合回 workflow 面板。
- 2026-07-05 04:40 +08:00: 前端 queue 后聚合已实现。`Run Guarded` 在提交 converted prompt 后继续轮询 `/history/<prompt_id>`；运行中显示 workflow-level `sampling` 状态，完成后从 `Remote Sampling Report` 文本解析并显示 job id、总耗时、upload/sampling/download 指标。最新包已同步到本地和远端，远端 grep 确认 `Guarded remote workflow run completed.` 文案存在。残余缺口：这些 queue 后指标目前是前端从 ComfyUI history 观察，不会写回 workflow-level `workflow_status.json`。
- 2026-07-05 12:19 +08:00: queue 后持久化缺口完成。新增 `POST /remote_workflow/runtime/client_event`，前端在 queue、sampling、complete、failed 时回写 workflow-level status/events/report。契约探针确认 `workflow_status.json` 更新到 `complete` 且 manifest status/events/report hash 刷新。真实 client_event smoke `workflow_runtime_20260705_121532_7fd71d73` 成功，prompt id `c125bf4d-bcdf-414a-b825-8256fe572499`，底层 job `remote_sampling_20260705_121605_b72e4fcf_workflow_client_event_smoke_20260705_0445_500` 采样 4/4，upload/sampling/download 指标已写回 workflow status details；远端 job/output 无图片，8197 无监听，locks 清空。
- 2026-07-05 12:25 +08:00: Phase 7 stale workflow/profile bypass guard 完成。`_load_plan_for_run()` 现在在复用 `run_id` 时校验 supplied prompt/workflow hash 是否匹配 manifest 中的 source hash，不匹配则以 `SourcePromptHashMismatch` / `SourceWorkflowHashMismatch` 在 `local_preflight` fail-closed。函数级 probe `workflow_runtime_20260705_122113_f2d3b32b` 与 route 级 probe `workflow_runtime_20260705_122317_81f9a3c1` 均证明 mismatch 不会创建 `resources_diff.json`、`converted_local_prompt.json` 或远端 job。远端包已同步并 grep 确认包含 `SourcePromptHashMismatch`。证据见 `evidence/phase7_privacy_fail_closed/stale-workflow-profile-bypass-20260705.md`。
- 2026-07-05 12:27 +08:00: Phase 7 missing resource fail-closed 通过。将 clean animal prompt 的 UNET 文件名替换为不存在的 `__codex_missing_unet_phase7_20260705__.safetensors` 后调用 `/remote_workflow/runtime/run`，返回 HTTP 400 / `LocalResourceMissing`，run `workflow_runtime_20260705_122636_257bebbc` 生成诊断 status/events/report，但未创建 `resources_diff.json`、`converted_local_prompt.json` 或任何 `missing_resource_phase7_20260705` 底层 job。证据见 `evidence/phase7_privacy_fail_closed/missing-resource-fail-closed-20260705.md`。
- 2026-07-05 12:34 +08:00: Phase 7 remote profile forbidden image gate 通过。修正 privacy gate 边界：本地 converted prompt 允许保留 `VAEDecode/SaveImage`，真正检查 generated remote profile 可重建出的远端采样 prompt。clean workflow conversion `workflow_runtime_20260705_123226_ca571890` 的 remote class list 为 `UNETLoader/CLIPLoader/Remote_Sampling_remote`、forbidden count 0；synthetic malicious profile 中 `VAEDecode/SaveImage` 被识别为 forbidden。最新包已同步到本地和远端，远端 grep 确认包含 `remote_profile_prompt_reconstruction`。证据见 `evidence/phase7_privacy_fail_closed/remote-profile-forbidden-image-gate-20260705.md`。
- 2026-07-05 13:20 +08:00: 使用 `project-lifecycle-workflow` 和 `construction-plan-system` 将 v2 升级整理为 Full Mode 长程任务体系。新增 `00_preflight_governance/`、`01_target_plans/`、`02_long_task_books/00_phase_execution_matrix.md`、`04_phase_start_checklists/`、`05_minimal_feasibility_probe/`、`06_pre_start_readiness_review.md`；manifest 和 README 已接入这些治理文件。DEV-GATE-04 更新为 `pass-with-boundary`，下一步保持在 Phase 7/8/9 执行链上继续验证与发布准备。
- 2026-07-05 13:35 +08:00: Phase 8 真实验证矩阵完成汇总。新增 `evidence/phase8_real_validation/real_validation_report.md` 和 `phase_summary.md`，覆盖 clean animal、real LoRA、custom-node、missing-resource、incompatible-node、stale-bypass、remote privacy 七类场景。Phase 8 gate 结论为 `pass-with-boundary`；Phase 9 release readiness 可以开始。
- 2026-07-05 13:45 +08:00: Phase 9 release readiness 启动。`py_compile`、`node --check`、`git diff --check` 通过；本地 8188 `/object_info` 和 `/remote_workflow/runtime/status` 加载正常；远端轻量检查显示 8197 无监听、无残留 ComfyUI/submit 进程、locks 清空、最近 180 分钟远端 `ComfyUI/output` 无图片输出。证据写入 `evidence/phase9_release/release_readiness_report.md`。剩余 gate：review、是否补 final smoke、commit/push/remote head。
- 2026-07-05 13:55 +08:00: Phase 9 review 完成。新增 `evidence/phase9_release/review_report.md`，当前 diff 未发现 P0/P1；P2/P3 后续项包括通用 SSH backend、超大资源断点续传、cancel/retry UI 和更多 workflow fixture。release readiness 中 code review 状态更新为 `pass-with-boundary`。
- 2026-07-05 13:10 +08:00: Phase 9 final guarded smoke 通过。重启本地 ComfyUI 后使用普通 `KSampler` clean animal 源 prompt 触发 workflow-level `/remote_workflow/runtime/run`，run `workflow_runtime_20260705_130317_c9da533c` / prompt `fb176de6-6085-44e1-835c-28ebbb11cd3f` 成功；profile LoRA count `[0]`，remote prompt forbidden image node count `0`，workflow status `complete`，输出为红熊猫且无白发女孩特征；远端 job/output 无 PNG/JPG/JPEG/WEBP，8197 无监听，locks 清空。证据见 `evidence/phase9_release/final_smoke_report.md`。
