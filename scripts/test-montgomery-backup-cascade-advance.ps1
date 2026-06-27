# Advance Montgomery backup notify cascade after sniper timeout (dry-run safe).

param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$DispatchId = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$ManusKey = $null
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*MANUS_API_KEY=(.+)$') { $ManusKey = $Matches[1].Trim() }
    }
}
if (-not $ManusKey) {
    Write-Host "FAIL  MANUS_API_KEY not found in .env"
    exit 1
}

if (-not $DispatchId) {
    $activePath = Join-Path $Root "logs\manus\backup_cascade_active.json"
    if (-not (Test-Path $activePath)) {
        Write-Host "FAIL  No backup_cascade_active.json - run live call-out first"
        exit 1
    }
    $active = Get-Content $activePath -Raw | ConvertFrom-Json
    $keys = @($active.cascades.PSObject.Properties.Name)
    if ($keys.Count -eq 0) {
        Write-Host "FAIL  No active backup cascades"
        exit 1
    }
    $DispatchId = $keys[-1]
    Write-Host ("Using latest dispatch_id: " + $DispatchId)
}

$body = @{ dispatch_id = $DispatchId; force = [bool]$Force } | ConvertTo-Json
$headers = @{ "X-Manus-Key" = $ManusKey; "Content-Type" = "application/json" }

$result = Invoke-RestMethod -Method Post -Uri ($BaseUrl + "/api/vettedcare/manus/desk/advance-backup-cascade") -Headers $headers -Body $body -TimeoutSec 60
Write-Host ("OK    status=" + $result.status + " message=" + $result.message)
if ($result.cascade) {
    Write-Host ("OK    cascade_status=" + $result.cascade.status + " sent=" + $result.cascade.sent_count + " wait=" + $result.cascade.seconds_until_eligible + "s")
}
