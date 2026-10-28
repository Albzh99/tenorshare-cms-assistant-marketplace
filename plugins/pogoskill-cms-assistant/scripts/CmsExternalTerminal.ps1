# System-window launcher only. No API key or clipboard value enters this file.
$ErrorActionPreference = 'Stop'

function Test-CmsExternalConsole {
  if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { return $false }
  if ([Console]::IsInputRedirected -or [Console]::IsOutputRedirected) { return $false }
  if (-not ('TenorshareCms.ConsoleWindow' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace TenorshareCms {
  public static class ConsoleWindow {
    [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
  }
}
'@
  }
  $window = [TenorshareCms.ConsoleWindow]::GetConsoleWindow()
  return ($window -ne [IntPtr]::Zero -and [TenorshareCms.ConsoleWindow]::IsWindowVisible($window))
}

function Get-CmsExternalSaveCommand {
  param([Parameter(Mandatory)][string]$SaveScript,
        [Parameter(Mandatory)][string]$ReadyFile,
        [switch]$FromClipboard, [switch]$Prompt, [switch]$KeepClipboard,
        [switch]$ValidateWindowOnly)
  $quotedScript = $SaveScript.Replace("'", "''")
  $quotedReady = $ReadyFile.Replace("'", "''")
  $command = "& '$quotedScript' -ExternalTerminal -ReadyFile '$quotedReady'"
  foreach ($name in @('FromClipboard','Prompt','KeepClipboard','ValidateWindowOnly')) {
    if (Get-Variable -Name $name -ValueOnly) { $command += " -$name" }
  }
  return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
}

function Open-CmsSaveKeyTerminal {
  param([switch]$FromClipboard, [switch]$Prompt, [switch]$KeepClipboard,
        [switch]$ValidateWindowOnly)
  if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'Windows launcher requires Windows. On macOS use cms-macos.py open-save-key-terminal.'
  }
  $readyFile = [IO.Path]::GetTempFileName()
  $shell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
  $consoleHost = Join-Path $env:SystemRoot 'System32/conhost.exe'
  $saveScript = Join-Path $PSScriptRoot 'cms-save-api-key.ps1'
  try {
    $encoded = Get-CmsExternalSaveCommand -SaveScript $saveScript -ReadyFile $readyFile -FromClipboard:$FromClipboard -Prompt:$Prompt -KeepClipboard:$KeepClipboard -ValidateWindowOnly:$ValidateWindowOnly
    $keepOpen = if ($ValidateWindowOnly) { '' } else { '-NoExit' }
    # Explicit conhost prevents a Codex panel or inherited pseudo-terminal being used.
    # A visible window is intentional here: the user must press Enter in this window.
    $arguments = '"{0}" -NoLogo -NoProfile {1} -ExecutionPolicy Bypass -EncodedCommand {2}' -f $shell,$keepOpen,$encoded
    $process = Start-Process -FilePath $consoleHost -ArgumentList $arguments -WindowStyle Normal -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
      if ((Test-Path -LiteralPath $readyFile) -and [IO.File]::ReadAllText($readyFile) -eq 'ExternalWindowsConsole') {
        $ready = $true
        break
      }
      if ($process.HasExited) { break }
      Start-Sleep -Milliseconds 200
    }
    if (-not $ready) {
      throw 'The external Windows PowerShell window did not become ready. Do not use the Codex integrated terminal as a substitute.'
    }
    if ($ValidateWindowOnly) {
      Write-Output 'External Windows PowerShell window is ready. Validation only: no clipboard or CMS credential was read or changed.'
    }
    else {
      Write-Output 'External Windows PowerShell window is ready. Copy the CMS Key and press Enter in that separate window only. This is not a save confirmation; run cms-check-api-key.ps1 after the user completes the step.'
    }
  }
  finally {
    if (Test-Path -LiteralPath $readyFile) { Remove-Item -LiteralPath $readyFile -Force }
  }
}
