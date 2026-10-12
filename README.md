# Tenorshare CMS 多站点文章助手

本仓库的插件身份是 `tenorshare-cms-assistant`，用于 Tenorshare 任一产品、语言和独立网站。它不预设 PoGoskill 的 HTML；PoGoskill 固定模板助手在[独立仓库](https://github.com/Albzh99/pogoskill-cms-article-assistant)。两种助手可以并存，不应把“英文”自动解释为“PoGoskill 英文”。

操作员只需看 [START-HERE.md](START-HERE.md)，安装细节由 AI 按 [SETUP.md](SETUP.md) 执行。安装后，给出目标网站或产品、语言、文章类型。例如：

> 我负责 4DDiG 英文站的 SEO 文章。请使用 `$tenorshare-cms-article-assistant`，先从 CMS 只读查询本站已发布的同类文章，学习真实 HTML，生成本站本机规范和简明审核报告给我确认。现在不上传文章，也不要套用 PoGoskill 模板。

首次建规范阶段只读 CMS，会在当前用户本机保存该站／语言／文章类型的 `profile.json`、`html-contract.md`、组件样本、校验器和 `review-report.md`。旧 HTML 可补充，但有 CMS 旧文章时不要求操作员提供。操作员确认后，新的文章任务才按该规范上传草稿。草稿上传可以上传并单独发布图片资源，不生成或发布文章、不修改无关旧文。

本仓库安装时只向 Codex 暴露三个多站点技能：`$tenorshare-cms-article-assistant`、`$cms-site-standard-builder` 和 `$cms-site-article-assistant`。历史 PoGoskill 素材和脚本仍保留供迁移及兼容测试，但 PoGoskill 专用技能不作为本插件入口。安装标识中的 Marketplace 名称 `pogoskill-team` 是旧注册名，不代表本站模板；插件名已独立为 `tenorshare-cms-assistant`。

API Key 不在仓库中。Windows 从当前用户的受保护存储读取，macOS 从 Keychain 读取；有 Key 就不重复索取。首次保存采用“先运行等待命令、再复制 Key、回可见终端按 Enter”的流程。CMS 业务成功以响应 `code === 0` 和 `request_id` 为证据。学习阶段不调用写入接口；上传阶段必须有页面写入和回读证据，才可称草稿已保存。
