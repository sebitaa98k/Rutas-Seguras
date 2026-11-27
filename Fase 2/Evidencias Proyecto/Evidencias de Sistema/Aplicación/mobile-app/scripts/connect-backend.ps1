$ErrorActionPreference = 'Stop'

$adbPath = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
if (-not (Test-Path -LiteralPath $adbPath)) {
    throw "No se encontró ADB en $adbPath. Revisa la ubicación del SDK de Android Studio."
}

function Test-LocalPort([int]$Port) {
    $cliente = [System.Net.Sockets.TcpClient]::new()
    try {
        $conexion = $cliente.ConnectAsync('127.0.0.1', $Port)
        return $conexion.Wait(1500) -and $cliente.Connected
    } finally {
        $cliente.Dispose()
    }
}

if (-not (Test-LocalPort 8000)) {
    throw 'Django no está escuchando en 127.0.0.1:8000. Inicia primero manage.py runserver.'
}
if (-not (Test-LocalPort 3000)) {
    throw 'La Geo API no está escuchando en 127.0.0.1:3000. Ejecuta node api.js dentro de backend.'
}

$dispositivos = @(
    & $adbPath devices |
        Select-String -Pattern "`tdevice$" |
        ForEach-Object { ($_.Line -split "`t")[0] }
)

if ($dispositivos.Count -eq 0) {
    throw 'No hay un teléfono Android autorizado. Conecta el USB, activa Depuración USB y acepta la huella RSA.'
}

foreach ($dispositivo in $dispositivos) {
    & $adbPath -s $dispositivo reverse tcp:8000 tcp:8000
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo redirigir el puerto para el dispositivo $dispositivo."
    }
    & $adbPath -s $dispositivo reverse tcp:3000 tcp:3000
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo redirigir la Geo API para el dispositivo $dispositivo."
    }
    Write-Host "Servicios conectados con ${dispositivo}: Django :8000 y Geo API :3000"
}

& $adbPath reverse --list
