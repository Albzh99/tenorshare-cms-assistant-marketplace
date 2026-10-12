"""Check that a new CMS site/article-type contract is based on real page readbacks."""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED_CONTRACT_SECTIONS = (
    "适用范围与证据", "CMS 字段与动态关联", "页面骨架与模块顺序", "标题与目录",
    "段落与列表", "图片与媒体", "表格", "产品区与下载", "FAQ 与特殊模块",
    "结论与链接", "校验与例外", "逐模块执行规则表", "参考文章差异与适用条件",
)
REQUIRED_REPORT_SECTIONS = (
    "这份规范管什么", "文章会长什么样", "可直接照做的关键规则",
    "上传时会怎样处理", "已检查与待确认", "人工暂缓的低频模块", "请运营回复",
)
RULE_MODULES = (
    "页面骨架", "H2/H3 标题", "目录与锚点", "段落与强调", "列表与步骤",
    "图片与图注", "表格", "产品介绍", "下载区", "Buy Box／购买区",
    "使用指南", "FAQ", "视频", "结语与内链",
)
RULE_STATUSES = {"固定", "可选", "无", "待确认"}
CORE_RULE_MODULES = {"页面骨架", "H2/H3 标题", "段落与强调", "图片与图注"}
DEFERRABLE_MODULES = set(RULE_MODULES) - CORE_RULE_MODULES
RULE_FIELDS = (
    "schema_version", "profile_id", "profile_version", "site", "article_type", "cms",
    "references", "cms_discovery", "images", "html_contract", "review_report",
    "validator", "validation_examples", "assets",
)


def positive_int(value):
    return type(value) is int and value > 0


def same_positive_id(value, expected):
    """CMS readbacks may encode database IDs as decimal strings."""
    return (positive_int(expected) and not isinstance(value, bool)
            and isinstance(value, (int, str)) and str(value) == str(expected))


def local_file(root, name, suffix=None):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("path is missing")
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"path must stay inside profile directory: {name}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"profile file missing or empty: {name}")
    if suffix and path.suffix.lower() != suffix:
        raise ValueError(f"profile file must end in {suffix}: {name}")
    return path


def rules_sha256(profile, root):
    """Bind the confirmed site rules and their local files, not just the review summary."""
    assets = profile.get("assets")
    if not isinstance(assets, list):
        raise ValueError("assets must be an array before computing the rules fingerprint")
    examples = profile.get("validation_examples") or {}
    discovery = profile.get("cms_discovery") or {}
    names = [profile.get("html_contract"), profile.get("validator"), *assets]
    if isinstance(examples, dict):
        names.extend(examples.values())
    if isinstance(discovery, dict):
        names.extend(discovery.values())
    images = profile.get("images") or {}
    if isinstance(images, dict) and images.get("enabled"):
        names.append(images.get("markup_asset"))
    for reference in profile.get("references") or []:
        if isinstance(reference, dict):
            names.append(reference.get("html_file") if reference.get("kind") == "html"
                         else reference.get("page_info_json"))
    files = {}
    for name in names:
        path = local_file(root, name)
        files[str(Path(name))] = hashlib.sha256(path.read_bytes()).hexdigest()
    profile_snapshot = {field: profile.get(field) for field in RULE_FIELDS}
    # Preserve fingerprints for profiles created before optional waivers existed.
    if profile.get("optional_rule_waivers"):
        profile_snapshot["optional_rule_waivers"] = profile["optional_rule_waivers"]
    snapshot = {"profile": profile_snapshot, "files": dict(sorted(files.items()))}
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def contains_id(value, target):
    if isinstance(value, dict):
        if same_positive_id(value.get("id"), target):
            return True
        return any(contains_id(child, target) for child in value.values())
    if isinstance(value, list):
        return any(contains_id(child, target) for child in value)
    return False


def check_rule_table(contract, root, indexed_assets, waivers):
    """Reject overview-only contracts while allowing site-specific optional modules."""
    errors = []
    match = re.search(r"^## 逐模块执行规则表\s*$([\s\S]*?)(?=^## |\Z)", contract, re.MULTILINE)
    if not match:
        return ["html_contract missing actionable rule table"]
    rows = {}
    for line in match.group(1).splitlines():
        if not line.startswith("|") or line.startswith("| ---") or line.startswith("| 模块"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7:
            errors.append("html_contract rule table rows must have seven filled columns")
            continue
        name, status, condition, position, rule, evidence, asset = cells
        if name in rows:
            errors.append(f"html_contract duplicate module rule: {name}")
        rows[name] = cells
        if status not in RULE_STATUSES:
            errors.append(f"html_contract {name}: status must be 固定/可选/无/待确认")
        if any(not cell or "【" in cell or "未填写" in cell for cell in cells):
            errors.append(f"html_contract {name}: rule has blank or placeholder fields")
        if status in {"固定", "可选"}:
            if not re.search(r"[<`]|class=|style=|尺寸|像素|px|模板字段", rule):
                errors.append(f"html_contract {name}: rule is a summary, not an HTML/style/size instruction")
            if not re.search(r"assets/[^\s`]+\.html", asset):
                errors.append(f"html_contract {name}: a real assets/*.html snippet is required")
            else:
                asset_name = re.search(r"assets/[^\s`]+\.html", asset).group(0)
                if asset_name not in indexed_assets:
                    errors.append(f"html_contract {name}: asset must be listed in profile.assets for approval fingerprint")
                try:
                    snippet = local_file(root, asset_name, ".html").read_text(encoding="utf-8-sig")
                    if not re.search(r"<\s*[a-z][\w-]*\b", snippet, re.IGNORECASE):
                        errors.append(f"html_contract {name}: asset contains no HTML element")
                    if re.search(r"【|example\.(?:webp|jpe?g|png)|IMAGE_PENDING|\.\.\.", snippet, re.IGNORECASE):
                        errors.append(f"html_contract {name}: asset still contains example or placeholder markup")
                except (OSError, ValueError) as exc:
                    errors.append(f"html_contract {name}: asset {exc}")
        if not re.search(r"\b\d{3,}\b|evidence/", evidence):
            errors.append(f"html_contract {name}: cite a reference page ID or evidence file")
    for name in RULE_MODULES:
        if name not in rows:
            errors.append(f"html_contract rule table missing module: {name}")
    if sum(rows[name][1] in {"固定", "可选"} for name in RULE_MODULES if name in rows) < 3:
        errors.append("html_contract rule table has too few observed active modules")
    waived_modules = set()
    if not isinstance(waivers, list):
        errors.append("optional_rule_waivers must be an array")
        waivers = []
    for waiver in waivers:
        if not isinstance(waiver, dict):
            errors.append("optional_rule_waivers entries must be objects")
            continue
        module = waiver.get("module")
        if module not in DEFERRABLE_MODULES or module in waived_modules:
            errors.append(f"optional_rule_waivers invalid or duplicate module: {module}")
            continue
        waived_modules.add(module)
        if rows.get(module, [None, None])[1] != "待确认":
            errors.append(f"optional_rule_waivers {module}: only a pending module can be deferred")
        if waiver.get("decision") != "defer_until_needed":
            errors.append(f"optional_rule_waivers {module}: decision must be defer_until_needed")
        if not isinstance(waiver.get("reason"), str) or len(waiver["reason"].strip()) < 10:
            errors.append(f"optional_rule_waivers {module}: a specific reason is required")
        if not isinstance(waiver.get("operator_confirmation"), str) or not waiver["operator_confirmation"].strip():
            errors.append(f"optional_rule_waivers {module}: operator confirmation is required")
    unresolved = {name for name, cells in rows.items() if cells[1] == "待确认"}
    if unresolved & CORE_RULE_MODULES:
        errors.append("html_contract has unresolved core layout rules; these cannot be waived")
    if unresolved - waived_modules:
        errors.append("html_contract has unresolved module rules without operator waiver; keep profile draft")
    return errors


def check_profile(profile_path):
    path = Path(profile_path).resolve()
    root = path.parent
    errors = []
    try:
        profile = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return {"pass": False, "errors": [f"cannot read profile: {exc}"]}
    if not isinstance(profile, dict):
        return {"pass": False, "errors": ["profile root must be an object"]}

    if profile.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in ("profile_id", "article_type"):
        value = profile.get(field)
        if not isinstance(value, str) or not SAFE_SLUG.fullmatch(value):
            errors.append(f"{field} must be a lowercase hyphenated slug")
    if profile.get("status") != "ready":
        errors.append("status must be ready before use for an article")
    if not positive_int(profile.get("profile_version")):
        errors.append("profile_version must be a positive integer")
    approval = profile.get("approval") if isinstance(profile.get("approval"), dict) else {}
    if not isinstance(approval.get("confirmed_by"), str) or not approval.get("confirmed_by").strip():
        errors.append("approval.confirmed_by is required before article use")
    confirmed_at = approval.get("confirmed_at")
    try:
        if not isinstance(confirmed_at, str) or datetime.fromisoformat(confirmed_at.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("timezone required")
    except ValueError:
        errors.append("approval.confirmed_at must be an ISO 8601 timestamp with timezone")
    if type(approval.get("profile_version")) is not int or profile.get("profile_version") != approval.get("profile_version"):
        errors.append("approval.profile_version must match the current profile_version")

    try:
        report_path = local_file(root, profile.get("review_report"), ".md")
        report = report_path.read_text(encoding="utf-8-sig")
        report_headings = set(re.findall(r"^##\s+(.+?)\s*$", report, flags=re.MULTILINE))
        for section in REQUIRED_REPORT_SECTIONS:
            if section not in report_headings:
                errors.append(f"review_report missing required section: {section}")
        if "【未填写】" in report:
            errors.append("review_report still contains unfilled template placeholders")
        for waiver in profile.get("optional_rule_waivers") or []:
            if isinstance(waiver, dict) and isinstance(waiver.get("module"), str):
                if waiver["module"] not in report:
                    errors.append(f"review_report must disclose deferred module: {waiver['module']}")
                confirmation = waiver.get("operator_confirmation")
                if isinstance(confirmation, str) and confirmation not in report:
                    errors.append(f"review_report must quote operator confirmation for: {waiver['module']}")
        snippets = re.findall(r"```html\s*\n([\s\S]*?)\n```", report, flags=re.IGNORECASE)
        if not 2 <= len(snippets) <= 4 or any(not re.search(r"<\s*[a-z][\w-]*\b", item, re.IGNORECASE)
                                                or re.search(r"【|\.\.\.|example\.(?:webp|jpe?g|png)", item, re.IGNORECASE)
                                                for item in snippets):
            errors.append("review_report must show 2-4 real, non-placeholder HTML snippets")
        digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
        if approval.get("report_sha256") != digest:
            errors.append("approval.report_sha256 must match the current review_report")
    except (OSError, ValueError) as exc:
        errors.append(f"review_report: {exc}")
    try:
        if approval.get("rules_sha256") != rules_sha256(profile, root):
            errors.append("approval.rules_sha256 must match the current local site rules; revalidate and reconfirm edits")
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"rules fingerprint unavailable: {exc}")

    site = profile.get("site") if isinstance(profile.get("site"), dict) else {}
    cms = profile.get("cms") if isinstance(profile.get("cms"), dict) else {}
    site_id = site.get("id")
    template_id = cms.get("template_id")
    if not positive_int(site_id):
        errors.append("site.id must be a positive integer")
    if not positive_int(template_id):
        errors.append("cms.template_id must be a positive integer")
    for field in ("name", "language"):
        if not isinstance(site.get(field), str) or not site[field].strip():
            errors.append(f"site.{field} is required")
    base_url = site.get("base_url")
    parsed = urlparse(base_url) if isinstance(base_url, str) else None
    if not parsed or parsed.scheme != "https" or not parsed.hostname:
        errors.append("site.base_url must be an HTTPS URL")
    if type(cms.get("draft_status")) is not int or type(cms.get("draft_sync_status")) is not int:
        errors.append("CMS draft status and sync status must be confirmed integer values")
    products = cms.get("product_ids")
    if not isinstance(products, list) or any(not isinstance(p, str) or not p.isdigit() for p in products):
        errors.append("cms.product_ids must be an array of string IDs (empty only if this site uses no product)")
    fields = cms.get("required_fields")
    if not isinstance(fields, list) or not fields or any(not isinstance(f, str) or not f.strip() for f in fields):
        errors.append("cms.required_fields must list field names confirmed for this template")
    images = profile.get("images") if isinstance(profile.get("images"), dict) else {}
    if type(images.get("enabled")) is not bool:
        errors.append("images.enabled must state whether this article type uses images")
    elif images["enabled"]:
        prefix = images.get("public_url_prefix")
        parsed_prefix = urlparse(prefix) if isinstance(prefix, str) else None
        if (not parsed_prefix or parsed_prefix.scheme != "https" or not parsed_prefix.hostname
                or not prefix.endswith("/") or parsed_prefix.hostname == "site.p.cms.afirstsoft.cn"):
            errors.append("images.public_url_prefix must be an HTTPS frontend directory ending in /")
        formats = images.get("formats")
        if not isinstance(formats, list) or not formats or any(ext not in {"jpg", "jpeg", "png", "webp"} for ext in formats):
            errors.append("images.formats must list the actual formats required by this site")
        directories = images.get("cms_directories")
        if not isinstance(directories, dict) or not directories or any(
            not isinstance(role, str) or not role or not isinstance(folder, str) or not folder.strip()
            for role, folder in directories.items()
        ):
            errors.append("images.cms_directories must map image roles to verified CMS directories")
        if images.get("publish_mode") != "picture-upload-publish-id":
            errors.append("images.publish_mode must describe the confirmed CMS image publication flow")
        try:
            image_markup = local_file(root, images.get("markup_asset"), ".html").read_text(encoding="utf-8-sig")
            if not re.search(r"<\s*(?:img|picture)\b", image_markup, re.IGNORECASE) or re.search(
                    r"【|example\.(?:webp|jpe?g|png)|IMAGE_PENDING|\.\.\.", image_markup, re.IGNORECASE):
                errors.append("images.markup_asset must contain real, non-placeholder image HTML")
        except ValueError as exc:
            errors.append(f"images.markup_asset: {exc}")

    references = profile.get("references")
    if not isinstance(references, list) or not references:
        errors.append("at least one CMS page/info reference is required")
        references = []
    page_ids = set()
    cms_reference_count = 0
    for index, reference in enumerate(references, 1):
        if not isinstance(reference, dict):
            errors.append(f"reference {index}: reference must be an object")
            continue
        kind = reference.get("kind", "cms")
        if kind == "html":
            try:
                evidence_path = local_file(root, reference.get("html_file"))
                if evidence_path.suffix.lower() not in {".html", ".htm"}:
                    errors.append(f"reference {index}: HTML file extension is required")
                raw = evidence_path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                if digest != reference.get("sha256"):
                    errors.append(f"reference {index}: HTML checksum differs from profile")
                if len(raw) < 100:
                    errors.append(f"reference {index}: HTML reference is too short")
            except (OSError, ValueError) as exc:
                errors.append(f"reference {index}: {exc}")
            continue
        if kind != "cms" or not positive_int(reference.get("page_id")):
            errors.append(f"reference {index}: kind must be cms with a positive page_id, or html with a local HTML file")
            continue
        cms_reference_count += 1
        page_id = reference["page_id"]
        if page_id in page_ids:
            errors.append(f"reference {index}: duplicate page_id {page_id}")
        page_ids.add(page_id)
        try:
            evidence_path = local_file(root, reference.get("page_info_json"), ".json")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
            page = evidence.get("data") if isinstance(evidence, dict) else None
            if not isinstance(evidence, dict) or evidence.get("code") != 0 or not isinstance(page, dict):
                errors.append(f"reference {index}: page/info response is not successful")
                continue
            if not same_positive_id(page.get("id"), page_id):
                errors.append(f"reference {index}: page ID differs from page/info")
            if not same_positive_id(page.get("site_id"), site_id):
                errors.append(f"reference {index}: site ID differs from profile")
            if not same_positive_id(page.get("template_id"), template_id):
                errors.append(f"reference {index}: template ID differs from profile")
            if str(page.get("status")) != "4":
                errors.append(f"reference {index}: CMS reference must be a published page (status 4)")
            if not isinstance(page.get("content"), str) or len(page["content"].strip()) < 100:
                errors.append(f"reference {index}: source HTML is absent or too short")
            if not evidence.get("request_id"):
                errors.append(f"reference {index}: request_id is absent")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"reference {index}: {exc}")

    if references and cms_reference_count == 0:
        discovery = profile.get("cms_discovery") if isinstance(profile.get("cms_discovery"), dict) else {}
        for field, expected_id in (("site_list_json", site_id), ("template_list_json", template_id)):
            try:
                evidence_path = local_file(root, discovery.get(field), ".json")
                evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
                if not isinstance(evidence, dict) or evidence.get("code") != 0 or not evidence.get("request_id"):
                    errors.append(f"cms_discovery.{field}: unsuccessful CMS response")
                elif not contains_id(evidence.get("data"), expected_id):
                    errors.append(f"cms_discovery.{field}: configured ID absent from CMS response")
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"cms_discovery.{field}: {exc}")
        try:
            evidence_path = local_file(root, discovery.get("template_fields_json"), ".json")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
            if not isinstance(evidence, dict) or evidence.get("code") != 0 or not evidence.get("request_id"):
                errors.append("cms_discovery.template_fields_json: unsuccessful CMS response")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"cms_discovery.template_fields_json: {exc}")

    for field, suffix in (("html_contract", ".md"), ("validator", ".py")):
        try:
            contract_path = local_file(root, profile.get(field), suffix)
            if field == "html_contract":
                contract = contract_path.read_text(encoding="utf-8-sig")
                headings = set(re.findall(r"^##\s+(.+?)\s*$", contract, flags=re.MULTILINE))
                for section in REQUIRED_CONTRACT_SECTIONS:
                    if section not in headings:
                        errors.append(f"html_contract missing required section: {section}")
                if "【未填写】" in contract:
                    errors.append("html_contract still contains unfilled template placeholders")
                errors.extend(check_rule_table(contract, root, profile.get("assets") or [],
                                               profile.get("optional_rule_waivers", [])))
        except ValueError as exc:
            errors.append(f"{field}: {exc}")
    assets = profile.get("assets")
    if not isinstance(assets, list):
        errors.append("assets must be an array, even when this article type has no fixed components")
    else:
        for index, asset in enumerate(assets, 1):
            try:
                local_file(root, asset)
            except ValueError as exc:
                errors.append(f"asset {index}: {exc}")

    examples = profile.get("validation_examples") if isinstance(profile.get("validation_examples"), dict) else {}
    if examples.get("valid_html") == examples.get("invalid_html"):
        errors.append("validation_examples must use distinct valid and invalid HTML files")
    for kind in ("valid_html", "invalid_html"):
        try:
            local_file(root, examples.get(kind), ".html")
        except ValueError as exc:
            errors.append(f"validation_examples.{kind}: {exc}")

    return {
        "pass": not errors,
        "profile_id": profile.get("profile_id"),
        "site_id": site_id,
        "article_type": profile.get("article_type"),
        "reference_count": len(references),
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_json")
    parser.add_argument("--fingerprint", action="store_true", help="Print hashes for operator-confirmed local rules; does not contact CMS")
    args = parser.parse_args()
    if args.fingerprint:
        path = Path(args.profile_json).resolve()
        try:
            profile = json.loads(path.read_text(encoding="utf-8-sig"))
            report = local_file(path.parent, profile.get("review_report"), ".md")
            result = {"profile_version": profile.get("profile_version"),
                      "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                      "rules_sha256": rules_sha256(profile, path.parent)}
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except (OSError, ValueError, TypeError) as exc:
            print(json.dumps({"pass": False, "error": str(exc)}, ensure_ascii=False))
            sys.exit(1)
        return
    result = check_profile(args.profile_json)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
