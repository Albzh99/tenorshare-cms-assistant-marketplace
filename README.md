# Tenorshare CMS 多站点文章助手

本仓库的插件身份是 `tenorshare-cms-assistant`，用于 Tenorshare 任一产品、语言和独立网站。它不预设 PoGoskill 的 HTML；PoGoskill 固定模板助手在[独立仓库](https://github.com/Albzh99/pogoskill-cms-article-assistant)。两种助手可以并存，不应把“英文”自动解释为“PoGoskill 英文”。

操作员只需看 [START-HERE.md](START-HERE.md)，安装细节由 AI 按 [SETUP.md](SETUP.md) 执行。安装后，给出目标网站或产品和语言；无需先选文章分类或 HTML 版式类型。例如：

> 我负责 4DDiG 英文站的 SEO 文章。请使用 `$tenorshare-cms-article-assistant`，先从 CMS 只读查询本站已发布的同类文章，学习真实 HTML，生成本站本机规范和简明审核报告给我确认。现在不上传文章，也不要套用 PoGoskill 模板。

首次建规范阶段只读 CMS，会在当前用户本机按站点／语言／实际 HTML 版式族保存 `profile.json`、`html-contract.md`、组件样本、校验器和 `review-report.md`；不同 CMS 分类如共用版式，就共用一套规范。旧 HTML 可补充，但有 CMS 旧文章时不要求操作员提供。操作员确认后，新的文章任务才按该规范上传草稿，并按主题与 URL 实时选择分类。草稿上传可以上传并单独发布图片资源，不生成或发布文章、不修改无关旧文。

本仓库安装时只向 Codex 暴露三个多站点技能：`$tenorshare-cms-article-assistant`、`$cms-site-standard-builder` 和 `$cms-site-article-assistant`。历史 PoGoskill 素材和脚本仍保留供迁移及兼容测试，但 PoGoskill 专用技能不作为本插件入口。安装标识中的 Marketplace 名称 `pogoskill-team` 是旧注册名，不代表本站模板；插件名已独立为 `tenorshare-cms-assistant`。

API Key 不在仓库中。Windows 从当前用户的受保护存储读取，macOS 从 Keychain 读取；有 Key 就不重复索取。首次保存由 AI 启动等待流程，用户复制 Key 后回可见终端按 Enter；Mac 必须是独立的系统 Terminal.app，不是 Codex 内置终端。CMS 业务成功以响应 `code === 0` 和 `request_id` 为证据。学习阶段不调用写入接口；上传阶段必须有页面写入和回读证据，才可称草稿已保存。

## 2026-10-28 附加增强

保留现有站点学习、确认、图片与CMS草稿流程，增加：先完整学习文章栏目首篇风格模板，再比较至少三篇历史文章；对全部结构和样式变体登记覆盖证据。用户纠正一次后保存本站持久规则、更新组件和校验，以正确／错误样例防止复发。旧profile兼容，不自动迁移或重建。详见[补充契约](plugins/pogoskill-cms-assistant/site-skills/cms-site-standard-builder/references/learning-and-corrections.md)。

凭据窗口修复版 `1.0.0+codex.20261028terminal1`：Windows 保存入口自动打开独立系统 PowerShell，检查可见控制台和子进程就绪信号；macOS 使用 Terminal.app，旧的直接保存命令也会自动转到系统窗口。Codex 内置面板不能作为 Key 输入窗口。窗口打开只表示可以操作，保存成功仍以凭据检查和只读 CMS 连接验证为准。
