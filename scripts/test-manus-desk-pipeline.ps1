# Manus desk pipeline API smoke test — staging orchestrator over HTTP.
# Requires: VettedMe API running, MANUS_API_KEY in .env, staging JSON under logs/manus/

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Base = if ($env:VETTED_BASE_URL) { $env:VETTED_BASE_URL.TrimEnd("/") } else { "http://127.0.0.1:8000" }

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

$Headers = @{ "X-Manus-Key" = $ManusKey; "Content-Type" = "application/json" }

Write-Host "VettedMe Manus desk pipeline test — $Base"
Write-Host ""

Write-Host "[1/3] GET /api/vettedme/manus/desk/handoff"
try {
  $handoff = Invoke-RestMethod -Uri "$Base/api/vettedme/manus/desk/handoff" -Headers $Headers -TimeoutSec 30
  Write-Host "OK    run endpoint: $($handoff.api_endpoints.run)"
} catch {
  Write-Host "FAIL  $($_.Exception.Message)"
  exit 1
}

Write-Host "[2/3] POST /api/vettedme/manus/desk/run (full pipeline)"
try {
  $body = @{ pipeline = "full" } | ConvertTo-Json
  $run = Invoke-RestMethod -Method Post -Uri "$Base/api/vettedme/manus/desk/run" -Headers $Headers -Body $body -TimeoutSec 60
  Write-Host "OK    status: $($run.status) · run_id: $($run.run_id)"
  Write-Host "      log: $($run.log_path)"
} catch {
  Write-Host "FAIL  $($_.Exception.Message)"
  exit 1
}

Write-Host "[3/3] POST /api/vettedme/manus/desk/run (penalty audit)"
try {
  $body = @{
    pipeline = "penalty"
    facility_id = "MD-SNF-ARBOR-RIDGE"
    provider_id = "CNA-MD-88421"
    total_hours_worked = 45
  } | ConvertTo-Json
  $penalty = Invoke-RestMethod -Method Post -Uri "$Base/api/vettedme/manus/desk/run" -Headers $Headers -Body $body -TimeoutSec 60
  $fee = $penalty.result.audit.calculated_penalty_fee
  Write-Host "OK    penalty fee: `$$fee"
} catch {
  Write-Host "FAIL  $($_.Exception.Message)"
  exit 1
}

Write-Host ""
Write-Host "All desk pipeline checks passed."
