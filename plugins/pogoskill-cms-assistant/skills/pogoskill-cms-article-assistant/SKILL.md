---
name: pogoskill-cms-article-assistant
description: 将一篇 PoGoskill 台湾站 DOCX 完整处理为图片已单独发布、通过机械校验并经 CMS 回读审查的草稿。适用于端到端文章任务；禁止生成或发布文章、删除或修改无法确认归属的旧文章。
---

# PoGoskill CMS 完整文章助手

负责从 DOCX 到可审查 CMS 草稿的完整闭环。不要只生成局部 HTML、只上传图片，或在尚未获得 CMS 回读证据时结束。

开始时完整读取并依次使用：

1. [CMS 真实执行与证据契约](references/execution-contract.md)；
2. `../pogoskill-cms-publisher/SKILL.md` 与其中要求的 HTML/CMS 契约；
3. `../pogoskill-cms-image-pipeline/SKILL.md` 与图片契约；
4. `../pogoskill-cms-reviewer/SKILL.md` 与审查契约；
5. [完成门槛](references/completion-gates.md)。

执行证据契约优先于口头进度：没有真实工具调用、API 响应和写后回读时，不得声称 CMS 无法访问、正在执行或已经上传。

## API Key 首次设置

API Key 由统一凭据脚本管理：优先使用稳定的 DPAPI 加密、当前 Windows 用户专属本地存储，并兼容 Windows Credential Manager。插件升级不会删除该存储。任务开始时先从当前已加载插件根目录运行 `scripts/cms-check-api-key.ps1`；禁止复用旧消息中带 `1.0.0+codex...` 的缓存路径。只有脚本确认两个位置都不存在时，才允许再次索取 Key。看到 Windows `1312` 不能直接判定 Key 丢失或阻断任务，检查脚本也绝不输出密钥内容。

首次确实没有 CMS Key 时，采用“先启动命令、后复制”的交互流程。Agent 必须创建可持续跟踪的终端运行会话，在当前插件根目录运行：

```powershell
pwsh -NoProfile -File scripts/cms-save-api-key.ps1
```

脚本会自动打开独立的系统 PowerShell 窗口，并验证可见控制台及子进程就绪信号。禁止用 Codex 内置终端面板代替，不让使用者手工打开 PowerShell 或输入缓存长路径。只有收到窗口就绪信号才说“系统窗口已打开”；这还不表示 Key 已保存。此时让使用者复制 Key，回到终端直接按 Enter；脚本随后读取剪贴板，写入 DPAPI 加密且仅当前 Windows 用户可读的本地存储，并在可用时同时写入 Windows Credential Manager，最后清空剪贴板。用户在独立系统窗口完成保存后，Agent 再从同一插件根目录运行 `cms-check-api-key.ps1`；检查报告可用后才算完成。不要让使用者把 Key 粘贴进终端、发到聊天、写进命令行、文章文件或日志。

如果 Agent 已经确认使用者提前复制完 Key，并且要通过非交互终端自动执行，则使用：

```powershell
pwsh -NoProfile -File scripts/cms-save-api-key.ps1 -FromClipboard
```

`-FromClipboard` 会立即读取剪贴板，不等待 Enter。只有使用者明确要求键盘隐藏输入时才使用 `-Prompt`；默认禁止用 `-Prompt` 代替剪贴板流程。若 Credential Manager 返回 `1312`，但脚本明确显示受保护备用存储保存成功，则继续运行检查脚本，不得再次询问。若检查失败，先核对保存和检查是否来自同一当前插件根目录、进程是否确实退出以及 `%LOCALAPPDATA%\PoGoskillCMS\OpenAPI.v1.dat` 是否存在；完成诊断前不得要求再次输入。

## 强制执行闭环

1. 建立当前文章独立工作目录，保留源 DOCX、结构 JSON、HTML、图片 manifest、API payload/response 和检查结果。先从 DOCX 提取参考文章 URL、CMS 页面 ID 或现有 HTML；至少有一种参考样式。缺失时不得自行设计页面，应明确报告输入缺少参考样式。
2. 先用 `inspect-docx-structure.py` 读取全文、表格与图片关系，按文档出现位置建立“源图片账本”，列出每一次图片引用、章节、FAQ 和 Guide 文件名；不得只阅读开头或摘要。重复引用同一媒体文件也按两个出现位置记录，禁止去重后静默漏图。
3. 实时查询站点、模板、分类、作者、产品、相关文章和 URL 冲突。
4. 按 Publisher 契约生成完整 HTML。下载区与 Buy Box 必须直接复制资产文件，不得手写简化。源 DOCX／参考样式明确存在并排双图时，使用对应语言 Publisher 的 `assets/paired-image-box.html`，保留左右顺序和每张图下方说明，不得拆成无关单图或让桌面／手机布局溢出。普通表格合理宽度、居中且不滚动；只有实际过宽的多列或长文本表格才启用横向滚动。
   Guide／操作步骤的文字属于不可编辑来源：允许按固定结构加入 `label` 和对源文已有短标题加粗，但后续正文必须逐字、原序保留；没有源文短标题时不得自行创造。任何改写、润色、缩写、补写、合并或拆分都必须在上传前恢复为原文。
5. 按 Image Pipeline 完成所有正文图。新上传正文图必须真实嵌入 DOCX 的目标位置；按该位置逐一提取、转换和回填，任何无法处理的图片仍须保留在账本中并阻断流程，禁止从 manifest 删除。Guide 图不要求嵌入，只读取 DOCX 对应位置写明的 CMS 准确文件名（含扩展名），并按名称精确查库；不进行语义猜图、相似图替换或 Guide 重传。新上传图片必须使用上传响应的图片 `publish_id` 单独发布并确认前台双格式可读；图片未齐不得伪装完成。
6. 运行 `validate-article-html.py`。返回非零时继续修复，禁止上传不合格 HTML。正文必须使用真实换行；发现 `` `n ``、字面 `\n`、`‘n`、`’n` 或相应实体时，修复 HTML 生成方式并重新校验，不能仅在页面上隐藏字符。
7. 在任何 CMS 写入前运行 `validate-image-coverage.py <structure.json> <image-manifest.json> <final.html>`。只有 `source_embedded_image_count == manifest_image_count == html_manifest_image_count`、DOCX 中点名的 Guide fallback/WebP 全部出现、且 `pass: true` 才可继续；少一张、少一个出现位置、未发布、缺任一公开 URL 或残留 `IMAGE_PENDING` 都禁止调用 `page/add`／`page/update`。用户已明确要求保存草稿时，只用 CMS POST API 调用 `page/add` 或已确认目标的 `page/update`。禁止用浏览器表单代替 API；禁止 `page/make` 和发布文章页面。图片资源发布是前一步的必要流程，不属于文章发布。
8. 写入后立即 `page/info` 回读，并对回读 JSON 再运行 `validate-image-coverage.py`，同时运行 `compare-docx-to-cms-page.py`。缺少正文、表格、FAQ、图片、结语、下载区或 Buy Box 时修复草稿并再次回读；图片三方对账必须再次 `pass: true`，`missing_step_blocks` 必须为空，否则禁止通过。
9. 使用 Reviewer 通过 API 回读和本地机械检查复核当前草稿的字段、HTML、图片、来源覆盖与安全状态。当前暂不执行 AI 桌面／手机页面预览，也不得因此阻断草稿完成。

## 持续执行要求

- Commentary 只能报告已发生且可验证的进度，例如已生成的文件、API `request_id` 或页面 ID；任何“正在处理”之后必须立即执行真实工具调用，禁止只说不做。
- 任务仍有安全、已授权的下一步时继续调用工具，不把剩余步骤交还给使用者。
- 命令仍在运行时轮询同一会话；未经真实 POST 和执行证据契约规定的重试，不得报告网络、权限或接口故障。写请求结果不确定时先按 URL/标题查询，确认没有已创建草稿后再重试，防止重复文章。
- 只有遇到缺少必要源文件、凭据不存在、三次相同失败、关键 CMS 字段无法唯一确认或需要新增授权时才停止，并给出具体阻断证据。

## 最终报告

只有完成门槛全部通过后才能报告 `Draft ready for review`，并同时提供页面 ID、URL、草稿状态、HTML 校验、图片数量、来源完整度和回读 `request_id`。否则明确报告 `Image hold` 或 `Blocked`，不得说已经完成、已经上传或稍后继续。AI 页面预览目前停用，不要求也不报告桌面／手机预览结论。
