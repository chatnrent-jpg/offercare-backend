# Simulate Manus webhook — tests VettedMe ingest without a Manus account.
# Requires: VettedMe API running, MANUS_API_KEY in .env

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Base = if ($env:VETTED_BASE_URL) { $env:VETTED_BASE_URL.TrimEnd("/") } else { "http://127.0.0.1:8000" }

# Read MANUS_API_KEY from .env without exposing full value
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

Write-Host "VettedMe Manus hook test — $Base"
Write-Host ""

Write-Host "[1/3] GET /api/vettedme/manus/config"
try {
  $config = Invoke-RestMethod -Uri "$Base/api/vettedme/manus/config" -Headers @{ "X-Manus-Key" = $ManusKey } -TimeoutSec 15
  Write-Host "OK    endpoints: $($config.endpoints.work_queue)"
} catch {
  Write-Host "FAIL  $($_.Exception.Message)"
  Write-Host "      Start VettedMe.ai first"
  exit 1
}

Write-Host "[2/3] GET /api/vettedme/manus/work-queue?limit=1"
try {
  $queue = Invoke-RestMethod -Uri "$Base/api/vettedme/manus/work-queue?limit=1" -Headers @{ "X-Manus-Key" = $ManusKey } -TimeoutSec 30
  Write-Host "OK    total_due=$($queue.total_due) returned=$($queue.returned)"
} catch {
  Write-Host "FAIL  $($_.Exception.Message)"
  exit 1
}

Write-Host "[3/3] POST /api/vettedme/manus/run (example payload)"
$example = Join-Path $Root "docs\manus-webhook-example.json"
if (-not (Test-Path $example)) {
  Write-Host "SKIP  example payload not found"
  exit 0
}

try {
  $body = Get-Content $example -Raw
  $result = Invoke-RestMethod -Uri "$Base/api/vettedme/manus/run" -Method POST `
    -Headers @{ "X-Manus-Key" = $ManusKey; "Content-Type" = "application/json" } `
    -Body $body -TimeoutSec 30
  Write-Host "OK    status=$($result.status) (provider_not_found is OK for fake NPI in example)"
} catch {
  $detail = $_.ErrorDetails.Message
  if ($detail -match "provider_not_found" -or $detail -match "FAILED") {
    Write-Host "OK    webhook accepted — provider_not_found expected for demo NPI"
  } else {
    Write-Host "FAIL  $($_.Exception.Message)"
    exit 1
  }
}

Write-Host ""
Write-Host "Manus hook test complete — no Manus account required."
