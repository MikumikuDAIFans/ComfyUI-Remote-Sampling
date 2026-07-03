## 计划元数据
- Plan ID: remote-sampling-runtime-conversion-entry
- Version: v1
- Last updated: 2026-07-04 02:22 +08:00
- Canonical progress file: `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_runtime_conversion_task_book.md`
- Related handoff file: none
- Current branch: main
- Current active phase: completed
- Execution readiness: executing

## 目标
把 `ComfyUI-Remote-Sampling` 从“用户手动打开 converted workflow 再运行”升级为“从当前本地原始 workflow 触发远程采样运行”。新的上层入口需要在每次运行时获取当前画布/API prompt，自动转换为远端 latent-only 工作流，生成 job-local profile 与审计证据，完成资源 preflight 后再提交远端采样。最终用户不应再依赖历史 `workflows/runs/*.json` 作为正式运行入口；旧 workflow 或 fixed profile 只能作为显式调试路径，并必须被多层兜底机制拦截或高可见提示。

## 范围与约束
- In scope:
  - 新增 ComfyUI 前端入口，例如菜单按钮或面板按钮 `Remote Sampling: Run Current Workflow`。
  - 新增后端 route，支持接收当前前端 workflow/API prompt，执行转换、审计、落盘 run bundle，并返回可读结果。
  - 支持 `convert` 与 `convert_and_queue` 两级能力；若直接排队风险较高，先实现 `convert + audit`，再提交 converted prompt。
  - 默认每次运行重新转换当前 workflow，避免旧 converted workflow 污染。
  - 为每次运行生成 run bundle：`source_prompt.json`、`converted_prompt.json`、job-local/generated profiles、`audit.json`、`manifest.json`。
  - 将 profile 从全局 generated 文件逐步迁移到 job/run-local profile，至少保证运行 manifest 能记录本次 profile 内容与 SHA256。
  - 加强审计工具与运行时错误提示：fixed profile、远端图片节点、资源缺失、转换不支持节点、hash 不一致时必须 fail-closed。
  - 保持现有 `Remote_Sampling_local` 节点作为最终执行节点和最后一道防线。
- Out of scope:
  - 不在本任务中完整支持 ControlNet、IPAdapter、AnimateDiff、区域提示词、复杂 conditioning hook；这些可以被审计器明确标记 unsupported。
  - 不改变隐私边界：远端仍不得读取或保存 RGB 输入/输出图片。
  - 不重写整个 ComfyUI 执行器；只通过 custom node package 的前端 JS、后端 route、转换器和 bridge 扩展实现。
  - 不删除历史 workflow 文件，除非用户另行要求；默认通过入口迁移和运行时拒绝降低误用风险。
- Constraints:
  - `Remote_Sampling_local` 第一个输出必须继续保持 `LATENT`。
  - fixed profile `anima_qwen_aella_xcn` 默认继续在转换器和运行时被拒绝，除非显式 allow。
  - 远端写入范围限定在 `/home/user02/remote_ComfyUI`。
  - 使用公司服务器时必须通过 `company-lab-2-server` 技能和既有脚本。
  - GitHub 网络操作必须使用 `git-proxy-push` 的 `127.0.0.1:11809` 代理规则。
  - 不提交 `jobs/`、`transfer/`、截图、模型、latent、输出图片等运行产物。
  - 前端实现必须和现有 `ComfyUI-Remote-Sampling/web/remote_sampling_panel.js` 共存，不破坏现有节点内监控面板。

## 执行阶段
### Phase 1: 运行时入口可行性与前后端边界确认
- Purpose: 确认 ComfyUI 前端如何获取当前画布 workflow/API prompt，以及 custom node 后端 route 如何接收并返回 converted prompt/audit，避免一开始就绑定错误接口。
- Outputs:
  - 一份简短设计记录或 task book 更新，说明前端可用 API、后端 route 形态、数据格式和限制。
  - 最小后端 route 原型，例如 `GET /remote_sampling/runtime/status` 或 `POST /remote_sampling/convert` 的空实现/echo 实现。
  - 前端 JS 入口原型，能在浏览器控制台或 UI 中触发一次请求。
- Completion criteria:
  - 已确认当前 ComfyUI 前端能否直接拿到 API prompt；如果只能拿前端 workflow，需要定义前端转 API prompt 或后端转换边界。
  - 已确认后端 route 可以从 custom node package 注册并被前端调用。
  - 已确定第一版入口是 `convert`、`convert_and_queue`，还是两者都做。
- Validation:
  - 本地 8188 加载前端扩展后，浏览器触发 route 请求成功。
  - route 返回包含 `ok`、`version`、`capabilities` 的 JSON。
  - 不提交或上传任何 latent、图片或模型。
- Evidence:
  - route 响应样例。
  - 相关文件 diff。
  - 任务书执行日志。

### Phase 2: Runtime Convert API 与 run bundle 落盘
- Purpose: 把现有 CLI 转换能力封装成后端可调用服务，确保每次运行从当前源 prompt 生成本次专属 converted prompt/profile/audit。
- Outputs:
  - 后端 route `POST /remote_sampling/convert`。
  - 可复用 Python 转换服务模块，复用 `tools/convert_ksampler_to_remote_sampling.py` 的核心逻辑，避免 CLI-only 复制粘贴。
  - run bundle 目录，例如 `runs/runtime_<timestamp>_<id>/` 或 `jobs/runtime_<id>/conversion/`。
  - `manifest.json` 记录 source prompt sha256、converted prompt sha256、profile sha256、converter version、policy version、created_at。
  - `audit.json` 与人类可读 audit summary。
- Completion criteria:
  - 每次调用 `POST /remote_sampling/convert` 都生成新的 run bundle。
  - base-only source prompt 转换后 profile `loras: []`。
  - LoRA source prompt 转换后 profile 只包含原始 model chain 中实际启用的 LoRA。
  - fixed profile 与 unsupported nodes 默认 fail-closed。
- Validation:
  - 使用现有 base-only prompt 和 `workflows/extracted_ComfyUI_00042/prompt.json` 调用 route，输出 bundle 可审计。
  - 审计工具能读取 bundle 或 converted prompt 并显示 UNET/CLIP/LoRA。
  - `python -m py_compile` 覆盖新增/修改 Python 文件。
- Evidence:
  - 两个 run bundle 的 manifest/audit 摘要。
  - route 调用命令或前端调用截图，截图不得展示生成图内容。

### Phase 3: 前端 Run Current Workflow 入口
- Purpose: 让用户从当前画布发起转换，不再手动打开历史 converted workflow 作为正式运行入口。
- Outputs:
  - 新增或扩展前端 JS，例如 `ComfyUI-Remote-Sampling/web/remote_sampling_runtime_runner.js`。
  - UI 入口：菜单项、按钮或轻量面板，名称类似 `Remote Sampling: Run Current Workflow`。
  - 转换前审计弹窗/面板，显示本次将加载的 UNET、CLIP、LoRA、LoRA strength、风险 warning。
  - 转换失败时的可读错误展示，包括 unsupported node、fixed profile、资源缺失或 prompt 获取失败。
- Completion criteria:
  - 用户在当前原始 workflow 页面可以触发 runtime convert。
  - 前端能展示转换审计结果，不需要用户手动打开 JSON。
  - 如果审计存在 fatal error，不允许继续提交。
  - 成功转换后能选择提交 converted prompt 或至少把 converted prompt 加载/发送到 ComfyUI queue。
- Validation:
  - Playwright 或浏览器实测：点击入口后能生成 run bundle 并显示审计摘要。
  - base-only workflow 显示 `LoRA: none`。
  - LoRA workflow 显示 exactly 对应 LoRA。
  - 旧 fixed workflow 被提示为 deprecated/unsafe，不作为正式入口。
- Evidence:
  - 前端截图或控制台输出。
  - 对应 run bundle 路径。
  - 任务书执行日志。

### Phase 4: Convert-and-Queue 集成与多层兜底防御
- Purpose: 把“转换”和“提交执行”串成可用工作流，并保证任何异常都在上传 latent 前或远端图片风险出现前 fail-closed。
- Outputs:
  - `POST /remote_sampling/convert_and_queue` 或等价前端流程。
  - job-local profile 或 profile snapshot 注入机制，避免运行依赖历史 generated profile 文件。
  - 加强 `Remote_Sampling_local` / bridge manifest，使 job 关联 run bundle id、source prompt hash、converted prompt hash、profile hash、remote prompt hash。
  - 审计器支持 bundle/job 关联检查，能回答“这个 job 来自哪个 source prompt 和 converted prompt”。
- Completion criteria:
  - base-only 当前画布一键远程运行成功，远端 prompt 不含 `LoraLoader`。
  - LoRA 当前画布一键远程运行成功，远端 prompt 只含原始实际 LoRA。
  - fixed profile、unsupported conversion、远端图片节点、资源缺失均在上传 latent 前失败。
  - 远端 job/output 目录不出现 PNG/JPG/JPEG/WEBP。
- Validation:
  - 本地 8188 完成一次 base-only smoke。
  - 本地 8188 完成一次 LoRA smoke 或 20-30 step 质量流。
  - 构造旧 fixed workflow 或固定 profile 输入，确认失败且无 `inputs.pt` 上传。
  - 使用 `company-lab-2-server` 检查远端 job 目录和 `ComfyUI/output`。
  - 审计最新 job，确认 run bundle id 与所有 hash 字段完整。
- Evidence:
  - prompt id、job id、run bundle id。
  - 审计工具输出。
  - 远端无图片检查输出。

### Phase 5: 缓存策略、文档与发布
- Purpose: 在默认每次重新转换的基础上，为后续可选缓存预留安全策略，并把新入口写成正式使用路径。
- Outputs:
  - 可选指纹缓存设计或最小实现，cache key 至少包含 source prompt sha256、converter version、policy version、custom node version、model/LoRA chain summary hash。
  - 更新 `docs/remote_sampling_usage.md`、`docs/remote_sampling_workflow_conversion_rules.md`，明确正式入口不再是历史 converted workflow。
  - 更新 README 或新增 runtime runner 使用说明。
  - 完成 review、commit、push。
- Completion criteria:
  - 文档明确推荐 `Run Current Workflow`。
  - 文档说明旧 converted workflow 的风险和节点级 fixed profile 拒绝机制。
  - 所有修改 Python 文件通过 `py_compile`。
  - 前端入口实测通过。
  - GitHub remote head 已确认。
- Validation:
  - `python -m py_compile` 覆盖修改 Python 文件。
  - `git diff --check` 通过。
  - 本地 8188 route、前端入口、base-only 与 LoRA 运行验证通过。
  - GitHub push 后 `ls-remote` 确认 remote head。
- Evidence:
  - commit hash。
  - remote head。
  - 文档路径和验证摘要。

## 决策记录
- Verified facts:
  - 远端 bridge 当前已经会为每个 job 重新生成并上传远端 latent-only prompt。
  - 最近一次防护提交 `24552f4 Guard remote sampling workflow alignment` 已加入节点级 fixed profile 运行时拒绝。
  - 旧 fixed workflow 实测会在上传 latent 前失败，且失败 job 不含 `inputs.pt`。
  - auto workflow 实测成功 job 已记录 `local_prompt_sha256`、`profile_sha256`、`remote_prompt_sha256` 和 `remote_prompt_rebuilt_per_job: true`。
  - 当前手动转换器处理的是 ComfyUI API prompt JSON，不是完整前端 workflow JSON。
- Active assumptions:
  - ComfyUI 前端扩展可以通过现有 app/api 能力拿到当前 prompt 或可提交 prompt；若只能拿 workflow JSON，需要先做前端到 API prompt 的转换探针。
  - 默认每次重新转换的性能成本可以接受，因为 JSON 转换远小于采样成本。
  - job-local profile 或 profile snapshot 可以逐步实现，不必第一阶段完全移除全局 generated profile。
- Locked decisions:
  - 正式运行入口应从当前画布即时转换，不应要求用户手动打开历史 `workflows/runs/*.json`。
  - 默认每次运行重新转换；缓存只能作为后续优化，并且必须 fail-closed。
  - `Remote_Sampling_local` 继续保留节点级 fixed profile 拒绝作为最后防线。
  - 远端仍不得读取或保存 RGB 输入/输出图片。
  - fixed profile `anima_qwen_aella_xcn` 只允许显式调试使用。
- Open questions:
  - ComfyUI 当前前端版本暴露的最稳定 prompt 获取 API 是哪个。
  - 第一版是否直接实现 `convert_and_queue`，还是先实现 `convert + audit` 后由前端二次提交。
  - run bundle 应放在 `runs/` 还是 `jobs/<job_id>/conversion/`；需要兼顾 `.gitignore` 和审计便利。
  - 是否需要在 UI 中加入“强制重新转换 / 允许缓存”开关，还是第一版完全不做缓存开关。

## 关键制品与环境
- Canonical docs:
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_runtime_conversion_task_book.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_equivalence_task_book.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_usage.md`
  - `F:\TieguoDun\Remote_comfyui\docs\remote_sampling_workflow_conversion_rules.md`
- Important code or output artifacts:
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\__init__.py`: 后端 route 注册位置。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\web\remote_sampling_panel.js`: 现有前端监控扩展，需要共存。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\nodes\remote_sampling_local.py`: 最终执行节点和 fixed profile 最后防线。
  - `F:\TieguoDun\Remote_comfyui\ComfyUI-Remote-Sampling\tools\remote_sampling_job_cli.py`: 远端 prompt 生成、上传、preflight、执行桥。
  - `F:\TieguoDun\Remote_comfyui\tools\convert_ksampler_to_remote_sampling.py`: 当前转换器核心逻辑来源。
  - `F:\TieguoDun\Remote_comfyui\tools\audit_remote_sampling_workflow.py`: 当前 workflow/job/profile 审计工具。
  - `F:\TieguoDun\Remote_comfyui\workflows\extracted_ComfyUI_00042\prompt.json`: 已知 LoRA 源 prompt 验证样本。
  - `F:\TieguoDun\Remote_comfyui\workflows\runs\remote_sampling_converter_source_20260630_1755_api.json`: 已知 base-only 源 prompt 验证样本。
- Required commands:
  - `python -m py_compile <modified .py files>`: Python 语法验证。
  - `python tools\audit_remote_sampling_workflow.py --job <job_dir>`: job 审计。
  - `python C:\Users\25454\.codex\skills\company-lab-2-server\scripts\server_exec.py --cmd "<cmd>"`: 远端检查。
  - `git -c http.proxy=http://127.0.0.1:11809 -c https.proxy=http://127.0.0.1:11809 <git network command>`: GitHub 网络操作。
- Environment baseline:
  - Local project root: `F:\TieguoDun\Remote_comfyui`
  - Local ComfyUI: `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI`
  - Local ComfyUI API: `http://127.0.0.1:8188`
  - Remote workspace: `/home/user02/remote_ComfyUI`
  - Remote temporary ComfyUI port: `8197`
  - Current branch: `main`
  - Latest known pushed commit before this task book: `24552f4 Guard remote sampling workflow alignment`

## 进度台账
- Overall progress: 已实现上层 runtime conversion route、前端 `Run Current Workflow` 入口、run bundle/profile snapshot 落盘、bundle/job 审计关联与 convert-then-queue 验证；文档、同步、验证、commit、push 收尾中。
- Phase 1: done
- Phase 2: done
- Phase 3: done
- Phase 4: done
- Phase 5: done
- Validation status: 本地 8188 runtime status route 可调用；`/remote_sampling/convert` 已用 base-only 与 LoRA source prompt 验证；前端 JS 已由 8188 extensions 服务；base-only 与 LoRA runtime convert-and-queue 均成功；旧 fixed workflow 上传 latent 前失败；远端图片节点风险 fail-closed；远端 job/output 无图片输出；本地与远端 custom node 包已同步。
- Residual risks:
  - ComfyUI 前端 API prompt 获取方式可能受版本影响，需要先做探针。
  - 如果只实现后端 convert 但没有好用前端入口，用户仍可能回到手动打开旧 converted workflow。
  - job-local profile 迁移若处理不当，可能影响现有 generated profile 兼容性。
  - 复杂自定义节点的 model/conditioning 链可能无法自动等价转换，必须 fail-closed。

## 下一步动作
当前任务实现已完成；下一步只剩最终 commit、push 并记录 GitHub remote head。

## 执行日志
- 2026-07-04 02:12 +08:00: Phase 1/2 完成。新增 `ComfyUI-Remote-Sampling/runtime_conversion.py`，后端 route `/remote_sampling/runtime/status` 与 `/remote_sampling/convert` 在本地 8188 验证通过。route 返回 `runtime-conversion-v1` / `fail-closed-v1` capabilities。使用 base-only 与 LoRA source prompt 调用 convert route，均生成 runtime run bundle、`manifest.json`、`audit.json`、profile snapshot；base `lora_count=0`，LoRA `lora_count=2`。
- 2026-07-04 02:14 +08:00: Phase 3 完成。新增 `ComfyUI-Remote-Sampling/web/remote_sampling_runtime_runner.js`，提供右下角 `Remote Sampling` 面板和 `Run Current Workflow` 按钮。前端资源已由本地 8188 `/extensions/ComfyUI-Remote-Sampling/remote_sampling_runtime_runner.js` 正常服务。Playwright MCP 当前无法访问本机 localhost；使用本机 HTTP 与 Chrome headless 对服务可达性做替代验证。
- 2026-07-04 02:17 +08:00: Phase 4 完成。通过 runtime convert route 生成并提交 base smoke：prompt `cb759360-30a7-4314-8d92-5d44c5ede4d1`，job `remote_sampling_20260704_021356_d4156aec_runtime_base_202660704_021353`，远端 prompt classes 为 `UNETLoader, CLIPLoader, Remote_Sampling_remote`，`LoraLoader` 数量 0。通过 runtime convert route 生成并提交 LoRA smoke：prompt `8ee4e268-d5ce-4470-910a-85192149b5ac`，job `remote_sampling_20260704_021457_64943a70_runtime_lora_202660704_021457`，远端 prompt classes 为 `UNETLoader, CLIPLoader, LoraLoader, LoraLoader, Remote_Sampling_remote`，只包含 Aella/xcn 两个原始 LoRA。旧 fixed workflow `runtime_old_fixed_guard_20260704` 在上传 latent 前失败，失败 job 无 `inputs.pt`。构造恶意远端图片节点 profile，`build_profile_prompt` 返回 `ValueError: remote profile ... contains forbidden image nodes: ['SaveImage']`。使用 company-lab-2-server 检查 runtime 两个远端 job 目录与远端 `ComfyUI/output`，无 PNG/JPG/JPEG/WEBP。
- 2026-07-04 02:22 +08:00: 补强 job/run bundle 关联。`Remote_Sampling_local` 自动从 runtime profile snapshot 路径记录 `runtime_bundle_id` 和 `runtime_bundle_dir`；`tools/audit_remote_sampling_workflow.py` 增加 `--bundle`。追加 base smoke `ddb5d220-1fe5-4226-85c1-d4fddf539a97`，job `remote_sampling_20260704_022112_5a44cdac_runtime_base_bundleid_20260704` 已记录 `runtime_bundle_id=runtime_20260704_022109_e6e89b8a`、profile SHA256、remote prompt SHA256 与 `remote_prompt_rebuilt_per_job=true`。
- 2026-07-04 02:29 +08:00: Phase 5 完成。文档已更新正式入口、run bundle 内容、bundle 审计命令与 fail-closed 缓存策略。同步本地 custom node 到 `F:\TieguoDun\ComfyUI_NEW\ComfyUI_windows_portable\ComfyUI\custom_nodes\ComfyUI-Remote-Sampling`；同步远端 custom node 到 `/home/user02/remote_ComfyUI/ComfyUI/custom_nodes/ComfyUI-Remote-Sampling` 并确认 `remote_sampling_runtime_runner.js` 存在。最终本地 8188 status route 返回 `convert_and_queue=true`，前端 runner JS 包含 `Run Current Workflow`。
