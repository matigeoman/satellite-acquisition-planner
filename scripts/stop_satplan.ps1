[CmdletBinding()]
param(
    [switch]$RemovePersistentData
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $ProjectRoot

try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Nie znaleziono polecenia 'docker'."
    }

    if ($RemovePersistentData) {
        Write-Warning "Usunięte zostaną trwałe wolumeny SatPlan z wynikami i importami."
        & docker compose down --remove-orphans --volumes
    }
    else {
        & docker compose down --remove-orphans
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Nie udało się zatrzymać kontenera SatPlan."
    }
}
finally {
    Pop-Location
}
