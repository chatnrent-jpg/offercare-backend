# VettedCare.ai — local Docker deploy (Step 24)
# Usage: .\scripts\deploy-local.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — edit ADMIN_API_KEY and secrets before production."
}

Write-Host "Building and starting VettedCare.ai (db + api)..."
docker compose up -d --build

$deadline = (Get-Date).AddSeconds(90)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5
        if ($resp.status -eq "ok") {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 3
    }
}

if (-not $healthy) {
    Write-Error "API did not become healthy within 90s. Check: docker compose logs api"
}

Write-Host ""
Write-Host "VettedCare.ai is online."
Write-Host "  Health:  http://127.0.0.1:8000/health"
Write-Host "  Admin:   http://127.0.0.1:8000/admin"
Write-Host "  Portal:  http://127.0.0.1:8000/portal"
Write-Host "  Swagger: http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Live Twilio webhook (set PUBLIC_BASE_URL to your HTTPS domain first):"
Write-Host "  POST https://YOUR-DOMAIN/shift-sniper/twilio/sms"
Write-Host ""
Write-Host "Open admin Deploy walkthrough for full checklist: /admin"
