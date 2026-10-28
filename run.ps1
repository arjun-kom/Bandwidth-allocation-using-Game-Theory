# Build and start the app in Docker, then open the dashboard.
# Usage (PowerShell, in this folder):  .\run.ps1            uses port 8080, or the next free one
#                                      .\run.ps1 -Port 9000 uses a port you choose
param([int]$Port = 8080)
$ErrorActionPreference = "Stop"

function Test-PortFree([int]$p) {
    -not (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

# Stop an earlier copy of this app so it does not hold the port
docker compose down 2>$null | Out-Null

$start = $Port
while (-not (Test-PortFree $Port)) {
    Write-Host "Port $Port is busy, trying $($Port + 1)..."
    $Port++
    if ($Port -gt $start + 20) { throw "No free port between $start and $Port. Run .\run.ps1 -Port <number>." }
}

$env:PORT = $Port
docker compose up --build -d
Write-Host "Waiting for the server..."
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-RestMethod "http://localhost:$Port/api/health" | Out-Null; break } catch { Start-Sleep -Seconds 2 }
}
Start-Process "http://localhost:$Port"
Write-Host "Dashboard: http://localhost:$Port   API docs: http://localhost:$Port/docs   Stop with: docker compose down"
