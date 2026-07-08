# 配套 /goal 提示词

```text
/goal 请基于已批准的 canonical task book，端到端推进 ComfyUI-Remote-Sampling 下一阶段升级。

Canonical task book:
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_next_upgrade_task_book.md

Read first:
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_next_upgrade_task_book.md
- F:\TieguoDun\Remote_comfyui\docs\current_project_workflow.md
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_usage.md
- F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_conversion_rules.md
- F:\TieguoDun\Remote_comfyui\README.md

Primary objective:
把当前可用的工作流级远程采样插件升级为更稳定、更可诊断、更适合公开使用的工程化系统。最终系统必须具备统一远端会话管理、可恢复资源同步、采样器等价性测试矩阵、前端运行历史和诊断体验、自定义节点远端环境管理、完整公开文档，以及端到端回归验证。

Execution contract:
- 这是执行型任务，不要停留在方案讨论。
- 严格以 canonical task book 为主计划推进。
- 每完成一个有意义阶段，更新 `docs/remote_sampling_next_upgrade_task_book.md` 的进度台账。
- 如果修改用户使用方式或行为，同步更新 `docs/current_project_workflow.md`、`docs/remote_sampling_usage.md`、`docs/remote_sampling_workflow_conversion_rules.md` 和 README。
- 不要回滚用户已有改动。
- 不提交模型、图片、latent、job、run、secret、真实凭据。
- 远端写入范围限定在 `/home/user02/remote_ComfyUI`。
- 远端不得读取或保存 RGB 输入/输出图片；远端 job 和 output 目录不得出现 PNG/JPG/JPEG/WEBP。
- `Remote_Sampling_local` 的第一个输出必须保持 `LATENT`。
- 日常使用路径必须保持：`Check & Sync -> Convert Canvas -> ComfyUI 原生运行按钮`。

Required skills and environment rules:
- 远端服务器操作必须使用 `company-lab-2-server` 技能，并通过：
  `python C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py --cmd "<cmd>"`
- GitHub fetch/push 必须使用 `git-proxy-push` 规则：
  `git -c http.proxy=http://127.0.0.1:11809 -c https.proxy=http://127.0.0.1:11809 ...`
- 本地项目根目录：
  `F:\TieguoDun\Remote_comfyui`
- 本地 ComfyUI 根目录：
  `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI`
- 远端工作区：
  `/home/user02/remote_ComfyUI`

Implementation order:
1. Phase 1: 远端会话管理与传输可靠性统一
   - 新增或重构统一 RemoteSession 管理模块。
   - 修复 `submit_remote_prompt()` 采样期间 status/events 读取不走重连机制的问题。
   - 将 job CLI 的远端命令、SFTP、下载、状态读取统一纳入 retry/backoff/keepalive。
   - 为远端路径 sandbox、断线重连、完整 `.uploading` rename、下载恢复添加单元测试。

2. Phase 2: 资源同步队列与可恢复状态
   - 为资源同步增加 per-resource 状态机。
   - 支持中断后恢复上传。
   - 增加 hash 策略配置。
   - 使用缺失 LoRA 场景做实测，确认自动同步和 SHA256 对齐。

3. Phase 3: 工作流转换与采样器等价性测试矩阵
   - 新增 sampler parity matrix 工具。
   - 至少覆盖 `euler/normal` 和一个已知风险采样器组合。
   - 输出本地/远端对照报告。
   - 确认每次转换都从当前 workflow 生成 remote prompt，而不是复用旧 workflow。

4. Phase 4: 前端运行历史与诊断体验
   - 增加 recent runs/jobs 列表。
   - 增加 status/report/job 路径快捷查看或复制。
   - 增加错误摘要复制按钮。
   - 使用浏览器自动化或截图验证 UI 不重叠、状态能实时更新。

5. Phase 5: 自定义节点同步与远端环境管理
   - 无自定义节点 workflow 直接 short circuit，不做不必要远端 custom-node 检查。
   - 增强自定义节点包打包、上传、requirements 检测、远端 import smoke。
   - 失败时提供 ComfyUI Manager fallback 或人工安装提示。

6. Phase 6: 公开仓库文档、安装流程与发布准备
   - 新增/完善 `INSTALL.md`、`TROUBLESHOOTING.md`、`ARCHITECTURE.md`。
   - README 改为清晰入口。
   - 检查 `.env.example` 和所有硬编码路径说明。

7. Phase 7: 端到端回归、实测与发布
   - 执行完整单元测试和实测矩阵。
   - 检查远端无图片输出。
   - 生成最终回归报告。
   - 提交并推送。

Required validation:
- `python -m py_compile` 覆盖所有修改过的 Python 文件。
- `python -m unittest discover -s tests -p test_*.py -v` 全部通过。
- 本地 ComfyUI 8188 至少执行：
  - 一个最小 anima smoke workflow。
  - 一个缺失 LoRA 自动同步 workflow。
  - 一个 20-step recommended sampler 质量 workflow。
  - 一个资源缺失 preflight 失败场景，确认 latent 上传前失败。
- 至少执行一组本地/远端采样器等价性对照。
- 使用 `company-lab-2-server` 检查最新远端 job 目录和远端 `ComfyUI/output` 无 PNG/JPG/JPEG/WEBP。
- 检查最新 job 的 `status.json`、`events.jsonl`、`result.json`、`remote_sampling_report.txt` 字段完整。
- 对同步后的至少一个 LoRA 执行本地/远端 SHA256 对比。
- 前端面板改动必须有截图证据或浏览器自动化验证。
- 提交前执行 secret scan，确认没有真实凭据、模型文件、图片、job/run 产物进入 git。

Definition of done:
- 统一远端 session/retry 机制落地，采样期间 status/events 读取可恢复。
- 资源同步具备 per-resource 可恢复状态和可审计报告。
- 采样器等价性矩阵存在，并明确 recommended 与 risk warning 组合。
- 前端能展示运行历史、最新 job/report/status 和可复制错误摘要。
- 自定义节点环境管理能 short-circuit 无依赖 workflow，并能对有依赖 workflow 给出明确同步/失败诊断。
- 公开文档完整：安装、架构、排障、当前工作流程。
- 全部 required validation 通过。
- 远端隐私边界保持成立。
- 本地工作树干净，提交并推送到 GitHub main。

Escalation rules:
- 只有以下情况暂停询问用户：
  - 需要破坏隐私边界，让远端读取或保存 RGB 图片。
  - 需要修改 `/home/user02` 以外的远端系统目录。
  - 需要破坏 `Remote_Sampling_local` 现有节点接口兼容性。
  - 需要安装系统级依赖或使用包管理器修改远端系统环境。
  - GitHub、远端 SSH 或 ComfyUI 服务出现连续三次无法自行恢复的真实阻塞。

Start by:
读取 `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_next_upgrade_task_book.md`，将 `Execution readiness` 更新为 `executing`，然后开始 Phase 1: 远端会话管理与传输可靠性统一。
```
