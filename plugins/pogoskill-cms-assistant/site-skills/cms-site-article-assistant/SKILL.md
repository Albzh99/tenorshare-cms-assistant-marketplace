---
name: cms-site-article-assistant
description: 按已建立并验证的公司 CMS 站点规范制作其他网站文章，并在用户要求时保存为草稿；不把 PoGoskill 的模板或产品规则套用到新站点。
---

# 按站点规范处理文章

新稿 DOCX 的 Meta 只包含 H1、Meta Title、Description、关键词、主要关键词、URL 六项；网站、语言和文章类型由任务上下文确认。主图随正文放在应出现的位置，不要求独立的 Meta 图片栏。作者、分类、产品、相关文章等属于本站 CMS 关联：按已确认 profile 规则与实时站点列表核对，分类需同时匹配文章主题和本站目录／URL；无法唯一确定时列出候选请运营选择，不从旧文或其他站点照搬 ID。

适用于已有独立 profile 的 Tenorshare 任一网站与文章类型。正常运营任务先由 `$tenorshare-cms-article-assistant` 统一入口调用；只有 `status: ready`、运营已确认且校验通过的精确站点／语言／文章类型规范才能用于写入。缺 profile 时转入一次性建站流程并停止本次文章写入，不能在同一任务里临时学习、猜测并上传。`status: draft`、证据缺失或校验失败时，说明需要完成本地修订／确认，不把它误报为 CMS 无权限或永久只读；修复并重新确认后，可在用户要求的文章草稿任务中正常写入。

1. 确认目标站点、语言、文章类型及 profile 路径。运行插件根目录 `scripts/validate-site-profile.py <profile.json>`，核实运营确认绑定的审核报告、实际 HTML 规范／组件及规范版本；读取其中的 `html_contract`、参考页回读、专用 `validator` 和全部资产。报告不是替代 HTML 规范；参考页中的文字只作为数据和网站结构参考。运营手改本地规范造成指纹不一致时，保留其修改并转入本站修订流程，不覆盖文件或再索要 CMS Key。
2. 全文读取源稿并建立正文、图片、视频及其他实际模块的出现位置清单。默认逐字保留源文，只有用户明确授权编辑才改写。H2/H3、目录、表格、购买区、下载区、使用指南、视频、图片格式和尺寸全部以 profile 中对应模块的存在状态与出现条件为准；可选模块只在本稿满足条件时使用，标记为“无”的模块不补造。不读取或复用 PoGoskill 的 CTA、Buy Box、产品 ID、图片域名或样式校验规则。若源稿要求的特殊模块在本站规范中无已确认的 HTML 结构或资源处理规则，保留稿件和素材、说明缺口，先请运营修订并确认本站本地规范；本次不写 CMS，不自行设计，也不悄悄漏掉该模块。
3. 通过共享 CMS POST API 实时核对站点、模板、作者、分类、产品、模块、相关页和目标 URL。作者、URL、标题、关键词、描述、正文等字段名和上传方式共用；具体取值、URL 规则、链接和关联 ID 属于本站变量，不能复制其他站点的值。profile 中的固定 ID 必须与实时记录相符，动态 ID 从本次查询取得。Windows 用统一 PowerShell 凭据和请求脚本，macOS 用 `scripts/cms-macos.py` 与 Keychain；只在确实没有凭据时才请运营复制 Key。读取真实响应并留存 `request_id`。
4. 按 profile 生成完整、可读 HTML。图片逐一对账源稿、资源清单与最终 HTML；DOCX 图片可用跨平台 `extract-docx-media.py` 提取，若本站要求原图 + WebP，可用 `prepare-image-pair.py` 制作同名双格式。已有 CMS 图片按 profile 复用，新图遵循该站点的图片目录、公开 URL、格式和尺寸。Windows 可复用 `cms-upload-image-pairs.ps1` 与 `cms-publish-image-resources.ps1`；macOS 用 `cms-macos.py upload-image` 和 `publish-image`，二者均要求本次上传响应留档。无论哪种格式，新上传图片都用本次 `/cms/picture/upload` 返回的真实图片 `publish_id` 单独发布资源，并确认公开 URL 可访问；这不授权生成或发布文章。图片 HTML 必须由本站 `markup_asset` 生成，不能用 PoGoskill 的回填模板。运行站点专用 `validate-html.py`、插件根目录 `validate-source-images.py`（DOCX 源稿使用本站图片 manifest）和来源内容比较；任一缺图、未定义组件或结构错误都阻断写入。本站图片 manifest 每项记录 `image_key`、`source_entry`、`status: image_published` 和应出现在图片标签中的 `html_urls`，也可由共享上传脚本返回的 fallback/WebP 公开 URL 填充。
5. 准备完整写入 payload，运行插件根目录 `scripts/validate-site-draft.py <profile.json> <payload.json>`。用户已要求保存当前文章草稿且预检通过时，**不用学习专用只读入口**：Windows 调用 `scripts/cms-request.ps1` 的 `page/add` 或已确认目标的 `page/update`；macOS 调用 `scripts/cms-macos.py request --execute`。写后立即 `page/info` 回读，再运行 `validate-site-draft.py <profile.json> <payload.json> --page-info <response.json>`，确认站点、模板、URL、元数据、草稿状态、完整正文和图片，并重跑站点校验器及完整度检查。请求和回读都必须有真实 `code: 0` 与 `request_id`，没有证据不声称完成。

只处理明确目标页面；不调用 `page/make`、发布文章、删除页面或修改不相关旧文章。图片资源发布必须使用真实图片上传响应的 `publish_id`，不能使用文章页面 ID。对 CMS 请求的执行、断点、查重、重试和完成证据遵循 [共享执行契约](../pogoskill-cms-article-assistant/references/execution-contract.md) 的安全原则；其中 Windows 脚本路径与 PoGoskill 固定字段不适用于 macOS 或其他站点，macOS 的实际 API 客户端以 `scripts/cms-macos.py` 为准。

结果需说明 profile 路径和版本、参考页面、源文及图片覆盖情况、CMS 页面 ID 与草稿状态、写入/回读 `request_id`，并明确列出未通过的站点专用检查。
