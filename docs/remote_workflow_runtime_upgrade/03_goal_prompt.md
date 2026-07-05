# Goal Prompt

Copy this prompt into `/goal` only after the user approves the v2 plan and `Execution readiness` is updated to `approved for execution`.

```text
/goal 请基于已批准的 canonical v2 plan system，端到端实现 ComfyUI Remote Workflow Runtime Upgrade。

Canonical plan system:
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\plan-manifest.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\00_master_goal_index.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\01_remote_workflow_runtime_upgrade_task_book.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\02_testing_and_evidence_governance.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\00_preflight_governance\gate-validation-checklist.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\00_preflight_governance\risk-and-authorization-governance.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\01_target_plans\00_target_plan_index.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\02_long_task_books\00_phase_execution_matrix.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\04_phase_start_checklists\phase-start-checklists.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\05_minimal_feasibility_probe\minimal-feasibility-probe-plan.md
- F:\TieguoDun\Remote_comfyui\docs\remote_workflow_runtime_upgrade\06_pre_start_readiness_review.md

Read first:
- F:\TieguoDun\Remote_comfyui\README.md
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_runtime_conversion_task_book.md
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_equivalence_task_book.md
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_usage.md
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_conversion_rules.md
- F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\__init__.py
- F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\runtime_conversion.py
- F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\web\remote_sampling_runtime_runner.js
- F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\web\remote_sampling_panel.js
- F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\nodes\remote_sampling_local.py
- F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\tools\remote_sampling_job_cli.py
- F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py
- F:\TieguoDun\Remote_comfyui\tools\audit_remote_sampling_workflow.py

最终目标：
把当前 ComfyUI-Remote-Sampling 升级为工作流级远程运行插件。用户打开全新的本地 workflow 后，可以点击工作流级按钮启用远程运行；系统先确认本地 workflow 是可信源，再分析 workflow、生成资源计划、同步模型/LoRA/自定义节点、验证远端 Linux 环境、转换采样器为远程采样器、生成本次 run bundle 和审计证据，最后只把采样阶段交给远端执行。本地保留输入图片、VAE encode/decode、最终保存和 WebUI 编辑；远端不得读取或保存 RGB 图片。

产品级完成标准：
- 用户不需要手工维护远端 latent-only workflow。
- 正式运行默认每次从当前本地 workflow fresh conversion；严格 hash cache 只能作为优化，不能绕过 guard。
- 工作流中实际启用的模型、LoRA、自定义节点必须同步、校验并保持相对路径对齐。
- 资源缺失、hash 不一致、custom node 不兼容、unsupported conversion、stale profile/workflow、远端图片节点风险必须在 latent 上传前 fail-closed。
- workflow-level UI 必须显示或准实时显示本地预检、分析、资源同步、custom node 同步、依赖安装、import smoke、转换、上传、采样、下载、解码和失败修复建议。

Execution contract:
- 这是执行型任务，不要停留在方案讨论。
- 严格按 task book Phase 0 到 Phase 9 推进。
- 每完成一个有意义阶段，更新 canonical task book 的进度台账。
- 每个阶段开工前先检查 `04_phase_start_checklists/phase-start-checklists.md`；阶段结束时按 `00_preflight_governance/stage-completion-gate-template.md` 形成完成门证据。
- 每个阶段必须按 testing governance 执行对应 Unit / Contract / Integration / Gray / Real / Zero-Short 测试，若不适用必须写明理由；不得用 v1 证据替代 v2 Gate，只能作为 baseline。
- 修改用户使用方式时同步更新 README、docs/remote_sampling_usage.md、docs/remote_sampling_workflow_conversion_rules.md 和本计划目录。
- 连接远端必须使用 company-lab-2-server 技能和既有脚本；远端写入范围限定在 /home/user02/remote_ComfyUI。
- GitHub 网络操作必须使用 git-proxy-push 技能规则，通过 127.0.0.1:11809 代理。
- 不要提交 runs/、jobs/、transfer/、模型、latent、生成图片、日志或密钥。
- 不要回滚用户已有改动；遇到非本任务相关脏文件直接忽略。

Locked decisions:
- 系统定位为 workflow-level remote runtime plugin，不再只是一个远程采样自定义节点。
- Remote_Sampling_local 第一个输出必须继续是 LATENT。
- 正式运行不得依赖历史 converted workflow；默认每次 runtime conversion。
- 缓存只能作为严格 hash 对齐后的优化，任何 mismatch 都必须重新转换。
- 模型和 LoRA 必须按本地 ComfyUI/models 下的相对目录镜像到远端。
- 自定义节点优先本地打包上传远端并安装依赖；失败后才尝试 ComfyUI Manager/git fallback。
- Linux 兼容性不能假设，远端 startup/import smoke 不通过必须 fail-closed。
- 缺失资源、hash 不一致、自定义节点不兼容、unsupported conversion、远端图片节点风险必须在 latent 上传前失败。
- 远端 job 目录和远端 ComfyUI/output 不得出现 PNG/JPG/JPEG/WEBP。

Implementation order:
1. Phase 0: Plan Approval And Baseline Re-Freeze。
2. Phase 1: Workflow-Level Product Shell。
3. Phase 2: Source Workflow Validity And Analysis。
4. Phase 3: Resource Sync And Path Mirror。
5. Phase 4: Custom Node Environment Manager。
6. Phase 5: Fresh Conversion And Identity Guard。
7. Phase 6: Orchestration, Progress And Recovery。
8. Phase 7: Privacy And Fail-Closed Hardening。
9. Phase 8: Real Workflow Validation Matrix。
10. Phase 9: Productization, Release And Maintenance。

Required validation:
- python -m py_compile 覆盖所有修改过的 Python 文件。
- 本地 8188 route 和 frontend extension 加载验证。
- workflow-level UI 能从当前画布生成 plan/run bundle，并能显示长任务阶段进度。
- clean animal workflow：远端 LoRA count 为 0，输出不得出现白发女孩。
- LoRA workflow：远端 LoRA 清单 exactly match 本地 workflow 实际启用 LoRA。
- custom-node workflow：远端 custom node 同步和 startup/import smoke 成功，或 fail-closed。
- 缺失模型/LoRA/custom node 必须在 latent 上传前失败。
- stale converted workflow/profile bypass case 必须被拒绝或重新生成。
- workflow-level `workflow_status.json`、`workflow_events.jsonl`、report 和 manifest hash chain 完整。
- 使用 company-lab-2-server 检查远端 job 目录和远端 ComfyUI/output 无 PNG/JPG/JPEG/WEBP。
- 审计最新 job，确认 source workflow hash、analysis hash、resources plan hash、profile hash、remote prompt hash 完整。
- git diff --check 通过。
- 完成后 review、commit、push，并报告 commit hash 和 GitHub remote head。

Escalation rules:
- 只有以下情况暂停询问用户：
  - 需要破坏隐私边界，例如让远端读取/保存 RGB 图片。
  - 需要修改 /home/user02 以外的远端目录。
  - 需要破坏 Remote_Sampling_local LATENT 输出兼容性。
  - 需要联网安装未知来源模型或不可信代码。
  - 真实环境权限、依赖或远端服务出现无法自行恢复的阻塞。

Start by:
读取 canonical task book。若用户已经明确批准 v2 计划，将 Execution readiness 更新为 executing，创建 evidence/phase0_baseline，然后开始 Phase 0；若尚未批准，只做 readiness review，不进入代码实现。
```
