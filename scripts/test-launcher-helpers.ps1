# Checks the launcher helpers in scripts/install-utils.ps1 under the PowerShell that run.bat starts
# (Windows PowerShell 5.1). Run it with:  powershell -NoProfile -File scripts\test-launcher-helpers.ps1
# The launchers were once only parsed, never executed, under 5.1, and a plain "Using CPython ..." line on
# stderr aborted every first run.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "install-utils.ps1")

function Assert-That([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw "FAILED: $Message" }
  Write-Host "ok: $Message"
}

# 1. stderr output from a native command is captured, not fatal, and the exit code survives.
$result = Invoke-InstallNative "cmd.exe" @("/c", "echo progress on stderr 1>&2 & exit 3")
Assert-That ($result.ExitCode -eq 3) "native exit code is returned (got $($result.ExitCode))"
Assert-That (($result.Output -join " ") -match "progress on stderr") "stderr text is captured as a plain line"
Assert-That ($ErrorActionPreference -eq "Stop") "the caller's ErrorActionPreference is restored"

$clean = Invoke-InstallNative "cmd.exe" @("/c", "echo fine & exit 0")
Assert-That ($clean.ExitCode -eq 0) "a successful command returns exit code 0"

# 2. An interrupted setup's .venv (no Python inside) is removed; a working one is never touched.
$scratch = Join-Path ([IO.Path]::GetTempPath()) ("launcher-helper-test-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $scratch | Out-Null
try {
  Initialize-Install -RepositoryRoot $scratch -ProductName "helper test"

  New-Item -ItemType Directory -Path (Join-Path $scratch ".venv\Lib") -Force | Out-Null
  Remove-IncompleteVenv $scratch
  Assert-That (-not (Test-Path -LiteralPath (Join-Path $scratch ".venv"))) "a .venv without Python is removed"

  New-Item -ItemType Directory -Path (Join-Path $scratch ".venv\Scripts") -Force | Out-Null
  Set-Content -LiteralPath (Join-Path $scratch ".venv\Scripts\python.exe") -Value "stub"
  Remove-IncompleteVenv $scratch
  Assert-That (Test-Path -LiteralPath (Join-Path $scratch ".venv\Scripts\python.exe")) "a .venv with Python is left alone"

  Remove-IncompleteVenv (Join-Path $scratch "does-not-exist")
  Assert-That $true "a missing folder is a no-op"
} finally {
  Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "All launcher helper checks passed."
