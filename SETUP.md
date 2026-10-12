# Tenorshare CMS 助手安装说明 供 AI 执行

运营同事只读 [START-HERE.md](START-HERE.md)。本仓库插件名为 `tenorshare-cms-assistant`；Marketplace 的历史注册名仍是 `pogoskill-team`。**其他产品和网站不能调用 PoGoskill 专用技能。**

## 安装或升级

先检查 `codex plugin list` 与 `codex plugin marketplace list`，再根据实际状态安装或升级公开仓库 `https://github.com/Albzh99/tenorshare-cms-assistant-marketplace.git`：

```text
codex plugin marketplace add "https://github.com/Albzh99/tenorshare-cms-assistant-marketplace.git" --ref main
codex plugin add tenorshare-cms-assistant@pogoskill-team
```

若已注册 `pogoskill-team` Marketplace，则改为 `codex plugin marketplace upgrade pogoskill-team`，再安装新版插件。旧 `pogoskill-cms-assistant@pogoskill-team` 与新插件是不同身份：新插件安装并验证后，若旧身份仍导致路由冲突，只移除这一个旧插件；不删除凭据、站点 profile、Marketplace 或独立的 `pogoskill-cms-assistant@pogoskill-only`。安装后开新对话以加载新技能。只有 `$tenorshare-cms-article-assistant` 等多站点入口出现，才把安装称为完成；仅看到 `$pogoskill-cms-en-publisher` 说明选错了插件。

动态取得当前安装的插件根目录，不复用旧消息里的缓存版本路径。源码目录仍是 `plugins/pogoskill-cms-assistant/`，这是历史路径；它不决定可调用的插件身份，不能据此选择 PoGoskill HTML 模板。

## Key 和本机检查

先判断系统。Windows 从插件根目录运行 `scripts/cms-check-api-key.ps1`，macOS 运行 `python3 scripts/cms-macos.py check-key`。已有 Key 不再询问。确实没有时，Windows 运行不带 `-Prompt` 的 `scripts/cms-save-api-key.ps1` 并打开可见终端；**macOS 必须由 AI 运行 `python3 scripts/cms-macos.py open-save-key-terminal`，让系统打开真正的 Terminal.app 窗口**。Mac 不能直接在 Codex 内置终端运行 `save-key`，也不能把那个内置终端说成 Terminal.app；脚本会拒绝这种用法。Mac 启动命令现在等待独立 Terminal.app 中的脚本发回就绪信号；若超时即失败，不能凭 `open` 退出码称窗口已开。收到信号且用户确认确实看见系统窗口，才让用户复制 Key、回到该窗口按 Enter，不粘贴、不发聊天。之后 AI 再运行 Mac 的 `check-key`，实际成功才说已保存。若 macOS 阻止打开 Terminal.app，报告该具体错误并请求用户处理系统弹窗；不要谎称窗口已打开，也不要退回不可用的 Codex 内置终端。Mac 不运行 `.ps1` 或 Windows `.exe`。

随后运行插件根目录 `scripts/verify-workstation.py`，实际检查当前凭据、`/cms/site/list` 只读 POST 和 WebP 编码能力。Windows 缺 PATH 中的 PowerShell 时，AI 定位当前机器真实的 `pwsh` 并传 `--powershell`；Mac 不传。失败按具体错误处理，不把“Key 检查通过”误报为“4DDiG 已建规范”或“文章已上传”。

Mac 的 CMS POST 现在使用系统 `curl`，不再由 Python `urllib` 发往网关；Key 仍从当前用户 Keychain 读取，经 curl 的标准输入传入，不出现在命令参数或临时文件。`check-key` 只证实本机有格式有效的 Key，不等于网关授权。若出现 403，先用当前插件的 `verify-workstation.py` 检查只读 `/cms/site/list`，记录脱敏的接口、HTTP 状态、`code`、`msg`、`request_id`；再根据同一台 Mac 上 curl 的实际结果区分旧版脚本、请求路径与网关／网络出口问题，不直接说 Key 没权限或反复索要。

若 Mac 报 `Keychain status=-50`，先引用脚本的完整错误（`read`、`save` 或 `item lookup`），不要只说“Key 没权限”。读取遇到旧 Keychain API 的 `-50` 时，脚本会改用系统 `security find-generic-password -w` 读取同一服务与用户的条目；Key 仅在进程内接收，不输出到日志。已有条目覆盖保存时，脚本会完整取得旧条目的指针后再更新。若两个读取方式都失败，应记录两个非敏感状态码并停止；不要反复要求用户重存或显示 Key。

安装检查通过后，**安装 AI 必须主动告知运营模型选择**，不能等运营问：首次学习网站、编写及审核 `html-contract.md`／组件校验器、修订规范时，请在 Codex 的模型／推理控制中选当前账户可用的较强推理模型；这是需要判断本站结构的阶段。规范 `ready` 且几篇草稿上传、回读稳定后，重复执行才可改用较便宜的 Luna。遇到新模块、版式冲突或规范修订，再切回较强模型。只建议和说明，不假称 AI 能自动切换模型，也不假定运营账户一定有某个具体型号。安装完成回复中同时给出这段提醒和一条可直接复制的建规范消息。

## 4DDiG 英文站首次测试

在新对话中直接向 AI 发送：

> 我负责 4DDiG 英文站的 SEO 文章。请使用 `$tenorshare-cms-article-assistant`，先通过只读 CMS POST 查 `site/list`，确认与 4DDiG 英文站对应的准确网址；若有多个候选，让我选网址。然后读取 2–3 篇本站同模板、同正文版式但可跨分类的已发布文章，查询模板、作者、分类和图片规则，学习真实 HTML，建立仅属于该站和该版式族的本地规范与 `review-report.md` 给我确认。分类是逐篇动态选择字段，不要先问我要分类，也不要因分类不同拆规范。现在只学习，不上传图片或文章，不生成、不发布，不用 PoGoskill 英文模板。

用户不必指定文章分类或“文章类型”。先从本站模板和已发布正文判断是否有不同 HTML 版式族；同模板、同版式的分类共用一套规范，只有真实结构／必填字段不同才拆分。分类规则以实时查询和文章主题／URL 匹配记录，不要求首次学习时穷尽分类。站点 profile 先保持 `draft`，明确确认当前报告后才能设为 `ready`。只有后续另行提供新稿并要求存草稿时，才使用正常 CMS 写入；首次学习的只读限制不是永久权限。CMS 预览如可用，应区分“实际打开并检查”与“只核对 HTML”；未预览不能声称已预览。
