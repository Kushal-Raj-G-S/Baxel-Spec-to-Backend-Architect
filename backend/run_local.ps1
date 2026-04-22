param(
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $backendRoot 'venv\Scripts\python.exe'

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python executable not found at $pythonExe"
}

# Clean old listeners on the same port to avoid ghost bind problems.
Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }

$args = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port", '--log-level', 'debug')
if ($Reload) {
    $args += '--reload'
    $args += '--access-log'
}

Push-Location $backendRoot
try {
    $proc = Start-Process -FilePath $pythonExe -ArgumentList $args -PassThru
    Start-Sleep -Seconds 2

    $healthUrl = "http://127.0.0.1:$Port/health"
    $docsUrl = "http://127.0.0.1:$Port/docs"

    try {
        $health = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
        $docs = Invoke-WebRequest -Uri $docsUrl -UseBasicParsing -TimeoutSec 5
        Write-Host "Backend is up. /health=$($health.StatusCode), /docs=$($docs.StatusCode), pid=$($proc.Id)" -ForegroundColor Green
        Write-Host "Press Ctrl+C in this terminal to stop if running foreground elsewhere." -ForegroundColor Yellow
    }
    catch {
        Write-Host "Backend started but probe failed: $($_.Exception.Message)" -ForegroundColor Red
        if (-not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}
finally {
    Pop-Location
}
