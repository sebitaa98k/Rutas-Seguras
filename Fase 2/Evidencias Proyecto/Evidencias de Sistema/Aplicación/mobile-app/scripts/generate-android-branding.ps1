param(
    [string]$SourceLogo = (Join-Path $PSScriptRoot '..\resources\logo_rutasSeguras.png')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$resRoot = Join-Path $projectRoot 'android\app\src\main\res'
$sourcePath = [System.IO.Path]::GetFullPath($SourceLogo)

if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "No se encontró el logo fuente: $sourcePath"
}

$source = [System.Drawing.Image]::FromFile($sourcePath)

function Write-LauncherPng {
    param(
        [int]$Size,
        [double]$LogoScale,
        [string]$Destination
    )

    $bitmap = New-Object System.Drawing.Bitmap($Size, $Size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.Clear([System.Drawing.Color]::Transparent)
        $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
        $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

        $targetSize = [int][Math]::Round($Size * $LogoScale)
        $x = [int][Math]::Round(($Size - $targetSize) / 2)
        $y = [int][Math]::Round(($Size - $targetSize) / 2)
        $graphics.DrawImage($source, $x, $y, $targetSize, $targetSize)

        $directory = Split-Path -Parent $Destination
        if (-not (Test-Path -LiteralPath $directory)) {
            New-Item -ItemType Directory -Path $directory | Out-Null
        }
        $bitmap.Save($Destination, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

try {
    $densities = @{
        'mdpi' = 48
        'hdpi' = 72
        'xhdpi' = 96
        'xxhdpi' = 144
        'xxxhdpi' = 192
    }

    foreach ($density in $densities.Keys) {
        $legacySize = $densities[$density]
        $directory = Join-Path $resRoot "mipmap-$density"
        Write-LauncherPng -Size $legacySize -LogoScale 0.92 -Destination (Join-Path $directory 'ic_launcher.png')
        Write-LauncherPng -Size $legacySize -LogoScale 0.86 -Destination (Join-Path $directory 'ic_launcher_round.png')
        Write-LauncherPng -Size ([int][Math]::Round($legacySize * 2.25)) -LogoScale 0.66 -Destination (Join-Path $directory 'ic_launcher_foreground.png')
    }
}
finally {
    $source.Dispose()
}

Write-Output 'Recursos launcher Android generados correctamente.'
