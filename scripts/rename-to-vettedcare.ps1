# Finish VettedCare.ai folder rename — run from ANY location (script jumps to C:\ first).
$ErrorActionPreference = 'Stop'
Set-Location C:\

$legacyRoot = 'C:\OFFERCARE.AI'
$legacyBackend = Join-Path $legacyRoot 'offercare-backend'
$legacyBackendRenamed = Join-Path $legacyRoot 'vettedcare-backend'
$newRoot = 'C:\VettedCare.ai'
$newBackend = Join-Path $newRoot 'vettedcare-backend'

Write-Host 'Stopping processes under OFFERCARE.AI / VettedCare.ai...'
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $cmd = [string]$_.CommandLine
        $exe = [string]$_.ExecutablePath
        $cmd -like '*OFFERCARE.AI*' -or $cmd -like '*offercare-backend*' -or $cmd -like '*vettedcare-backend*' -or
        $exe -like '*OFFERCARE.AI*' -or $exe -like '*offercare-backend*' -or $exe -like '*vettedcare-backend*'
    } |
    ForEach-Object {
        Write-Host "  stop pid $($_.ProcessId) $($_.Name)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
Start-Sleep -Seconds 3
Set-Location C:\

function Get-SourceBackend {
    if (Test-Path -LiteralPath $newBackend) { return $newBackend }
    if (Test-Path -LiteralPath $legacyBackendRenamed) { return $legacyBackendRenamed }
    if (Test-Path -LiteralPath $legacyBackend) { return $legacyBackend }
    return $null
}

function Copy-BackendFallback([string]$Source) {
    if (-not $Source) { throw 'No backend folder found to copy.' }
    New-Item -ItemType Directory -Path $newRoot -Force | Out-Null
    Write-Host "Rename blocked. Copying with robocopy..."
    Write-Host "  from: $Source"
    Write-Host "  to:   $newBackend"
    $null = robocopy $Source $newBackend /E /COPY:DAT /R:2 /W:2 /XD __pycache__ .pytest_cache /NFL /NDL /NJH /NJS /NP
    if (-not (Test-Path -LiteralPath (Join-Path $newBackend 'start-all.bat'))) {
        throw 'Copy failed - start-all.bat not found at destination.'
    }
    Write-Host ''
    Write-Host 'Copy complete. New project root:'
    Write-Host "  $newBackend"
    Write-Host ''
    Write-Host 'After you confirm start-all.bat works, delete the old tree:'
    Write-Host "  $legacyRoot"
}

$source = Get-SourceBackend
if (-not $source) {
    Write-Host 'No OFFERCARE.AI backend found. Expected one of:'
    Write-Host "  $legacyBackend"
    Write-Host "  $legacyBackendRenamed"
    Write-Host "  $newBackend"
    exit 1
}

if ($source -eq $newBackend) {
    Write-Host "Already at $newBackend"
    exit 0
}

Set-Location C:\
$renamed = $false
if ($source -eq $legacyBackend) {
    try {
        Write-Host "Renaming backend -> vettedcare-backend"
        Rename-Item -LiteralPath $legacyBackend -NewName 'vettedcare-backend' -ErrorAction Stop
        $source = $legacyBackendRenamed
        $renamed = $true
    } catch {
        Write-Host "Backend rename blocked: $($_.Exception.Message)"
    }
}

if (-not $renamed -and $source -ne $newBackend) {
    Copy-BackendFallback -Source $source
    exit 0
}

Set-Location C:\
if (Test-Path -LiteralPath $legacyRoot) {
    if (Test-Path -LiteralPath $newRoot) {
        Write-Host "Target root already exists: $newRoot"
        Write-Host "Backend is at: $legacyBackendRenamed"
        Write-Host "Move vettedcare-backend into VettedCare.ai manually if needed."
    } else {
        try {
            Write-Host 'Renaming root -> VettedCare.ai'
            Rename-Item -LiteralPath $legacyRoot -NewName 'VettedCare.ai' -ErrorAction Stop
            Write-Host ''
            Write-Host "Done. Project root: $newBackend"
        } catch {
            Write-Host "Root rename blocked: $($_.Exception.Message)"
            Write-Host "Backend renamed inside OFFERCARE.AI -> vettedcare-backend"
            Write-Host "Run this script again from a NEW PowerShell window (not inside the project folder)."
        }
    }
} elseif (Test-Path -LiteralPath $newBackend) {
    Write-Host ''
    Write-Host "Done. Project root: $newBackend"
}

Write-Host ''
Write-Host "Start: cd $newBackend; .\start-all.bat"
