import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate-site-profile.py")
SPEC = importlib.util.spec_from_file_location("validate_site_profile", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SiteProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "evidence").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "assets").mkdir()
        (self.root / "tests" / "valid.html").write_text("<article>valid sample</article>", encoding="utf-8")
        (self.root / "tests" / "invalid.html").write_text("<article>invalid sample</article>", encoding="utf-8")
        sections = "\n".join(f"## {name}\n本站已核对：无或有真实证据。" for name in MODULE.REQUIRED_CONTRACT_SECTIONS
                             if name != "逐模块执行规则表")
        rows = ["## 逐模块执行规则表", "| 模块 | 状态 | 条件 | 位置与顺序 | 可执行规则 | 证据 | 片段 |",
                "| --- | --- | --- | --- | --- | --- | --- |"]
        for index, name in enumerate(MODULE.RULE_MODULES):
            if index < 3:
                asset = f"assets/module-{index}.html"
                (self.root / asset).write_text(f"<p>Reference module {index}</p>", encoding="utf-8")
                rows.append(f"| {name} | 固定 | 每篇正文 | 正文开始处 | 使用 `<p>` 标签，不改层级 | 参考页 789 | {asset} |")
            else:
                rows.append(f"| {name} | 无 | 此文章类型未出现 | 正文不插入 | 正文不插入该模块 | 参考页 789 | 无，参考页未出现 |")
        sections += "\n" + "\n".join(rows)
        (self.root / "html-contract.md").write_text("# Site article rules\n" + sections, encoding="utf-8")
        report_sections = "\n".join(f"## {name}\n本站已核对的实际内容。" for name in MODULE.REQUIRED_REPORT_SECTIONS)
        report_sections += "\n参考页 789：\n```html\n<p>Reference module 0</p>\n```\n"
        report_sections += "\n参考页 789：\n```html\n<p>Reference module 1</p>\n```\n"
        (self.root / "review-report.md").write_text("# Site review\n" + report_sections, encoding="utf-8")
        self.report_sha256 = hashlib.sha256((self.root / "review-report.md").read_bytes()).hexdigest()
        (self.root / "validate-html.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        self.page = {
            "code": 0,
            "request_id": "original-cms-readback-id",
            "data": {"id": 789, "site_id": 123, "template_id": 456, "status": "4", "content": "<article>" + "sample section " * 12 + "</article>"},
        }
        self.profile = {
            "schema_version": 1,
            "profile_id": "example-com-how-to",
            "status": "ready",
            "profile_version": 1,
            "approval": {"confirmed_by": "site-operator", "confirmed_at": "2026-10-09T10:00:00+08:00",
                         "profile_version": 1, "report_sha256": self.report_sha256},
            "site": {"id": 123, "name": "Example", "language": "en", "base_url": "https://www.example.com"},
            "article_type": "how-to",
            "cms": {"template_id": 456, "draft_status": 5, "draft_sync_status": 1,
                    "product_ids": [], "required_fields": ["title", "content"]},
            "images": {"enabled": False},
            "references": [{"page_id": 789, "page_info_json": "evidence/reference.json"}],
            "html_contract": "html-contract.md",
            "review_report": "review-report.md",
            "validator": "validate-html.py",
            "validation_examples": {"valid_html": "tests/valid.html", "invalid_html": "tests/invalid.html"},
            "assets": ["assets/module-0.html", "assets/module-1.html", "assets/module-2.html"],
            "optional_rule_waivers": [],
        }
        self.seal()

    def seal(self):
        (self.root / "evidence" / "reference.json").write_text(json.dumps(self.page), encoding="utf-8")
        self.profile["approval"]["profile_version"] = self.profile["profile_version"]
        self.profile["approval"]["report_sha256"] = hashlib.sha256(
            (self.root / "review-report.md").read_bytes()).hexdigest()
        self.profile["approval"]["rules_sha256"] = MODULE.rules_sha256(self.profile, self.root)

    def check(self):
        (self.root / "evidence" / "reference.json").write_text(json.dumps(self.page), encoding="utf-8")
        path = self.root / "profile.json"
        path.write_text(json.dumps(self.profile), encoding="utf-8")
        return MODULE.check_profile(path)

    def test_accepts_matching_cms_reference(self):
        result = self.check()
        self.assertTrue(result["pass"], result["errors"])

    def test_fingerprint_command_works_before_ready(self):
        self.profile["status"] = "draft"
        self.check()
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.root / "profile.json"),
                                 "--fingerprint"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        fingerprint = json.loads(result.stdout)
        self.assertEqual(fingerprint["rules_sha256"], self.profile["approval"]["rules_sha256"])
        self.assertEqual(fingerprint["report_sha256"], self.profile["approval"]["report_sha256"])

    def test_accepts_cms_string_ids(self):
        self.page["data"].update({"id": "789", "site_id": "123", "template_id": "456"})
        self.seal()
        result = self.check()
        self.assertTrue(result["pass"], result["errors"])

    def test_rejects_reference_from_another_site(self):
        self.page["data"]["site_id"] = 324
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("site ID differs" in error for error in result["errors"]))

    def test_rejects_unpublished_reference(self):
        self.page["data"]["status"] = "5"
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("published page" in error for error in result["errors"]))

    def test_rejects_draft_profile(self):
        self.profile["status"] = "draft"
        self.assertFalse(self.check()["pass"])

    def test_rejects_unconfirmed_profile(self):
        self.profile.pop("approval")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("approval.confirmed_by" in error for error in result["errors"]))

    def test_rejects_report_changed_after_confirmation(self):
        (self.root / "review-report.md").write_text("# Changed report\n" + "\n".join(
            f"## {name}\n新内容。" for name in MODULE.REQUIRED_REPORT_SECTIONS), encoding="utf-8")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("report_sha256" in error for error in result["errors"]))

    def test_rejects_local_html_contract_edit_until_reconfirmed(self):
        contract = self.root / "html-contract.md"
        contract.write_text(contract.read_text(encoding="utf-8") + "\n本站调整了表格样式。\n", encoding="utf-8")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("rules_sha256" in error for error in result["errors"]))
        self.profile["profile_version"] = 2
        self.seal()
        self.assertTrue(self.check()["pass"])

    def test_rejects_local_component_edit_until_reconfirmed(self):
        asset = self.root / "assets" / "paragraph.html"
        asset.write_text("<p>Original</p>", encoding="utf-8")
        self.profile["assets"] = ["assets/paragraph.html"]
        self.seal()
        asset.write_text("<p>Changed</p>", encoding="utf-8")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("rules_sha256" in error for error in result["errors"]))

    def test_rejects_confirmation_of_previous_version(self):
        self.profile["profile_version"] = 2
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("approval.profile_version" in error for error in result["errors"]))

    def test_rejects_missing_review_report(self):
        self.profile.pop("review_report")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("review_report" in error for error in result["errors"]))

    def test_rejects_unfilled_review_report(self):
        (self.root / "review-report.md").write_text("# Site review\n" + "\n".join(
            f"## {name}\n【未填写】" for name in MODULE.REQUIRED_REPORT_SECTIONS), encoding="utf-8")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("unfilled template" in error for error in result["errors"]))

    def test_rejects_missing_version(self):
        self.profile.pop("profile_version")
        self.assertFalse(self.check()["pass"])

    def test_rejects_incomplete_html_contract(self):
        (self.root / "html-contract.md").write_text("# Empty contract\n## 标题与目录\n【未填写】", encoding="utf-8")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("missing required section" in error for error in result["errors"]))
        self.assertTrue(any("unfilled template" in error for error in result["errors"]))

    def test_rejects_overview_only_rule_table(self):
        contract = self.root / "html-contract.md"
        content = contract.read_text(encoding="utf-8")
        contract.write_text(content.replace("使用 `<p>` 标签，不改层级", "已核对旧文"), encoding="utf-8")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("summary" in error for error in result["errors"]))

    def test_rejects_placeholder_component(self):
        (self.root / "assets" / "module-0.html").write_text("<p>example.webp ...</p>", encoding="utf-8")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("placeholder markup" in error for error in result["errors"]))

    def test_rejects_unindexed_rule_asset(self):
        self.profile["assets"] = ["assets/module-1.html", "assets/module-2.html"]
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("profile.assets" in error for error in result["errors"]))

    def test_rejects_unresolved_module_when_ready(self):
        contract = self.root / "html-contract.md"
        contract.write_text(contract.read_text(encoding="utf-8").replace(
            "| 视频 | 无 |", "| 视频 | 待确认 |"), encoding="utf-8")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("unresolved module" in error for error in result["errors"]))

    def test_accepts_operator_deferred_video_without_weakening_core(self):
        contract = self.root / "html-contract.md"
        contract.write_text(contract.read_text(encoding="utf-8").replace(
            "| 视频 | 无 |", "| 视频 | 待确认 |"), encoding="utf-8")
        self.profile["optional_rule_waivers"] = [{
            "module": "视频", "decision": "defer_until_needed",
            "reason": "已查同版式参考页，未找到可复用的视频结构；有视频稿件时再补规范。",
            "operator_confirmation": "运营确认：视频先暂缓，普通文章可用。",
        }]
        report = self.root / "review-report.md"
        report.write_text(report.read_text(encoding="utf-8") +
                          "\n视频：运营确认暂缓；新稿有视频时先补规范。运营确认：视频先暂缓，普通文章可用。\n",
                          encoding="utf-8")
        self.seal()
        self.assertTrue(self.check()["pass"])
        self.profile["optional_rule_waivers"][0]["reason"] += " 更新后须重新确认。"
        changed = self.check()
        self.assertFalse(changed["pass"])
        self.assertTrue(any("rules_sha256" in error for error in changed["errors"]))

    def test_rejects_waiver_for_core_layout(self):
        contract = self.root / "html-contract.md"
        contract.write_text(contract.read_text(encoding="utf-8").replace(
            "| 页面骨架 | 固定 |", "| 页面骨架 | 待确认 |"), encoding="utf-8")
        self.profile["optional_rule_waivers"] = [{
            "module": "页面骨架", "decision": "defer_until_needed",
            "reason": "不允许把页面主体结构作为低频模块暂缓。",
            "operator_confirmation": "先跳过",
        }]
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("core layout" in error for error in result["errors"]))

    def test_rejects_unconfirmed_optional_waiver(self):
        contract = self.root / "html-contract.md"
        contract.write_text(contract.read_text(encoding="utf-8").replace(
            "| FAQ | 无 |", "| FAQ | 待确认 |"), encoding="utf-8")
        self.profile["optional_rule_waivers"] = [{
            "module": "FAQ", "decision": "defer_until_needed",
            "reason": "参考文章未包含 FAQ，待有含 FAQ 的文章再补真实结构。",
        }]
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("operator confirmation" in error for error in result["errors"]))

    def test_rejects_waiver_not_disclosed_in_report(self):
        contract = self.root / "html-contract.md"
        contract.write_text(contract.read_text(encoding="utf-8").replace(
            "| FAQ | 无 |", "| FAQ | 待确认 |"), encoding="utf-8")
        self.profile["optional_rule_waivers"] = [{
            "module": "FAQ", "decision": "defer_until_needed",
            "reason": "参考文章未包含 FAQ，待有含 FAQ 的文章再补真实结构。",
            "operator_confirmation": "同意暂缓 FAQ，有 FAQ 的新稿先补规范",
        }]
        self.seal()
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("review_report must quote" in error for error in result["errors"]))

    def test_rejects_report_without_real_snippets(self):
        report = self.root / "review-report.md"
        report.write_text("# Site review\n" + "\n".join(
            f"## {name}\n本站已核对。" for name in MODULE.REQUIRED_REPORT_SECTIONS), encoding="utf-8")
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("2-4 real" in error for error in result["errors"]))

    def test_rejects_missing_negative_example(self):
        self.profile["validation_examples"]["invalid_html"] = "tests/missing.html"
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("validation_examples.invalid_html" in error for error in result["errors"]))

    def test_rejects_assets_outside_profile(self):
        self.profile["assets"] = ["../foreign-cta.html"]
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("inside profile directory" in error for error in result["errors"]))

    def test_accepts_uploaded_old_html_with_verified_cms_discovery(self):
        old_html = b"<html><body><h2>Article</h2>" + b"<p>Reference paragraph</p>" * 8 + b"</body></html>"
        (self.root / "evidence" / "old-article.html").write_bytes(old_html)
        self.profile["references"] = [{
            "kind": "html", "html_file": "evidence/old-article.html",
            "sha256": hashlib.sha256(old_html).hexdigest(),
        }]
        self.profile["cms_discovery"] = {
            "site_list_json": "evidence/sites.json",
            "template_list_json": "evidence/templates.json",
            "template_fields_json": "evidence/fields.json",
        }
        for name, data in (("sites.json", {"list": [{"id": 123}]}),
                           ("templates.json", {"list": [{"id": 456}]}),
                           ("fields.json", {"list": [{"name": "title"}]})):
            (self.root / "evidence" / name).write_text(json.dumps({
                "code": 0, "request_id": "cms-evidence-id", "data": data,
            }), encoding="utf-8")
        self.seal()
        self.assertTrue(self.check()["pass"])

    def test_rejects_uploaded_html_without_cms_mapping(self):
        old_html = b"<html><body>" + b"paragraph" * 20 + b"</body></html>"
        (self.root / "evidence" / "old-article.html").write_bytes(old_html)
        self.profile["references"] = [{
            "kind": "html", "html_file": "evidence/old-article.html",
            "sha256": hashlib.sha256(old_html).hexdigest(),
        }]
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("cms_discovery" in error for error in result["errors"]))

    def test_image_profile_requires_own_public_domain_and_markup(self):
        self.profile["images"] = {"enabled": True, "formats": ["jpg", "webp"],
                                  "cms_directories": {"article": "blog"},
                                  "publish_mode": "picture-upload-publish-id",
                                  "public_url_prefix": "https://images.example.com/blog/",
                                  "markup_asset": "assets/image-box.html"}
        (self.root / "assets" / "image-box.html").write_text(
            '<picture><img src="https://images.example.com/blog/real-photo.jpg" alt="Real photo"></picture>',
            encoding="utf-8")
        self.seal()
        self.assertTrue(self.check()["pass"])
        self.profile["images"]["public_url_prefix"] = "https://site.p.cms.afirstsoft.cn/example/"
        self.assertFalse(self.check()["pass"])

    def test_rejects_placeholder_image_markup(self):
        self.profile["images"] = {"enabled": True, "formats": ["jpg", "webp"],
                                  "cms_directories": {"article": "blog"},
                                  "publish_mode": "picture-upload-publish-id",
                                  "public_url_prefix": "https://images.example.com/blog/",
                                  "markup_asset": "assets/image-box.html"}
        (self.root / "assets" / "image-box.html").write_text(
            '<picture><img src="example.webp" alt="placeholder"></picture>', encoding="utf-8")
        self.seal()
        result = self.check()
        self.assertFalse(result["pass"])
        self.assertTrue(any("non-placeholder image HTML" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
