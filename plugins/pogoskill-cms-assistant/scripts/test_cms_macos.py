import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("cms_macos", Path(__file__).with_name("cms-macos.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MacTransportTests(unittest.TestCase):
    def test_save_key_rejects_codex_integrated_terminal(self):
        with patch.dict(MODULE.os.environ, {"TERM_PROGRAM": "Codex",
                                                "TENORSHARE_CMS_TERMINAL_LAUNCH": "1"}):
            with self.assertRaisesRegex(RuntimeError, "Terminal.app"):
                MODULE.require_external_terminal()
        with patch.dict(MODULE.os.environ, {"TERM_PROGRAM": "Apple_Terminal",
                                                "TENORSHARE_CMS_TERMINAL_LAUNCH": "1"}):
            MODULE.require_external_terminal()
        with patch.dict(MODULE.os.environ, {"TERM_PROGRAM": "Apple_Terminal",
                                                "TENORSHARE_CMS_TERMINAL_LAUNCH": ""}):
            with self.assertRaisesRegex(RuntimeError, "Terminal.app"):
                MODULE.require_external_terminal()

    def test_external_terminal_launcher_contains_no_key_or_clipboard_value(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(MODULE, "require_macos"), patch.object(
                    MODULE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                MODULE.open_save_key_terminal(temp)
            command = run.call_args.args[0]
            self.assertEqual(command[:3], ["open", "-a", "Terminal"])
            launcher = Path(command[3])
            self.assertEqual(launcher.parent, Path(temp))
            self.assertEqual(launcher.suffix, ".command")
            content = launcher.read_text(encoding="utf-8")
            self.assertIn("save-key", content)
            self.assertNotIn("pbpaste", content)
            self.assertNotIn("X-API-KEY", content)

    def test_external_terminal_launch_failure_removes_temp_script(self):
        with tempfile.TemporaryDirectory() as temp:
            failed = subprocess.CompletedProcess([], 1, stderr="Terminal unavailable")
            with patch.object(MODULE, "require_macos"), patch.object(
                    MODULE.subprocess, "run", return_value=failed):
                with self.assertRaisesRegex(RuntimeError, "Could not open macOS Terminal.app"):
                    MODULE.open_save_key_terminal(temp)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_multipart_contains_files_and_no_key(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "article-image.jpg"
            file.write_bytes(b"image-bytes")
            body, content_type = MODULE.multipart_image_body(44, "blog", [file])
        self.assertIn(b'filename="article-image.jpg"', body)
        self.assertIn(b"image-bytes", body)
        self.assertIn(b'name="site_id"', body)
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))

    def test_rejects_invalid_file_name(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "Bad Name.JPG"
            file.write_bytes(b"bytes")
            with self.assertRaises(ValueError):
                MODULE.multipart_image_body(44, "blog", [file])

    def test_response_requires_business_success_and_request_id(self):
        self.assertEqual(0, MODULE.checked_response(b'{"code":0,"request_id":"ok"}', "/cms/site/list")["code"])
        with self.assertRaises(RuntimeError):
            MODULE.checked_response(b'{"code":0}', "/cms/site/list")
        with self.assertRaises(RuntimeError):
            MODULE.checked_response(b'{"code":60001,"request_id":"bad"}', "/cms/site/list")

    def test_visible_newline_tokens_rejected_before_request(self):
        with self.assertRaises(ValueError):
            MODULE.request_json("/cms/page/add", {"content": "part 1\\npart 2"}, api_key="placeholder")

    def test_learning_mode_rejects_mutations_before_network(self):
        for endpoint in ("/cms/page/add", "/cms/page/update", "/cms/page/make",
                         "/cms/pagepublish/publish", "/cms/picture/upload", "/cms/file/createdir"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                MODULE.learning_request_json(endpoint, {}, api_key="placeholder")

    def test_normal_mode_can_reach_page_write_and_image_publish(self):
        with patch.object(MODULE, "cms_post", return_value={"code": 0, "request_id": "mock"}) as post:
            MODULE.request_json("/cms/page/add", {"content": "<p>Ready draft</p>"}, api_key="placeholder")
            self.assertEqual("/cms/page/add", post.call_args.args[0])
            MODULE.request_json("/cms/pagepublish/publish", {"id": 42},
                                api_key="placeholder", allow_image_publish=True)
            self.assertEqual("/cms/pagepublish/publish", post.call_args.args[0])

    def test_learning_mode_whitelist_matches_windows(self):
        script = Path(__file__).with_name("cms-learning-request.ps1").read_text(encoding="utf-8-sig")
        import re
        windows_paths = set(re.findall(r"'(/cms/[a-z0-9/_-]+)'", script))
        self.assertEqual(MODULE.LEARNING_READ_ONLY_PATHS, windows_paths)


if __name__ == "__main__":
    unittest.main()
