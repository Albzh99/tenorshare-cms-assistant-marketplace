"""Optional, local-only learning coverage and durable correction checks.

Legacy profiles without either sidecar retain their existing checks/fingerprint.
This module never contacts CMS or changes approval, source files, or permissions.
"""

import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path


SIDECARS = ("learning-evidence.json", "corrections.json")
STRUCTURAL_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
                   "table", "picture", "img", "svg", "pre", "code", "blockquote",
                   "video", "iframe"}


def local(root, name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("missing local evidence path")
    relative = Path(name)
    path = (root / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root.resolve()):
        raise ValueError("evidence path must stay inside profile directory")
    if not path.is_file() or not path.stat().st_size:
        raise ValueError(f"missing or empty evidence: {name}")
    return path


def read(root, name):
    value = json.loads(local(root, name).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {name}")
    return value


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.signatures = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in STRUCTURAL_TAGS:
            self.signatures.add(f"tag:{tag}")
        for name in (attrs.get("class") or "").split():
            self.signatures.add(f"class:{tag}.{name}")
        if attrs.get("style"):
            self.signatures.add(f"style:{tag}:{attrs['style']}")

    handle_startendtag = handle_starttag


def signatures(markup):
    parser = Inventory()
    parser.feed(markup)
    return parser.signatures


def sidecar_files(root):
    """Bind sidecars and every file they reference to the existing approval hash."""
    names = []
    for name in SIDECARS:
        if not (root / name).exists():
            continue
        names.append(name)
        data = read(root, name)
        array_keys = ("historical_responses", "coverage") if name == "learning-evidence.json" else ("items",)
        if any(not isinstance(data.get(key), list) for key in array_keys):
            raise ValueError(f"{name}: evidence arrays required")
        if name == "learning-evidence.json":
            names.extend([data.get("listing_response"), data.get("template_response")])
            names.extend(data.get("historical_responses", []))
            for item in data.get("coverage", []):
                if not isinstance(item, dict):
                    raise ValueError("coverage entries must be objects")
                if item.get("asset"):
                    names.append(item["asset"])
        else:
            for item in data.get("items", []):
                if not isinstance(item, dict) or not isinstance(item.get("implementation_files", []), list) or not isinstance(item.get("regressions", []), list):
                    raise ValueError("correction entries/files/regressions invalid")
                names.extend(item.get("implementation_files", []))
                for case in item.get("regressions", []):
                    if not isinstance(case, dict):
                        raise ValueError("regression entries must be objects")
                    names.extend([case.get("valid_html"), case.get("invalid_html")])
                if item.get("review_evidence"):
                    names.append(item["review_evidence"])
    for name in names:
        local(root, name)
    return names


def scope_matches(data, profile):
    return data.get("profile_id") == profile.get("profile_id") and data.get("schema_version") == 1


def page(root, name, profile, published):
    response = read(root, name)
    value = response.get("data")
    if response.get("code") != 0 or not response.get("request_id") or not isinstance(value, dict):
        raise ValueError(f"unsuccessful CMS evidence: {name}")
    for key, expected in (("site_id", profile["site"]["id"]),
                          ("template_id", profile["cms"]["template_id"])):
        if isinstance(value.get(key), bool) or str(value.get(key)) != str(expected):
            raise ValueError(f"{name}: {key} differs from profile")
    if published and str(value.get("status")) != "4":
        raise ValueError(f"{name}: historical article must be published")
    if not str(value.get("id", "")).isdigit() or not isinstance(value.get("content"), str) or not value["content"].strip():
        raise ValueError(f"{name}: page ID/content missing")
    return value


def check_learning(root, profile):
    data = read(root, "learning-evidence.json")
    if not scope_matches(data, profile):
        raise ValueError("learning evidence schema/profile differs")
    for key in ("listing_query", "queried_at", "template_identification", "historical_comparison"):
        if not data.get(key):
            raise ValueError(f"learning evidence missing {key}")
    query = data["listing_query"]
    if not isinstance(query, dict) or str(query.get("site_id")) != str(profile["site"]["id"]) or query.get("page") != 1:
        raise ValueError("template discovery requires this site's first listing page")
    response = read(root, data.get("listing_response"))
    rows = response.get("data", {}).get("list", [])
    if response.get("code") != 0 or not response.get("request_id") or not rows:
        raise ValueError("template listing evidence missing")
    template = page(root, data.get("template_response"), profile, False)
    if str(rows[0].get("id")) != str(template["id"]):
        raise ValueError("template must be the recorded first article, not a guessed newest/oldest page")
    sources = [template]
    ids = {str(template["id"])}
    histories = data.get("historical_responses", [])
    if not isinstance(histories, list) or len(histories) < 3:
        raise ValueError("read at least three additional historical articles")
    for name in histories:
        source = page(root, name, profile, True)
        if str(source["id"]) in ids:
            raise ValueError("template and historical page IDs must be distinct")
        ids.add(str(source["id"]))
        sources.append(source)
    observed = set().union(*(signatures(source["content"]) for source in sources))
    covered = set()
    contract = local(root, profile.get("html_contract")).read_text(encoding="utf-8-sig")
    for item in data.get("coverage", []):
        signature = item.get("signature")
        if signature not in observed or signature in covered:
            raise ValueError("unknown or duplicate coverage signature")
        covered.add(signature)
        if not item.get("reason"):
            raise ValueError(f"coverage needs usage/exclusion reason: {signature}")
        if item.get("disposition") == "learned":
            asset = item.get("asset")
            if asset not in profile.get("assets", []):
                raise ValueError(f"coverage asset not in profile.assets: {signature}")
            if signature not in signatures(local(root, asset).read_text(encoding="utf-8-sig")):
                raise ValueError(f"coverage snippet lacks observed structure: {signature}")
            if not item.get("rule_id") or item["rule_id"] not in contract:
                raise ValueError(f"coverage rule absent from html contract: {signature}")
        elif item.get("disposition") != "excluded":
            raise ValueError(f"unresolved coverage: {signature}")
    if observed - covered:
        raise ValueError("unaccounted template/history structures: " + ", ".join(sorted(observed - covered)))


def run_validator(root, profile, name):
    result = subprocess.run([sys.executable, str(local(root, profile.get("validator"))),
                             str(local(root, name))], capture_output=True, timeout=30)
    if b"Traceback (most recent call last)" in result.stdout + result.stderr:
        raise ValueError("site validator crashed; traceback is not a deliberate rejection")
    return result.returncode


def check_corrections(root, profile):
    data = read(root, "corrections.json")
    if not scope_matches(data, profile) or not isinstance(data.get("items"), list):
        raise ValueError("corrections schema/profile/items invalid")
    ids = set()
    for item in data["items"]:
        key = item.get("id")
        if not isinstance(key, str) or not key.strip() or key in ids:
            raise ValueError("correction IDs must be nonempty and unique")
        ids.add(key)
        for field in ("reported_at", "user_feedback", "scope", "correct_behavior", "root_cause"):
            if not item.get(field):
                raise ValueError(f"correction {key}: missing {field}")
        if item.get("status") == "superseded":
            target = next((x for x in data["items"] if x.get("id") == item.get("superseded_by")), None)
            if not target or target is item or target.get("status") != "verified":
                raise ValueError(f"correction {key}: replacement rule missing")
            continue
        if item.get("status") != "verified":
            raise ValueError(f"correction {key}: recorded/implemented is not verified; finish repair before article use")
        if not item.get("implementation_files"):
            raise ValueError(f"correction {key}: implementation evidence missing")
        for name in item["implementation_files"]:
            local(root, name)
        if item.get("check_kind") == "mechanical":
            if not item.get("regressions"):
                raise ValueError(f"correction {key}: regression pair missing")
            for case in item["regressions"]:
                valid = local(root, case.get("valid_html"))
                invalid = local(root, case.get("invalid_html"))
                if valid.read_bytes() == invalid.read_bytes():
                    raise ValueError(f"correction {key}: identical positive/negative cases")
                if run_validator(root, profile, case["valid_html"]) != 0:
                    raise ValueError(f"correction {key}: valid example rejected")
                # Exit 1 is the documented deliberate rejection; crashes/timeouts do not prove detection.
                if run_validator(root, profile, case["invalid_html"]) != 1:
                    raise ValueError(f"correction {key}: old error not deliberately rejected (exit 1 required)")
        elif item.get("check_kind") == "review":
            local(root, item.get("review_evidence"))
        else:
            raise ValueError(f"correction {key}: check_kind must be mechanical or review")


def check(root, profile):
    errors = []
    for name, checker in (("learning-evidence.json", check_learning), ("corrections.json", check_corrections)):
        if (root / name).exists():
            try:
                checker(root, profile)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{name}: {exc}")
    return errors


def check_article(root, profile, content):
    errors = []
    if (root / "corrections.json").exists():
        try:
            if not isinstance(content, str):
                raise ValueError("article content must be HTML text")
            validator = local(root, profile.get("validator"))
            with tempfile.TemporaryDirectory(prefix="cms-correction-check-") as folder:
                article = Path(folder) / "article.html"
                article.write_text(content, encoding="utf-8")
                result = subprocess.run([sys.executable, str(validator), str(article)],
                                        capture_output=True, timeout=30)
            if result.returncode != 0:
                errors.append("article fails the corrected site validator")
        except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as exc:
            errors.append(f"corrected site validator: {exc}")
    return errors
