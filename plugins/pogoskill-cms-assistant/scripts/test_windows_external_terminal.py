import base64
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@unittest.skipUnless(sys.platform == 'win32', 'Windows PowerShell launcher')
class WindowsExternalTerminalTests(unittest.TestCase):
    def run_ps(self, command):
        shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
        return subprocess.run([str(shell), '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                               '-EncodedCommand', encoded], capture_output=True, timeout=35)

    def library(self):
        return ". '" + str(ROOT / 'CmsExternalTerminal.ps1').replace("'", "''") + "'; "

    def test_command_roundtrips_paths_and_contains_no_key(self):
        result = self.run_ps(self.library() + "Get-CmsExternalSaveCommand -SaveScript \"C:/test's files/cms-save-api-key.ps1\" -ReadyFile 'C:/temp/ready' -ValidateWindowOnly")
        self.assertEqual(result.returncode, 0, result.stderr)
        command = base64.b64decode(result.stdout.strip()).decode('utf-16-le')
        self.assertIn("test''s files", command)
        self.assertIn('-ExternalTerminal', command)
        self.assertIn('-ValidateWindowOnly', command)
        self.assertNotIn('AFS', command)
        self.assertNotIn('Get-Clipboard', command)

    def test_integrated_or_piped_session_cannot_read_clipboard(self):
        path = str(ROOT / 'cms-save-api-key.ps1').replace("'", "''")
        result = self.run_ps(f"& '{path}' -ExternalTerminal -FromClipboard")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Codex integrated terminal', result.stderr)
        self.assertNotIn(b'Clipboard is empty', result.stderr)

    def test_launcher_uses_visible_conhost_and_waits_for_child_handshake(self):
        command = self.library() + r'''
function Start-Process {
 param($FilePath,$ArgumentList,$WindowStyle,[switch]$PassThru)
 if($FilePath -notmatch 'conhost.exe$' -or $WindowStyle -ne 'Normal') { throw 'not an external visible console' }
 $encoded = ($ArgumentList -split ' ')[-1]
 $decoded = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($encoded))
 $ready = [regex]::Match($decoded, "-ReadyFile '([^']+)'").Groups[1].Value
 [IO.File]::WriteAllText($ready,'ExternalWindowsConsole')
 return [pscustomobject]@{HasExited=$false}
}
Open-CmsSaveKeyTerminal -ValidateWindowOnly
'''
        result = self.run_ps(command)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'External Windows PowerShell window is ready', result.stdout)

    def test_process_start_without_handshake_is_not_success(self):
        command = self.library() + r'''
function Start-Process {
 param($FilePath,$ArgumentList,$WindowStyle,[switch]$PassThru)
 return [pscustomobject]@{HasExited=$true}
}
Open-CmsSaveKeyTerminal -ValidateWindowOnly
'''
        result = self.run_ps(command)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'did not become ready', result.stderr)

    def test_syntax_valid_on_windows_powershell(self):
        for name in ['CmsExternalTerminal.ps1', 'cms-save-api-key.ps1']:
            path = str(ROOT / name).replace("'", "''")
            result = self.run_ps(f"$tokens=$null; $errors=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$tokens,[ref]$errors); if($errors.Count){{throw 'PowerShell syntax invalid'}}")
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
