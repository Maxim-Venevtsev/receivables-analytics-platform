$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\debt_management_BI"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PrivateKey = Join-Path $env:USERPROFILE ".ssh\debt_bi_local_sync"

Set-Location $ProjectRoot

Write-Host ""
Write-Host "============================================"
Write-Host " Debt Management BI - Local Sync DRY RUN"
Write-Host "============================================"
Write-Host ""

if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Project Python was not found:"
    Write-Host $PythonExe
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Test-Path $PrivateKey)) {
    Write-Host "ERROR: Local Sync SSH key was not found:"
    Write-Host $PrivateKey
    Read-Host "Press Enter to close"
    exit 1
}

$agent = Get-Service ssh-agent -ErrorAction SilentlyContinue

if ($null -eq $agent -or $agent.Status -ne "Running") {
    Write-Host "ERROR: Windows ssh-agent is not running."
    Read-Host "Press Enter to close"
    exit 1
}

$KeyInfo = & ssh-keygen -lf $PrivateKey 2>$null

if ($LASTEXITCODE -ne 0 -or -not $KeyInfo) {
    Write-Host "ERROR: The Local Sync SSH key fingerprint could not be read."
    Read-Host "Press Enter to close"
    exit 1
}

$KeyFingerprint = ($KeyInfo -split "\s+")[1]
$LoadedKeys = & ssh-add -l 2>$null
$KeyLoaded = $LASTEXITCODE -eq 0 -and $LoadedKeys -match [regex]::Escape($KeyFingerprint)

if (-not $KeyLoaded) {
    Write-Host "The Local Sync key must be unlocked."
    Write-Host "Enter its passphrase below."
    Write-Host ""

    & ssh-add $PrivateKey

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: The SSH key could not be loaded."
        Read-Host "Press Enter to close"
        exit 1
    }
}

Write-Host ""
Write-Host "Checking synchronization plan without changes..."
Write-Host ""

& $PythonExe -m src.automation.local_sync.cli --dry-run --order oldest
$SyncExitCode = $LASTEXITCODE

Write-Host ""

if ($SyncExitCode -eq 0) {
    Write-Host "============================================"
    Write-Host " Dry run completed successfully"
    Write-Host " No files or databases were changed"
    Write-Host "============================================"
} else {
    Write-Host "============================================"
    Write-Host " Dry run FAILED"
    Write-Host " Exit code: $SyncExitCode"
    Write-Host "============================================"
}

Write-Host ""
Read-Host "Press Enter to close"
exit $SyncExitCode
