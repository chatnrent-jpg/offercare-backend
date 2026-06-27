# Run as Administrator: sets postgres user password after silent PostgreSQL install.
# Usage: Right-click PowerShell -> Run as administrator, then:
#   cd C:\VettedCare.ai\vettedcare-backend\scripts
#   .\set_postgres_password.ps1

$ErrorActionPreference = "Stop"

$pgHba = "C:\Program Files\PostgreSQL\17\data\pg_hba.conf"
$pgHbaBak = "$pgHba.bak.offercare"
$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$serviceName = "postgresql-x64-17"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Please run this script as Administrator." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $psql)) {
    Write-Host "PostgreSQL 17 not found at expected path." -ForegroundColor Red
    exit 1
}

$pw1 = Read-Host "Enter the postgres password you chose" -AsSecureString
$pw2 = Read-Host "Confirm password" -AsSecureString
$bstr1 = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw1)
$bstr2 = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pw2)
$plain1 = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr1)
$plain2 = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr2)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr1)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr2)

if ($plain1 -ne $plain2) {
    Write-Host "Passwords do not match. Try again." -ForegroundColor Red
    exit 1
}

if ($plain1.Length -lt 8) {
    Write-Host "Use at least 8 characters." -ForegroundColor Red
    exit 1
}

Write-Host "Backing up pg_hba.conf..."
Copy-Item $pgHba $pgHbaBak -Force

Write-Host "Temporarily allowing local trust auth..."
$content = Get-Content $pgHba -Raw
$content = $content -replace '(?m)^(local\s+all\s+all\s+)scram-sha-256', '${1}trust'
$content = $content -replace '(?m)^(host\s+all\s+all\s+127\.0\.0\.1/32\s+)scram-sha-256', '${1}trust'
$content = $content -replace '(?m)^(host\s+all\s+all\s+::1/128\s+)scram-sha-256', '${1}trust'
Set-Content -Path $pgHba -Value $content -NoNewline

Write-Host "Restarting PostgreSQL..."
Restart-Service $serviceName

$escaped = $plain1 -replace "'", "''"
& $psql -U postgres -h localhost -d postgres -c "ALTER USER postgres PASSWORD '$escaped';"

Write-Host "Restoring secure auth..."
Copy-Item $pgHbaBak $pgHba -Force
Restart-Service $serviceName

Write-Host ""
Write-Host "Done. postgres password is set." -ForegroundColor Green
Write-Host "Next step: update DATABASE_URL in vettedcare-backend\.env with this password."
