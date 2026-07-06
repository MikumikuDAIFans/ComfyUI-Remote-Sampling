# Post-Review Hardening Task Book

## 计划元数据

- Plan ID: `remote-workflow-runtime-post-review-hardening`
- Version: `v1`
- Last updated: `2026-07-06 21:14 +08:00`
- Canonical progress file: `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\02_long_task_books\post_review_hardening_task_book.md`
- Related handoff file: none
- Current branch: `main`
- Current active phase: `complete`
- Execution readiness: `executing`

## 目标

把上一轮已经发布的 workflow-level remote runtime 从“当前环境可用、证据充分”的状态，进一步加固为更稳健、可维护、可公开使用的 ComfyUI workflow-level remote runtime 插件。重点解决 review 中发现的高优先级问题：queue 后状态依赖浏览器、workflow-level 配置仍隐含本机默认路径、远端服务所有权不统一、custom node 同步缺少路径沙箱、custom node 发现容易误判、公开用户仍依赖 company-lab 私有 helper，以及缺少可自动回归的测试套件。

最终完成后，用户应能在不依赖浏览器持续打开的情况下获得完整 run 状态；非开发者本机路径应可通过 UI/config 明确配置；远端服务和同步操作应有明确所有权和路径边界；核心 fail-closed 规则应有自动化测试覆盖；公开用户应看到清晰的通用 SSH 使用路径。

## 范围与约束

- In scope:
  - 后端接管 queue 后的 prompt history 轮询、report parsing、complete/failed 状态写回。
  - workflow-level 配置入口：`project_root`、Python、remote executor/profile/options 等关键参数不再隐式依赖开发机默认值。
  - 统一远端服务所有权/锁：采样桥、import smoke、远端 service start/stop 使用一致 owner token 和 lock 语义。
  - custom node/resource sync 路径沙箱校验、dry-run preview、危险操作前 fail-closed。
  - custom node package 发现机制增强，减少文本扫描误判。
  - 通用 SSH executor adapter，保留 company-lab helper 作为一种 backend。
  - 最小自动化测试套件：Python unit/contract、JS syntax、关键 fail-closed fixtures。
  - README/usage/troubleshooting 更新为公开用户可执行。
- Out of scope:
  - 不承诺一次性支持所有 ComfyUI 复杂工作流；unsupported graph 仍应 fail-closed。
  - 不改变远端不得读取/保存 RGB 图片的隐私边界。
  - 不破坏 `Remote_Sampling_local` 第一个 `LATENT` 输出。
  - 不默认执行未知来源网络安装；dependency install 仍需显式授权。
  - 不提交模型、latent、图片、runtime jobs、transfer 包、日志或密钥。
- Constraints:
  - 远端写入范围仍限定在 `/home/user02/remote_ComfyUI`，除非用户明确授权。
  - GitHub 网络操作仍通过 `127.0.0.1:11809` 代理。
  - 已通过的 release 证据作为 baseline，不得回滚或削弱。
  - 每阶段完成必须更新本任务书的进度台账。

## 执行阶段

### Phase 1: Backend-Owned Run Completion

- Purpose: 消除 workflow-level 状态依赖浏览器前端的问题，让 `/remote_workflow/runtime/run` 之后的 queue、sampling、complete/failed 由后端 watcher 持久化。
- Outputs:
  - 后端 run watcher 或 worker：提交 prompt 后轮询 `/history/<prompt_id>`。
  - `workflow_status.json`、`workflow_events.jsonl`、`workflow_runtime_report.txt` 在浏览器关闭后仍能更新到终态。
  - 前端改为订阅/轮询后端状态，不再负责唯一的 completion 写回。
  - 失败时记录 prompt messages、remote sampling report、是否已 latent upload。
- Completion criteria:
  - 浏览器在 queue 后关闭或刷新，run bundle 仍最终进入 `complete` 或 `failed`。
  - 前端刷新后可通过 `run_id` 恢复查看状态。
  - 成功 run 的 upload/sampling/download 指标仍写入 manifest/report。
- Validation:
  - Unit: report parser、history status reducer、terminal-state writer。
  - Contract: `/remote_workflow/runtime/run` 返回 watcher/job id；`run_status` schema 覆盖 queued/running/complete/failed。
  - Integration: 触发 guarded run 后立即停止前端轮询，后端仍完成状态写回。
  - Real: 4-step clean workflow remote sampling 成功，远端无图片。
  - Zero-Short: 重启 ComfyUI 后能读取旧 run 的终态报告。
- Evidence:
  - `docs/remote_workflow_runtime_upgrade/evidence/post_review_hardening/phase1_backend_completion/`

### Phase 2: Workflow Runtime Configuration UX

- Purpose: 让 workflow-level 面板不再隐式依赖开发机默认路径，使公开用户和多环境用户能明确配置运行参数。
- Outputs:
  - 前端配置面板或 settings section：`project_root`、bridge Python、remote executor/backend、remote profile/options、timeouts。
  - 配置持久化到 localStorage 或后端 config 文件。
  - 所有 `plan/run/run_status/client_event` 请求携带必要 config。
  - 配置错误时 fail-closed，并给出修复提示。
- Completion criteria:
  - 不设置环境变量也能在 UI 中填写 project root 并生成正确 bundle。
  - 非默认 project root 的 `run_status` 能读到正确 run。
  - README 中有新用户配置路径。
- Validation:
  - Unit: config normalization/default merge。
  - Contract: route payload schema 增加 config 字段。
  - Integration: 使用临时 project root 生成 plan/run bundle 并读取 status。
  - Gray: 缺失/错误 project root 给出可执行错误。
  - Real: 本机 ComfyUI UI 截图证明配置入口存在。
- Evidence:
  - `docs/remote_workflow_runtime_upgrade/evidence/post_review_hardening/phase2_config_ux/`

### Phase 3: Remote Service Ownership And Path Safety

- Purpose: 统一远端服务/端口/锁所有权，并给资源和 custom node 同步加路径沙箱，防止并发互相 kill 或 plan 被篡改导致远端目录被覆盖。
- Outputs:
  - `RemoteServiceLock` / owner token 机制，采样桥、import smoke、remote service start/stop 统一使用。
  - `stop()` 只停止当前 owner 创建的服务；不会误杀用户手动服务或其他 job 服务。
  - resource/custom node sync 校验 remote path 必须位于 configured remote root 下。
  - custom node sync 替换前备份原目录，失败可恢复。
  - dry-run preview 列出将上传/删除/替换的资源和包。
- Completion criteria:
  - 并发 import smoke 与 sampling 不会互相停止服务。
  - 恶意或错误 `remote_path` 被拒绝，不会写出 remote workspace。
  - custom node sync 对已有目录有备份/rollback 信息。
- Validation:
  - Unit: path sandbox、owner token、lock acquisition/release。
  - Contract: sync report schema 包含 `dry_run`、`validated_remote_path`、`backup_path`。
  - Integration: synthetic unsafe path fail-closed。
  - Real: remote no residual listener/process/locks after success and failure.
- Evidence:
  - `docs/remote_workflow_runtime_upgrade/evidence/post_review_hardening/phase3_remote_safety/`

### Phase 4: Custom Node Discovery And Public SSH Backend

- Purpose: 降低 custom node 包误判和公开用户使用门槛。
- Outputs:
  - 本地 custom node class -> package 映射增强：优先使用 ComfyUI object_info/module/source registry，文本扫描仅作为 fallback。
  - `RemoteExecutor` abstraction：`company_lab` backend 与 generic `ssh` backend。
  - `.env.example`、README、usage 文档加入 generic SSH 配置样例。
  - ComfyUI Manager/git fallback 保持报告化，不默认执行未知网络安装。
- Completion criteria:
  - known custom node workflow 能准确定位包。
  - synthetic ambiguous class 不会静默选错包，至少 warning 或 fail-closed。
  - 无 company-lab helper 时，generic SSH backend 至少能执行 remote `echo/status` smoke。
- Validation:
  - Unit: class-to-package fixtures、ambiguous match resolver。
  - Contract: executor interface schema。
  - Integration: generic SSH dry-run/status smoke。
  - Gray: company-lab backend 仍兼容。
- Evidence:
  - `docs/remote_workflow_runtime_upgrade/evidence/post_review_hardening/phase4_discovery_ssh/`

### Phase 5: Automated Regression Suite And Release Refresh

- Purpose: 把当前文档证据中最关键的 fail-closed 规则变成自动化回归，降低后续改动破坏概率。
- Outputs:
  - `tests/` 目录或等价测试脚本。
  - 覆盖 analyzer、resource planner、custom node planner、identity guard、forbidden remote image nodes、status/event helpers。
  - JS syntax check 纳入 release command。
  - 更新 README、usage、conversion rules、task book、release evidence。
  - 最终 commit/push/remote head verification。
- Completion criteria:
  - 本地一条命令可运行核心 unit/contract tests。
  - required validation pass：py_compile、tests、node check、git diff check、local route load、至少一条 final smoke 或明确复用证据。
  - GitHub remote head 与本地最终 commit 一致。
- Validation:
  - Unit/Contract: automated tests pass。
  - Integration: local 8188 route load。
  - Real: final clean workflow smoke 或经用户批准的 equivalent evidence。
  - Release: commit/push/ls-remote。
- Evidence:
  - `docs/remote_workflow_runtime_upgrade/evidence/post_review_hardening/phase5_regression_release/`

## 决策记录

- Verified facts:
  - 当前 release commit 已达到 workflow-level runtime `pass-with-boundary`。
  - 当前前端旧 runner 面板已默认隐藏，只保留 debug flag。
  - 当前 final smoke 已证明普通 `KSampler` clean workflow 可转为 remote runtime，profile LoRA count 为 0，远端无 RGB 图片输出。
  - review 发现 queue 后 completion 仍依赖前端浏览器，这是最高优先级稳定性风险。
- Active assumptions:
  - 后端 watcher 可以通过本地 ComfyUI `/history/<prompt_id>` 稳定获得 prompt 终态和 Remote Sampling Report。
  - 第一版 generic SSH backend 只需支持命令执行和文件传输的最小接口，不必覆盖所有高级场景。
  - 自定义节点复杂依赖仍可保持 fail-closed，不需要默认自动安装未知网络依赖。
- Locked decisions:
  - 不削弱远端 RGB 图片隐私边界。
  - 不破坏 `Remote_Sampling_local` 第一个 `LATENT` 输出。
  - company-lab helper 降级为 backend adapter，不作为公开唯一执行路径。
  - 所有路径同步都必须通过 remote root sandbox 校验。
- Open questions:
  - generic SSH backend 的首批目标系统是 Linux OpenSSH + password/key 哪一种。
  - 是否需要后端 watcher 支持多用户/多浏览器 session 隔离。
  - 是否在本轮加入 cancel API，还是只保留为后续阶段。

## 关键制品与环境

- Canonical docs:
  - `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\02_long_task_books\post_review_hardening_task_book.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\plan-manifest.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_usage.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_conversion_rules.md`
- Important code or output artifacts:
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\workflow_runtime.py`: workflow-level backend orchestration.
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\web\remote_workflow_runtime.js`: official frontend panel.
  - `F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py`: remote service lifecycle.
  - `F:\TieguoDun\Remote_comfyui\tools\sync_remote_custom_nodes.py`: remote custom node write path.
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\custom_node_planner.py`: custom class package discovery.
  - `F:\TieguoDun\Remote_comfyui\tools\check_remote_resource_plan.py`: remote resource diff.
- Required commands:
  - `python -m py_compile ...`: Python syntax validation.
  - `node --check ComfyUI-Remote-Sampling\web\remote_workflow_runtime.js`: frontend syntax.
  - `git diff --check`: whitespace and patch hygiene.
  - `python C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py --cmd "<cmd>"`: current company-lab remote checks.
  - `git -c http.proxy=http://127.0.0.1:11809 -c https.proxy=http://127.0.0.1:11809 <network command>`: GitHub operations.
- Environment baseline:
  - Local project root: `F:\TieguoDun\Remote_comfyui`
  - Local ComfyUI: `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI`
  - Local ComfyUI API: `http://127.0.0.1:8188`
  - Remote workspace: `/home/user02/remote_ComfyUI`
  - Remote ComfyUI: `/home/user02/remote_ComfyUI/ComfyUI`
  - Current branch: `main`

## 进度台账

- Overall progress: Phase 1-5 全部完成；post-review hardening 已通过最终 smoke、自动回归和远端隐私检查。
- Phase 1: complete
- Phase 2: complete
- Phase 3: complete
- Phase 4: complete
- Phase 5: complete
- Validation status: Phase 1 validation passed；Phase 2 validation passed；Phase 3 validation passed；Phase 4 validation passed；Phase 5 validation passed: full py_compile、node --check、unittest、git diff --check、final smoke、remote no-image check、post-restart run_status read。
- Residual risks:
  - 后端 watcher 目前已避免同一 run 重复启动，但跨进程恢复正在 Phase 1 范围内以终态读取为主，未实现运行中断点续跑。
  - remote service owner/lock 迁移涉及真实远端进程，必须小步验证。
  - generic SSH backend 需要谨慎处理凭据和公开文档。

## 下一步动作

准备提交并推送 post-review hardening 版本。
