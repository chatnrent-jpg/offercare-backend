# Montgomery SNF CNA live call-out dispatch - Manus HTTP smoke test.

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

Write-Host ("Montgomery live call-out test - " + $Base)
Write-Host ""

Write-Host "[1/2] GET handoff"
$handoff = Invoke-RestMethod -Uri ($Base + "/api/vettedcare/manus/desk/handoff") -Headers $Headers -TimeoutSec 30
Write-Host ("OK    " + $handoff.api_endpoints.run_production_live)
Write-Host ""

Write-Host "[2/2] POST run-production-live"
$body = @{ original_provider_id = "CNA-MD-88421" } | ConvertTo-Json
$result = Invoke-RestMethod -Method Post -Uri ($Base + "/api/vettedcare/manus/desk/run-production-live") -Headers $Headers -Body $body -TimeoutSec 60
Write-Host ("OK    live_execution=" + $result.live_execution + " status=" + $result.dispatch.status + " backups=" + $result.dispatch.backup_candidates.Count)
if ($result.notify_cascade) {
  Write-Host ("OK    notify=" + $result.notify_cascade.status + " dry_run=" + $result.notify_cascade.sms_dry_run)
  if ($result.notify_cascade.cascade) {
    $c = $result.notify_cascade.cascade
    Write-Host ("OK    cascade=" + $c.status + " sent=" + $c.sent_count + " wait=" + $c.seconds_until_eligible + "s dispatch_id=" + $c.dispatch_id)
  }
}
Write-Host ""
Write-Host "Done. Check logs/manus/ for backup dispatch files."
