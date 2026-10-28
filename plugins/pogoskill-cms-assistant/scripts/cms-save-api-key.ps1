param(
  [Alias('ApiKeyFromClipboard')][switch]$FromClipboard,
  [switch]$Prompt,
  [switch]$KeepClipboard,
  [switch]$ExternalTerminal,
  [string]$ReadyFile,
  [switch]$ValidateWindowOnly
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'CmsExternalTerminal.ps1')
if (-not $ExternalTerminal) {
  Open-CmsSaveKeyTerminal -FromClipboard:$FromClipboard -Prompt:$Prompt -KeepClipboard:$KeepClipboard -ValidateWindowOnly:$ValidateWindowOnly
  return
}
if (-not (Test-CmsExternalConsole)) {
  throw 'Key entry requires a separate visible Windows PowerShell window, not the Codex integrated terminal. Run cms-save-api-key.ps1 without -ExternalTerminal to open it automatically.'
}
if ($ValidateWindowOnly) {
  if ($ReadyFile) { [IO.File]::WriteAllText($ReadyFile, 'ExternalWindowsConsole') }
  Write-Output 'External Windows console verified. No clipboard or CMS credential was read or changed.'
  return
}
. (Join-Path $PSScriptRoot 'CmsCredential.ps1')
$Host.UI.RawUI.WindowTitle = 'Tenorshare CMS Key - System PowerShell'
if ($ReadyFile) { [IO.File]::WriteAllText($ReadyFile, 'ExternalWindowsConsole') }

$keyPtr = [IntPtr]::Zero
$apiKey = $null
try {
  if ($Prompt) {
    $secureKey = Read-Host 'CMS API key' -AsSecureString
    $keyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    $apiKey = ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPtr)).Trim()
  }
  else {
    if (-not $FromClipboard) {
      Write-Host ''
      Write-Host '请现在复制完整的 CMS API Key。'
      [void](Read-Host '复制完成后，回到这个窗口直接按 Enter')
    }
    $apiKey = ([string](Get-Clipboard -Raw)).Trim()
    if ([string]::IsNullOrWhiteSpace($apiKey)) {
      throw 'Clipboard is empty. Copy the complete CMS API key before pressing Enter, then try again.'
    }
  }

  $saveResult = Set-CmsStoredApiKey -ApiKey $apiKey
  if (-not $KeepClipboard) { Set-Clipboard -Value ' ' }
  if ($saveResult.CredentialManagerSaved) {
    Write-Host 'CMS API key saved in Windows Credential Manager and the protected user-only fallback store.'
  }
  else {
    Write-Host 'CMS API key saved in the protected user-only fallback store.'
    if ($saveResult.CredentialManagerErrorCode -eq 1312) {
      Write-Host 'Windows Credential Manager was unavailable in this logon session (1312); future CMS tasks will use the fallback automatically.'
    }
    elseif ($null -ne $saveResult.CredentialManagerErrorCode) {
      Write-Host ("Windows Credential Manager was unavailable (error {0}); future CMS tasks will use the fallback automatically." -f $saveResult.CredentialManagerErrorCode)
    }
  }
  if (-not $KeepClipboard) { Write-Host 'Clipboard cleared.' }
}
finally {
  if ($keyPtr -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPtr)
  }
  $apiKey = $null
}

