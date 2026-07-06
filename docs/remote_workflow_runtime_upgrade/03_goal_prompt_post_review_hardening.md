# Post-Review Hardening Goal Prompt

将下面内容复制到 `/goal` 后执行。

```text
/goal 请基于已批准的 post-review hardening task book，端到端实现 ComfyUI Remote Workflow Runtime 的后续加固优化。

Canonical task book:
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\02_long_task_books\post_review_hardening_task_book.md

Read first:
- F:\TieguoDun\Remote_comfyui\README.md
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_usage.md
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_conversion_rules.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\plan-manifest.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\evidence\phase9_release\final_smoke_report.md
- F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\workflow_runtime.py
- F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\web\remote_workflow_runtime.js
- F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\custom_node_planner.py
- F:\TieguoDun\Remote_comfyui\tools\remote_comfy_service.py
- F:\TieguoDun\Remote_comfyui\tools\sync_remote_custom_nodes.py
- F:\TieguoDun\Remote_comfyui\tools\check_remote_resource_plan.py
- F:\TieguoDun\Remote_comfyui\tools\remote_custom_node_import_smoke.py

最终目标：
把已经通过 release gate 的 workflow-level remote runtime 进一步加固为更稳健、可维护、可公开使用的插件：
- queue 后的 run completion 由后端持久化，不依赖浏览器页面持续打开。
- workflow-level UI/config 明确携带 project root、Python、remote backend/options 等配置，非默认路径可用。
- 远端服务 start/stop/import smoke/sampling 使用统一 owner/lock，避免互相误杀。
- resource/custom node sync 有 remote path sandbox、dry-run preview、备份/rollback 证据。
- custom node class -> package 发现减少文本扫描误判。
- company-lab helper 变为一个 backend adapter，同时增加 generic SSH backend 的最小可用路径。
- 核心 fail-closed 规则有自动化 unit/contract/regression 测试。

Execution contract:
- 这是执行型任务，不要停留在方案讨论。
- 严格按 task book Phase 1 到 Phase 5 推进。
- 每完成一个有意义阶段，更新 `post_review_hardening_task_book.md` 的进度台账。
- 修改用户使用方式时同步更新 README、docs/remote_sampling_usage.md、docs/remote_sampling_workflow_conversion_rules.md。
- 连接远端必须使用当前允许的 company-lab helper；新增 generic SSH backend 时不得写入真实凭据。
- 远端写入范围限定在 `/home/user02/remote_ComfyUI`，除非用户明确授权。
- GitHub 网络操作必须通过 `127.0.0.1:11809` 代理。
- 不要提交 runs/、jobs/、transfer/、模型、latent、生成图片、日志或密钥。
- 不要回滚用户已有改动；遇到非本任务相关脏文件直接忽略。

Locked decisions:
- 不削弱远端不得读取/保存 RGB 图片的隐私边界。
- 不破坏 `Remote_Sampling_local` 第一个 `LATENT` 输出。
- unsupported complex workflow 继续 fail-closed。
- 未经用户明确授权，不执行未知来源网络依赖安装。
- 路径同步必须通过 remote root sandbox 校验。

Implementation order:
1. Phase 1: Backend-Owned Run Completion。
2. Phase 2: Workflow Runtime Configuration UX。
3. Phase 3: Remote Service Ownership And Path Safety。
4. Phase 4: Custom Node Discovery And Public SSH Backend。
5. Phase 5: Automated Regression Suite And Release Refresh。

Required validation:
- `python -m py_compile` 覆盖所有修改过的 Python 文件。
- `node --check` 覆盖所有修改过的前端 JS 文件。
- 新增/更新的 unit/contract tests 全部通过。
- 本地 8188 route 和 frontend extension 加载验证。
- 后端 watcher 验证：queue 后关闭/刷新前端，run bundle 仍进入 complete/failed。
- 非默认 project root/config 验证：run_status 能读取正确 bundle。
- unsafe remote path 验证：sync 在 latent upload 前 fail-closed，且不写出 remote workspace。
- remote service ownership 验证：import smoke 与 sampling 不互相误停，结束后无残留 8197 listener/locks。
- clean workflow final smoke：普通 KSampler -> workflow-level runtime -> remote latent-only sampling -> local decode/save 成功；LoRA count 0；远端无图片。
- git diff --check 通过。
- 完成后 review、commit、push，并报告 commit hash 和 GitHub remote head。

Escalation rules:
- 只有以下情况暂停询问用户：
  - 需要破坏隐私边界，例如让远端读取/保存 RGB 图片。
  - 需要修改 `/home/user02/remote_ComfyUI` 以外的远端目录。
  - 需要破坏 `Remote_Sampling_local` LATENT 输出兼容性。
  - 需要执行未知来源网络依赖安装。
  - generic SSH backend 需要真实凭据或用户机器级配置决策。
  - 环境、权限、远端服务出现无法自行恢复的真实阻塞。

Start by:
读取 `post_review_hardening_task_book.md`，将 Execution readiness 更新为 `executing`，创建 `docs/remote_workflow_runtime_upgrade/evidence/post_review_hardening/phase1_backend_completion/`，然后开始 Phase 1。
```
