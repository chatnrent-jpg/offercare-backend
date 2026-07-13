# Create VettedMe.ai desktop shortcut + custom icon.
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$assets = Join-Path $root 'assets'
$iconPath = Join-Path $assets 'vettedme.ico'
$launcher = Join-Path $root 'start-all.bat'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'VettedMe.ai.lnk'

if (-not (Test-Path -LiteralPath $launcher)) {
    Write-Error "Launcher not found: $launcher"
}

New-Item -ItemType Directory -Path $assets -Force | Out-Null

Add-Type -AssemblyName System.Drawing

function New-VettedMeIcon([string]$Path) {
    $size = 256
    $bmp = New-Object System.Drawing.Bitmap $size, $size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::FromArgb(255, 10, 16, 32))

    $bg = [System.Drawing.Color]::FromArgb(255, 17, 24, 39)
    $blue = [System.Drawing.Color]::FromArgb(255, 37, 99, 235)
    $lightBlue = [System.Drawing.Color]::FromArgb(255, 96, 165, 250)
    $green = [System.Drawing.Color]::FromArgb(255, 74, 222, 128)

    $outer = New-Object System.Drawing.Rectangle 32, 32, 192, 192
    $g.FillRectangle((New-Object System.Drawing.SolidBrush $bg), $outer)
    $g.DrawRectangle((New-Object System.Drawing.Pen $blue, 10), $outer)

    $shield = New-Object System.Drawing.Drawing2D.GraphicsPath
    $shield.AddLines(@(
        [System.Drawing.Point]::new(128, 58),
        [System.Drawing.Point]::new(196, 88),
        [System.Drawing.Point]::new(196, 150),
        [System.Drawing.Point]::new(128, 206),
        [System.Drawing.Point]::new(60, 150),
        [System.Drawing.Point]::new(60, 88)
    ))
    $shield.CloseFigure()
    $g.FillPath((New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(40, 37, 99, 235))), $shield)
    $g.DrawPath((New-Object System.Drawing.Pen $lightBlue, 6), $shield)

    $check = New-Object System.Drawing.Drawing2D.GraphicsPath
    $check.AddLines(@(
        [System.Drawing.Point]::new(92, 132),
        [System.Drawing.Point]::new(118, 158),
        [System.Drawing.Point]::new(168, 102)
    ))
    $checkPen = New-Object System.Drawing.Pen $green, 16
    $checkPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $checkPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $checkPen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    $g.DrawPath($checkPen, $check)

    $hIcon = $bmp.GetHicon()
    $icon = [System.Drawing.Icon]::FromHandle($hIcon)
    $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::Create)
    $icon.Save($fs)
    $fs.Close()
    $icon.Dispose()
    $bmp.Dispose()
    $g.Dispose()
}

New-VettedMeIcon -Path $iconPath

$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcutPath)
$link.TargetPath = $launcher
$link.WorkingDirectory = $root
$link.IconLocation = "$iconPath,0"
$link.Description = 'VettedMe.ai - Credential Safety Platform'
$link.WindowStyle = 1
$link.Save()

Write-Host "Icon:     $iconPath"
Write-Host "Shortcut: $shortcutPath"
Write-Host 'Done - VettedMe.ai is on your desktop.'
