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
    def test_keychain_param_error_uses_security_cli_without_secret_in_argv(self):
        class ParamErrorKeychain:
            def SecKeychainFindGenericPassword(self, *_args):
                return -50
        key = "AFS1727-0001-example-valid-key"
        with patch.object(MODULE, "require_macos"), patch.object(
                MODULE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=key)) as run:
            self.assertEqual(MODULE.read_key(api=ParamErrorKeychain()), key)
        self.assertEqual(run.call_args.args[0][:3],
                         ["/usr/bin/security", "find-generic-password", "-w"])
        self.assertNotIn(key, run.call_args.args[0])

    def test_save_key_rejects_codex_integrated_terminal(self):
        with patch.dict(MODULE.os.environ, {"TERM_PROGRAM": "Codex",
                                                "TENORSHARE_CMS_TERMINAL_LAUNCH": "1"}):
            with self.assertRaisesRegex(RuntimeError, "Terminal.app"):
                MODULE.require_external_terminal()
        with patch.dict(MODULE.os.environ, {"TERM_PROGRAM": "Apple_Terminal",
                                                "TENORSHARE_CMS_TERMINAL_LAUNCH": "1"}), patch.object(MODULE.sys.stdin, "isatty", return_value=True):
            MODULE.require_external_terminal()
        with patch.dict(MODULE.os.environ, {"TERM_PROGRAM": "Apple_Terminal",
                                                "TENORSHARE_CMS_TERMINAL_LAUNCH": ""}):
            with self.assertRaisesRegex(RuntimeError, "Terminal.app"):
                MODULE.require_external_terminal()

    def test_inherited_terminal_environment_without_real_tty_is_rejected(self):
        with patch.dict(MODULE.os.environ, {"TERM_PROGRAM": "Apple_Terminal",
                                           "TENORSHARE_CMS_TERMINAL_LAUNCH": "1"}), patch.object(
                MODULE.sys.stdin, "isatty", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Terminal.app"):
                MODULE.require_external_terminal()

    def test_direct_save_command_in_codex_opens_system_terminal_without_reading_key(self):
        with patch.object(MODULE, 'require_macos'), patch.object(MODULE.sys, 'argv', ['cms-macos.py', 'save-key']), patch.dict(
                MODULE.os.environ, {'TERM_PROGRAM': 'Codex', 'TENORSHARE_CMS_TERMINAL_LAUNCH': ''}), patch.object(
                MODULE, 'open_save_key_terminal') as opened, patch.object(MODULE, 'save_key') as saved, patch.object(
                MODULE.subprocess, 'run') as transport:
            MODULE.main()
        opened.assert_called_once()
        saved.assert_not_called()
        transport.assert_not_called()

    def test_zsh_launcher_does_not_assign_readonly_status_parameter(self):
        content = MODULE.save_key_terminal_script('/usr/bin/python3', '/tmp/cms script.py', Path('/tmp/ready'))
        self.assertNotIn('\nstatus=$?', content)
        self.assertIn('cms_save_status=$?', content)
        self.assertIn('[ ! -t 0 ]', content)

    def test_external_terminal_launcher_contains_no_key_or_clipboard_value(self):
        with tempfile.TemporaryDirectory() as temp:
            observed = {}
            def launch(command, **_kwargs):
                launcher = Path(command[3])
                observed["command"] = command
                observed["content"] = launcher.read_text(encoding="utf-8")
                launcher.with_suffix(".ready").write_text("Apple_Terminal", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0)
            with patch.object(MODULE, "require_macos"), patch.object(
                    MODULE.subprocess, "run", side_effect=launch), patch("builtins.print") as announcement:
                MODULE.open_save_key_terminal(temp)
            announcement.call_args.args[0].encode("cp1252")
            command = observed["command"]
            self.assertEqual(command[:3], ["open", "-a", "Terminal"])
            launcher = Path(command[3])
            self.assertEqual(launcher.parent, Path(temp))
            self.assertEqual(launcher.suffix, ".command")
            content = observed["content"]
            self.assertIn("save-key", content)
            self.assertIn("TERM_PROGRAM", content)
            self.assertNotIn("pbpaste", content)
            self.assertNotIn("X-API-KEY", content)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_external_terminal_launch_failure_removes_temp_script(self):
        with tempfile.TemporaryDirectory() as temp:
            failed = subprocess.CompletedProcess([], 1, stderr="Terminal unavailable")
            with patch.object(MODULE, "require_macos"), patch.object(
                    MODULE.subprocess, "run", return_value=failed):
                with self.assertRaisesRegex(RuntimeError, "Could not open macOS Terminal.app"):
                    MODULE.open_save_key_terminal(temp)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_open_success_without_external_prompt_is_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(MODULE, "require_macos"), patch.object(
                    MODULE.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)), patch.object(
                    MODULE, "wait_for_external_terminal", return_value=False):
                with self.assertRaisesRegex(RuntimeError, "did not start the key prompt"):
                    MODULE.open_save_key_terminal(temp)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_curl_transport_keeps_key_out_of_argv_and_files(self):
        key = "AFS1727-0001-example-valid-key"
        seen = {}
        def run(command, **kwargs):
            seen["argv"] = command
            seen["stdin"] = kwargs["input"]
            Path(command[command.index("--output") + 1]).write_bytes(b'{"code":0,"request_id":"ok"}')
            Path(command[command.index("--dump-header") + 1]).write_bytes(b"HTTP/2 200\r\n")
            seen["body"] = Path(command[command.index("--data-binary") + 1][1:]).read_bytes()
            return subprocess.CompletedProcess(command, 0, stdout="200", stderr="")
        with patch.object(MODULE.shutil, "which", return_value="/usr/bin/curl"), patch.object(
                MODULE.subprocess, "run", side_effect=run):
            result = MODULE.cms_post("/cms/site/list", b"{}", api_key=key)
        self.assertEqual(result["request_id"], "ok")
        self.assertEqual(seen["body"], b"{}")
        self.assertNotIn(key, " ".join(seen["argv"]))
        self.assertIn(key, seen["stdin"])

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
