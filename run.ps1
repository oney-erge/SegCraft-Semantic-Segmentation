param(
  [ValidateSet("run", "doctor", "repair", "docker", "stop", "logs")]
  [string]$Action = "run",
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
. .\scripts\install-utils.ps1
Initialize-Install -RepositoryRoot $PSScriptRoot -ProductName "SegCraft"
trap { Write-InstallFailure $_; Exit-InstallLock; exit 1 }
$UvVersion = "0.12.5"
$Url = "http://127.0.0.1:8000"
function Resolve-Uv {
  $command = Get-Command uv -ErrorAction SilentlyContinue
  foreach ($candidate in @($(if ($command) { $command.Source }), "$env:USERPROFILE\.local\bin\uv.exe", "$env:USERPROFILE\.cargo\bin\uv.exe")) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
  }
  return $null
}
function Ensure-Uv {
  $uv = Resolve-Uv
  if ($uv) { return $uv }
  $installer = Join-Path $env:TEMP "segcraft-uv-$UvVersion.ps1"
  try {
    Save-InstallDownload -Url "https://astral.sh/uv/$UvVersion/install.ps1" -Destination $installer -Label "uv download"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
  } finally { Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue }
  $uv = Resolve-Uv
  if (-not $uv) { throw "uv installed but could not be located." }
  return $uv
}
function Wait-Ready {
  for ($i = 0; $i -lt 120; $i++) {
    if (Test-Ready) { return $true }
    Start-Sleep -Milliseconds 500
  }
  return $false
}
# Port 8000 is also LocalDeploy's default, and it answers /health too, so "something answered" is not enough:
# only SegCraft says service = segcraft. Otherwise this launcher reported SegCraft as already running and opened LocalDeploy.
function Test-Ready { try { return ((Invoke-RestMethod -Uri "$Url/health" -TimeoutSec 2).service -eq "segcraft") } catch { return $false } }

# The locked PyTorch is the PyPI wheel, which is CPU-only on Windows, so an NVIDIA GPU would never be used.
# On a machine with an NVIDIA GPU this picks the PyTorch CUDA index that matches the driver. It returns
# $null (keep the CPU build) with no GPU, when the driver is too old, or when SEGCRAFT_CPU_ONLY=1.
# SEGCRAFT_TORCH_INDEX_URL overrides the choice. Never fails the install.
function Get-CudaTorchIndex {
  if ($env:SEGCRAFT_CPU_ONLY -eq "1") { return $null }
  if ($env:SEGCRAFT_TORCH_INDEX_URL) { return $env:SEGCRAFT_TORCH_INDEX_URL }
  if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $null }
  try {
    $smi = & nvidia-smi 2>$null
    $match = ($smi | Select-String -Pattern 'CUDA Version:\s*([0-9]+)\.([0-9]+)').Matches
    if ($match.Count -eq 0) { return $null }
    $version = [double]("{0}.{1}" -f $match[0].Groups[1].Value, $match[0].Groups[2].Value)
    if ($version -ge 13.0) { return "https://download.pytorch.org/whl/cu130" }
    if ($version -ge 12.6) { return "https://download.pytorch.org/whl/cu126" }
  } catch {}
  return $null
}
function Get-LockedTorchVersion {
  $match = [regex]::Match((Get-Content -LiteralPath "uv.lock" -Raw), '(?m)^name = "torch"\r?\nversion = "([^"]+)"')
  if ($match.Success) { return $match.Groups[1].Value }
  return $null
}

if ($Action -in @("docker", "stop", "logs")) {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  $engineRunning = $false
  if ($docker) { $null = Invoke-NativeQuiet docker @("info"); $engineRunning = ($LASTEXITCODE -eq 0) }
  if ($Action -eq "stop" -and -not $engineRunning) { Write-Host "The native server runs in the foreground. Press Ctrl+C in its terminal to stop it."; exit 0 }
  if ($Action -eq "logs" -and -not $engineRunning) { Write-Host "The native server writes logs to its foreground terminal."; exit 0 }
  if (-not $docker) { throw "Docker is not installed." }
  if (-not $engineRunning) { throw "Docker is installed but its engine is not running." }
  if ($Action -eq "stop") { docker compose down; exit $LASTEXITCODE }
  if ($Action -eq "logs") { docker compose logs --follow; exit $LASTEXITCODE }
  Enter-InstallLock
  Assert-InstallFreeSpace -Path $PSScriptRoot -RequiredGB 3
  docker compose up --detach --build
  if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed to start SegCraft." }
  if (-not (Wait-Ready)) { docker compose logs; throw "SegCraft did not become healthy at $Url." }
  Complete-Install
  Write-Host "SegCraft is ready at $Url" -ForegroundColor Green
  if (-not $NoBrowser) { Start-Process $Url }
  exit 0
}

$uv = Resolve-Uv
if ($Action -eq "doctor") {
  if (-not $uv) { throw "uv is missing. Run .\run.ps1 once." }
  & $uv run --frozen --no-sync segcraft doctor
  exit $LASTEXITCODE
}
Enter-InstallLock
Assert-InstallFreeSpace -Path $PSScriptRoot -RequiredGB 3
if (-not $uv) { $uv = Ensure-Uv }
Remove-IncompleteVenv $PSScriptRoot
$python = ".\.venv\Scripts\python.exe"
$cudaIndex = Get-CudaTorchIndex
# uv sync restores the locked CPU wheel, so once the CUDA build is in, sync only runs when the lock or the
# chosen index changes (or on "repair"). Without an NVIDIA GPU nothing changes: sync runs on every launch.
$marker = ".\.venv\.segcraft-cuda"
$fingerprint = "$((Get-FileHash -LiteralPath uv.lock -Algorithm SHA256).Hash)|$cudaIndex"
$cudaCurrent = $cudaIndex -and $Action -ne "repair" -and (Test-Path -LiteralPath $python) -and
  (Test-Path -LiteralPath $marker) -and ((Get-Content -LiteralPath $marker -Raw).Trim() -eq $fingerprint)
if ($cudaCurrent) {
  Write-Host "Dependencies are already up to date (CUDA PyTorch)."
} else {
  $syncArgs = @("sync", "--frozen", "--extra", "web")
  if ($Action -eq "repair") { $syncArgs += "--reinstall" }
  Invoke-InstallRetry "dependency synchronization" {
    $result = Invoke-InstallNative $uv $syncArgs
    if ($result.ExitCode -ne 0) { throw "uv sync failed: $($result.Output -join [Environment]::NewLine)" }
    $result.Output | Write-Host
  }
  # The sync put the locked CPU wheel back, so any earlier "CUDA installed" marker is stale.
  Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
  if ($cudaIndex) {
    Write-Host "==> NVIDIA GPU found: installing the CUDA build of PyTorch (a large download the first time)" -ForegroundColor Cyan
    $lockedTorch = Get-LockedTorchVersion
    $torchSpec = if ($lockedTorch) { "torch==$lockedTorch" } else { "torch" }
    Invoke-InstallRetry "CUDA PyTorch installation" {
      $result = Invoke-InstallNative $uv @("pip", "install", "--python", $python, $torchSpec, "torchvision", "--index-url", $cudaIndex, "--reinstall-package", "torch", "--reinstall-package", "torchvision")
      if ($result.ExitCode -ne 0) { throw "CUDA PyTorch installation failed: $($result.Output -join [Environment]::NewLine)" }
      $result.Output | Write-Host
    }
    Set-Content -LiteralPath $marker -Value $fingerprint -NoNewline
  }
}
Complete-Install
if (Test-Ready) {
  Write-Host "SegCraft is already running at $Url" -ForegroundColor Green
  if (-not $NoBrowser) { Start-Process $Url }
  exit 0
}
$env:SEGCRAFT_OPEN_BROWSER = if ($NoBrowser) { "0" } else { "1" }
& $uv run --frozen --no-sync segcraft-web
exit $LASTEXITCODE
