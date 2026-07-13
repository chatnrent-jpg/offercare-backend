# Create VettedMe Maryland Ops Console desktop shortcut.
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$iconPath = Join-Path $root 'assets\vettedme.ico'
$launcher = Join-Path $root 'start-ops-console.bat'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'VettedMe Ops Console.lnk'

if (-not (Test-Path -LiteralPath $launcher)) {
    Write-Error "Launcher not found: $launcher"
}

$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcutPath)
$link.TargetPath = $launcher
$link.WorkingDirectory = $root
if (Test-Path -LiteralPath $iconPath) {
    $link.IconLocation = "$iconPath,0"
}
$link.Description = 'VettedMe.ai - Maryland Ops Console (Streamlit)'
$link.WindowStyle = 1
$link.Save()

Write-Host "Shortcut: $shortcutPath"
Write-Host 'Done - double-click VettedMe Ops Console on your desktop.'
