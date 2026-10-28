import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

import test_validate_site_profile as fixtures


MODULE = fixtures.MODULE
QUALITY = MODULE.ADDITIONS


class QualityAdditionTests(unittest.TestCase):
    def setUp(self):
        self.base = fixtures.SiteProfileTests()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.root = self.base.root
        self.profile = self.base.profile

    def save(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding="utf-8")

    def learning(self):
        self.save("evidence/list.json", {"code": 0, "request_id": "list-1",
                                         "data": {"list": [{"id": 800}]}})
        paths = []
        for i in range(4):
            name = f"evidence/source-{i}.json"
            paths.append(name)
            self.save(name, {"code": 0, "request_id": f"read-{i}", "data": {
                "id": 800 + i, "site_id": 123, "template_id": 456,
                "status": 5 if i == 0 else 4, "content": '<p class="sample">Text</p>'}})
        (self.root / "assets/module-0.html").write_text('<p class="sample">Text</p>', encoding="utf-8")
        value = {"schema_version": 1, "profile_id": self.profile["profile_id"],
                 "listing_query": {"site_id": 123, "page": 1, "type": 3},
                 "queried_at": "2026-10-28T12:00:00+08:00", "listing_response": "evidence/list.json",
                 "template_response": paths[0], "historical_responses": paths[1:],
                 "template_identification": "First listed style demonstration article",
                 "historical_comparison": "Three published usages compared with template",
                 "coverage": [{"signature": "class:p.sample", "disposition": "learned",
                               "reason": "Body paragraph variant", "asset": "assets/module-0.html",
                               "rule_id": "段落与列表"}]}
        self.save("learning-evidence.json", value)
        return value

    def corrections(self):
        (self.root / "validate-html.py").write_text(
            'import sys\nfrom pathlib import Path\nsys.exit(0 if "GOOD" in Path(sys.argv[1]).read_text() else 1)\n',
            encoding="utf-8")
        (self.root / "tests/good.html").write_text("<p>GOOD</p>", encoding="utf-8")
        (self.root / "tests/bad.html").write_text("<p>BAD</p>", encoding="utf-8")
        value = {"schema_version": 1, "profile_id": self.profile["profile_id"], "items": [{
            "id": "paragraph-fix", "reported_at": "2026-10-28T12:00:00+08:00",
            "user_feedback": "Keep the correct paragraph", "scope": "This site's body",
            "correct_behavior": "Use GOOD", "root_cause": "Validator missed bad paragraph",
            "status": "verified", "implementation_files": ["validate-html.py", "html-contract.md"],
            "check_kind": "mechanical", "regressions": [{"valid_html": "tests/good.html", "invalid_html": "tests/bad.html"}]}]}
        self.save("corrections.json", value)
        return value

    def test_legacy_profile_and_fingerprint_unchanged(self):
        before = MODULE.rules_sha256(self.profile, self.root)
        self.assertEqual(QUALITY.sidecar_files(self.root), [])
        self.assertTrue(self.base.check()["pass"])
        self.assertEqual(before, MODULE.rules_sha256(self.profile, self.root))

    def test_complete_template_and_three_histories(self):
        self.learning()
        self.base.seal()
        result = self.base.check()
        self.assertTrue(result["pass"], result["errors"])

    def test_unlearned_structure_is_rejected(self):
        self.learning()
        path = self.root / "evidence/source-0.json"
        source = json.loads(path.read_text())
        source["data"]["content"] += '<div class="notice-new"><code>command</code></div>'
        self.save("evidence/source-0.json", source)
        self.assertIn("unaccounted", " ".join(QUALITY.check(self.root, self.profile)))

    def test_first_article_cannot_be_silently_replaced(self):
        self.learning()
        self.save("evidence/list.json", {"code": 0, "request_id": "list", "data": {"list": [{"id": 999}]}})
        self.assertIn("first article", " ".join(QUALITY.check(self.root, self.profile)))

    def test_duplicate_history_and_wrong_site_rejected(self):
        data = self.learning()
        data["historical_responses"][1] = data["historical_responses"][0]
        self.save("learning-evidence.json", data)
        self.assertIn("distinct", " ".join(QUALITY.check(self.root, self.profile)))
        self.learning()
        source = json.loads((self.root / "evidence/source-2.json").read_text())
        source["data"]["site_id"] = 999
        self.save("evidence/source-2.json", source)
        self.assertIn("site_id", " ".join(QUALITY.check(self.root, self.profile)))

    def test_too_few_history_pages_rejected(self):
        data = self.learning()
        data["historical_responses"].pop()
        self.save("learning-evidence.json", data)
        self.assertIn("three", " ".join(QUALITY.check(self.root, self.profile)))

    def test_learned_component_must_contain_signature(self):
        self.learning()
        (self.root / "assets/module-0.html").write_text("<p>Text</p>", encoding="utf-8")
        self.assertIn("snippet lacks", " ".join(QUALITY.check(self.root, self.profile)))

    def test_full_inventory_is_not_truncated(self):
        markup = "".join(f'<div class="variant-{i}" style="padding:{i}px"></div>' for i in range(150))
        self.assertEqual(len(QUALITY.signatures(markup)), 300)

    def test_verified_correction_runs_both_regressions(self):
        self.corrections()
        self.base.seal()
        result = self.base.check()
        self.assertTrue(result["pass"], result["errors"])
        self.assertEqual(QUALITY.check_article(self.root, self.profile, "<p>GOOD</p>"), [])
        self.assertTrue(QUALITY.check_article(self.root, self.profile, "<p>BAD</p>"))

    def test_recorded_is_not_a_finished_repair(self):
        data = self.corrections()
        data["items"][0]["status"] = "recorded"
        self.save("corrections.json", data)
        self.assertIn("not verified", " ".join(QUALITY.check(self.root, self.profile)))

    def test_always_pass_validator_does_not_prove_repair(self):
        self.corrections()
        (self.root / "validate-html.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        self.assertIn("not deliberately rejected", " ".join(QUALITY.check(self.root, self.profile)))

    def test_validator_crash_does_not_prove_detection(self):
        self.corrections()
        (self.root / "validate-html.py").write_text(
            'import sys\nfrom pathlib import Path\nsys.exit(0 if "GOOD" in Path(sys.argv[1]).read_text() else 2)\n', encoding="utf-8")
        self.assertIn("exit 1 required", " ".join(QUALITY.check(self.root, self.profile)))

    def test_sidecar_and_referenced_files_bound_to_approval(self):
        self.corrections()
        self.base.seal()
        (self.root / "tests/bad.html").write_text("<p>Different BAD</p>", encoding="utf-8")
        self.assertTrue(any("rules_sha256" in x for x in self.base.check()["errors"]))

    def test_python_traceback_with_exit_one_is_not_a_valid_rejection(self):
        self.corrections()
        (self.root / "validate-html.py").write_text(
            'import sys\nfrom pathlib import Path\nif "GOOD" not in Path(sys.argv[1]).read_text():\n raise RuntimeError("broken validator")\n', encoding="utf-8")
        self.assertIn("traceback", " ".join(QUALITY.check(self.root, self.profile)))

    def test_path_escape_and_malformed_sidecar_rejected(self):
        data = self.corrections()
        data["items"][0]["implementation_files"] = ["../outside.py"]
        self.save("corrections.json", data)
        with self.assertRaises(ValueError):
            QUALITY.sidecar_files(self.root)
        data["items"] = None
        self.save("corrections.json", data)
        result = self.base.check()
        self.assertFalse(result["pass"])

    def test_draft_cli_checks_actual_content_after_successful_readback(self):
        self.corrections()
        self.base.seal()
        self.base.check()
        payload = {"site_id": 123, "template_id": 456, "product_id": [], "title": "Title",
                   "url": "article.html", "content": "<p>BAD</p>", "status": 5, "sync_status": 1}
        response = {"code": 0, "request_id": "readback", "data": copy.deepcopy(payload)}
        self.save("payload.json", payload)
        self.save("readback.json", response)
        script = Path(__file__).with_name("validate-site-draft.py")
        args = [sys.executable, str(script), str(self.root / "profile.json"), str(self.root / "payload.json"),
                "--page-info", str(self.root / "readback.json")]
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("corrected site validator", result.stdout)


if __name__ == "__main__":
    unittest.main()
