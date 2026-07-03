## 计划元数据
- Plan ID: remote-sampling-workflow-equivalence
- Version: v1
- Last updated: 2026-07-04 01:09 +08:00
- Canonical progress file: `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_equivalence_task_book.md`
- Related handoff file: none
- Current branch: main
- Current active phase: completed
- Execution readiness: executing

## 目标
让 `ComfyUI-Remote-Sampling` 的工作流转换链路达到可审计、可解释、可验证的资源等价：本地原始工作流中实际使用的 UNET、CLIP、LoRA 和采样参数，必须被准确转换为远端 latent-only profile 和远端采样 prompt。转换器不得在用户未显式要求时把工作流固定映射到带角色 LoRA 的 `anima_qwen_aella_xcn` profile。最终要能证明：原始 workflow 无角色 LoRA 时，远端 profile 和远端 prompt 也不加载角色 LoRA；原始 workflow 有 LoRA 时，远端 profile 只加载对应 LoRA 和对应强度。

## 范围与约束
- In scope:
  - 审计最近 job、现有 `workflows/runs`、generated profiles 和固定 profiles 的资源匹配关系。
  - 实现 workflow/job/profile 审计工具，能够展开每个 `Remote_Sampling_local.remote_profile` 的 UNET、CLIP、LoRA 清单。
  - 加固 `tools/convert_ksampler_to_remote_sampling.py`，避免正式转换继续误用固定 profile。
  - 增加转换后验证门禁，确保 profile 与原始 KSampler model 链等价。
  - 重新从真实本地 workflow/API prompt 生成干净的 auto-converted workflow，并完成至少一条 base-only 和一条 LoRA workflow 的对照验证。
  - 更新 `docs/remote_sampling_workflow_conversion_rules.md` 和使用文档，明确旧固定 profile 产物的风险和新推荐命令。
- Out of scope:
  - 不在本任务中扩展 ControlNet、IPAdapter、AnimateDiff、区域提示词、复杂 conditioning hook 的完整转换支持。
  - 不改变远端隐私边界：远端仍不得读取或保存 RGB 输入/输出图片。
  - 不重构整个 ComfyUI 前端 UI；仅在必要时补充审计报告显示或 CLI 输出。
  - 不删除历史测试 workflow，除非用户明确要求清理；默认只标记 deprecated/unsafe。
- Constraints:
  - 不破坏 `Remote_Sampling_local` 第一个输出仍为 `LATENT` 的兼容性。
  - 远端写入范围限定在 `/home/user02/remote_ComfyUI`。
  - 使用公司服务器时必须通过 `company-lab-2-server` 技能和既有脚本。
  - GitHub 操作必须使用本环境代理规则。
  - 对已有 dirty worktree 保持谨慎，不回滚用户改动。
  - 转换器处理对象是 ComfyUI API prompt JSON，不是前端 workflow JSON。

## 执行阶段
### Phase 1: 证据审计与污染范围冻结
- Purpose: 把“角色 LoRA 污染”从感知问题固定成可追踪证据，明确哪些 job/workflow/profile 使用了固定 profile。
- Outputs:
  - 一份审计报告，列出最近 job 的 `remote_profile`、profile LoRA 清单、远端 prompt class list。
  - 一份 `workflows/runs` 中固定 `anima_qwen_aella_xcn` profile 的文件清单。
  - 明确哪些文件是旧测试产物，哪些仍被当前实测脚本使用。
- Completion criteria:
  - 最新异常 job 已定位到具体 `job.json` 和 profile JSON。
  - 固定 profile 的 LoRA 来源已展开到具体文件路径和强度。
  - 已确认是否存在 base-only auto profile，并证明其 `loras` 为空。
- Validation:
  - 用 Python 脚本读取 `jobs/*/job.json`、`status.json` 和 profile JSON，不依赖截图判断。
  - 输出至少 10 条最近 job 的 profile 审计结果。
  - 扫描 `workflows/runs/*.json` 中所有 `Remote_Sampling_local.remote_profile`。
- Evidence:
  - `docs/reports/remote_sampling_profile_pollution_audit_YYYYMMDD.md`
  - 控制台命令和输出摘要写入报告。

### Phase 2: 审计工具实现
- Purpose: 把一次性排查沉淀成可重复工具，后续每个 workflow/job 都能检查资源等价性。
- Outputs:
  - 新增 `tools/audit_remote_sampling_workflow.py`。
  - 支持输入 converted API prompt、job directory、profile name/path 三类对象。
  - 输出 JSON 和人类可读摘要。
- Completion criteria:
  - 工具能列出每个 `Remote_Sampling_local` 的 node id、sampler_id、remote_profile、UNET、CLIP、LoRA、LoRA strength。
  - 工具能标记固定 profile `anima_qwen_aella_xcn` 为 warning，除非用户显式允许。
  - 工具能检测 profile 文件不存在、LoRA 清单为空/非空、远端 prompt class list 是否含 LoRALoader。
- Validation:
  - 对 `remote_sampling_monitor_smoke_20260701_api.json` 应报告固定 profile + Aella LoRA warning。
  - 对 `remote_sampling_converter_converted_auto_20260701_api.json` 应报告 generated profile + empty loras。
  - 对最新污染 job 应报告实际 profile 和两个 LoRALoader。
- Evidence:
  - 工具输出样例保存到 `docs/reports/remote_sampling_audit_tool_samples_YYYYMMDD.md`。

### Phase 3: 转换器防污染加固
- Purpose: 从源头避免正式转换继续生成固定 `anima_qwen_aella_xcn` 的 workflow。
- Outputs:
  - 更新 `tools/convert_ksampler_to_remote_sampling.py`。
  - 增加 `--forbid-fixed-profile` 或等价正式模式保护。
  - 增加转换输出 summary：每个 KSampler 推导出的 profile、LoRA 数量、LoRA 名称、是否固定 profile。
  - 必要时增加 `--allow-fixed-profile`，让调试流可以显式绕过保护。
- Completion criteria:
  - 默认正式转换优先使用 `--remote-profile auto`。
  - 若用户显式使用 `anima_qwen_aella_xcn`，CLI 必须给出高可见 warning。
  - 在 forbid 模式下，固定 profile 会直接失败，不生成可误用 workflow。
  - auto profile 生成后，转换器会输出 profile 文件路径和 LoRA 清单。
- Validation:
  - base-only prompt 转换生成 `loras: []`。
  - 含 Aella/xcn 的 prompt 转换生成 exactly 对应两个 LoRA。
  - 固定 profile 在 forbid 模式下失败，错误信息说明原因和替代命令。
- Evidence:
  - `python tools/convert_ksampler_to_remote_sampling.py ...` 的成功/失败样例记录。
  - 生成的 profile JSON diff 或摘要。

### Phase 4: 等价性回归与真实 workflow 重转
- Purpose: 用真实 workflow 证明远端 profile 与本地原 workflow 资源链等价。
- Outputs:
  - 至少一个 base-only auto converted workflow。
  - 至少一个含 LoRA auto converted workflow。
  - 对应 generated profile。
  - 对应 smoke/quality job。
- Completion criteria:
  - base-only workflow 的 generated profile `loras` 为空，远端 prompt 不含 `LoraLoader`。
  - LoRA workflow 的 generated profile 只包含原始 workflow 中实际启用的 LoRA。
  - 两类 workflow 均能完成远端采样、本地解码。
  - 远端 job/output 目录不出现 PNG/JPG/JPEG/WEBP。
- Validation:
  - 本地 8188 提交一次 base-only smoke。
  - 本地 8188 提交一次 LoRA smoke 或 20-30 step 质量流。
  - 用审计工具对每个 workflow 和 job 进行审计。
  - 使用 `company-lab-2-server` 检查远端图片输出和锁目录。
- Evidence:
  - job 路径、status/result/job.json 摘要。
  - 审计工具输出。
  - 必要时截图只保留节点面板，不展示生成图内容。

### Phase 5: 文档、弃用标记与发布准备
- Purpose: 让后续使用者不再误用旧固定 profile 流程，并把新门禁写进项目文档。
- Outputs:
  - 更新 `docs/remote_sampling_workflow_conversion_rules.md`。
  - 更新 `docs/remote_sampling_usage.md`。
  - 对旧固定 profile 测试 workflow 在文档中标记为 deprecated/unsafe for equivalence testing。
  - review、commit、push。
- Completion criteria:
  - 文档包含推荐转换命令、审计命令、固定 profile 风险说明。
  - 所有新增/修改 Python 文件通过 `py_compile`。
  - 关键 smoke 测试通过。
  - git 工作区可提交，推送到 GitHub。
- Validation:
  - `python -m py_compile` 覆盖修改 Python 文件。
  - 审计工具对代表性 workflow/job 通过。
  - `git diff --check` 通过。
  - GitHub remote head 确认。
- Evidence:
  - commit hash。
  - GitHub remote head。
  - 验证命令摘要。

## 决策记录
- Verified facts:
  - 最近多个 job 的 `remote_profile` 都是 `anima_qwen_aella_xcn`。
  - `anima_qwen_aella_xcn.json` 明确包含 `Anima/角色/AellaStella_v1_anima_char-000018-2c97.safetensors` 和 `Anima/画风/xcn_ogpt_v1a.safetensors`。
  - 最新异常 job 的远端 prompt class list 包含两个 `LoraLoader`。
  - `remote_sampling_converter_converted_auto_20260701_api.json` 使用 generated profile，且对应 profile `loras` 为空。
  - `ComfyUI_00042_remote_sampling_converted_auto_20260701_api.json` 使用 generated profile，且对应 profile 包含 Aella 和 xcn，符合其原始 prompt。
- Active assumptions:
  - 用户当前异常实测基于旧 fixed-profile workflow 或基于旧 smoke workflow 的参数改写。
  - 当前最重要问题是资源/profile 等价性，不是采样算法本身或 latent 传输损坏。
  - base-only 对照 workflow 可以从现有 `remote_sampling_converter_converted_auto_20260701_api.json` 或新导出的真实 base-only prompt 构造。
- Locked decisions:
  - 正式转换路径必须优先使用 `--remote-profile auto`。
  - 固定 `anima_qwen_aella_xcn` profile 只能作为明确调试/演示 profile，不能作为默认等价转换结果。
  - 需要把审计能力做成工具，而不是只靠人工打开 JSON。
  - 远端仍只做 latent sampling，不引入 VAE decode、PreviewImage、SaveImage。
- Open questions:
  - 用户接下来要审计的“当前真实工作流”具体文件路径是哪一个。
  - 是否需要把历史 fixed-profile workflow 文件迁移到 `workflows/deprecated/`，还是仅在文档中标记。
  - 是否要在节点 UI 中直接显示 profile LoRA 清单，作为额外防误用提示。

## 关键制品与环境
- Canonical docs:
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_equivalence_task_book.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_conversion_rules.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_usage.md`
- Important code or output artifacts:
  - `F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py`: 当前转换器入口。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\anima_qwen_aella_xcn.json`: 已证实会加载角色 LoRA 的固定 profile。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\anima_qwen_base.json`: base profile，无 LoRA。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\profiles\generated`: auto profile 输出目录。
  - `F:\TieguoDun\Remote_comfyui\jobs`: 本地 job 审计来源。
  - `F:\TieguoDun\Remote_comfyui\workflows\runs`: converted workflow 审计来源。
- Required commands:
  - `python -m py_compile <modified .py files>`: Python 语法验证。
  - `python tools\convert_ksampler_to_remote_sampling.py <input> <output> --remote-profile auto --sampler-prefix <prefix>`: 正式转换入口。
  - `python C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py --cmd "<cmd>"`: 远端检查入口。
  - `git -c http.proxy=http://127.0.0.1:11809 -c https.proxy=http://127.0.0.1:11809 <network command>`: GitHub 网络操作优先代理；必要时按环境诊断 fallback。
- Environment baseline:
  - Local project root: `F:\TieguoDun\Remote_comfyui`
  - Local ComfyUI: `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI`
  - Local ComfyUI API: `http://127.0.0.1:8188`
  - Remote workspace: `/home/user02/remote_ComfyUI`
  - Remote temporary ComfyUI port: `8197`
  - Current branch: `main`

## 进度台账
- Overall progress: 已完成初步人工审计，确认 fixed profile 是角色 LoRA 污染来源；任务书已进入执行状态。
- Phase 1: completed
- Phase 2: completed
- Phase 3: completed
- Phase 4: completed
- Phase 5: completed
- Validation status: 已完成 base-only 与 LoRA auto converted workflow 的真实 remote sampling 回归；远端 job/output 目录无图片文件；已完成 review、commit、push。
- Residual risks:
  - 历史测试 workflow 大量固定使用 `anima_qwen_aella_xcn`，后续实测容易继续误用。
  - 当前 auto 转换只支持有限模型链，复杂 loader 仍可能无法等价转换。
  - 如果用户提供的是前端 workflow JSON，需要先导出/提取 API prompt，不能直接套当前转换器。

## 下一步动作
当前任务已完成；后续可继续扩展更复杂 model chain、ControlNet/IPAdapter 转换支持或节点 UI 中的 profile 资源预览。

## 执行日志
- 2026-07-04 01:20 +08:00: Execution readiness 更新为 `executing`。
- 2026-07-04 01:26 +08:00: Phase 1 完成，新增污染审计报告 `docs/reports/remote_sampling_profile_pollution_audit_20260704.md`。报告确认最近 15 个 job 均使用 fixed profile `anima_qwen_aella_xcn`，远端 prompt 均含两个 `LoraLoader`；同时确认已有 base-only auto profile 的 `loras` 为空。
- 2026-07-04 01:39 +08:00: Phase 2 完成，新增 `tools/audit_remote_sampling_workflow.py` 和样例报告 `docs/reports/remote_sampling_audit_tool_samples_20260704.md`。工具已验证 fixed workflow warning、auto base empty loras、最新污染 job 两个 LoRA 展开。
- 2026-07-04 01:45 +08:00: Phase 3 完成，`tools/convert_ksampler_to_remote_sampling.py` 默认拒绝 fixed profile `anima_qwen_aella_xcn`，除非显式 `--allow-fixed-profile`；转换 summary 输出每个 sampler 的 generated profile、LoRA 数量、LoRA 名称和 fixed profile 标记。已重转 `equivalence_base_auto_20260704_api.json` 与 `equivalence_lora_auto_20260704_api.json`，base profile `loras: []`，LoRA profile exactly 包含 Aella/xcn 两个原始 LoRA。
- 2026-07-04 01:58 +08:00: Phase 4 完成。本地 8188 成功提交 base smoke `45313c6d-7b34-4537-b431-9d28bcb69710`，job `remote_sampling_20260704_012420_6c185c77_equivalence_base_smoke_202660704_012420`，远端 prompt classes 为 `UNETLoader, CLIPLoader, Remote_Sampling_remote`，`LoraLoader` 数量 0，采样 `4/4`。本地 8188 成功提交 LoRA smoke `d4b91150-f22e-464a-a159-ae89e8f8304c`，job `remote_sampling_20260704_012525_2b87f6ee_equivalence_lora_smoke_202660704_012524`，远端 prompt classes 为 `UNETLoader, CLIPLoader, LoraLoader, LoraLoader, Remote_Sampling_remote`，采样 `8/8`。使用 company-lab-2-server 检查两个远端 job 目录及远端 `ComfyUI/output` 近 60 分钟图片输出，均无 PNG/JPG/JPEG/WEBP。custom node 包已同步到本地 ComfyUI 和远端 `/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/ComfyUI-Remote-Sampling`。
- 2026-07-04 02:08 +08:00: Phase 5 完成。`python -m py_compile tools\audit_remote_sampling_workflow.py tools\convert_ksampler_to_remote_sampling.py` 通过，`git diff --check` 通过。提交 `9a3a6b5 Add workflow profile equivalence audit` 已推送到 GitHub，远端 head 确认为 `9a3a6b5a8357be3959750545d7d2cfd457736520 refs/heads/main`。
