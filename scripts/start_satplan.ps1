[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8501,

    [switch]$Foreground,
    [switch]$NoBuild,
    [switch]$OpenBrowser,

    [ValidateRange(10, 600)]
    [int]$HealthTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $ProjectRoot

try {
    $Docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($null -eq $Docker) {
        throw "Nie znaleziono polecenia 'docker'. Zainstaluj i uruchom Docker Desktop."
    }

    & docker compose version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose v2 nie jest dostępny."
    }

    & docker info | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Engine nie odpowiada. Uruchom Docker Desktop."
    }

    $env:SATPLAN_PORT = [string]$Port
    $ComposeArguments = @("compose", "up")
    if (-not $NoBuild) {
        $ComposeArguments += "--build"
    }

    if ($Foreground) {
        Write-Host "Uruchamianie SatPlan na http://localhost:$Port ..."
        & docker @ComposeArguments
        exit $LASTEXITCODE
    }

    $ComposeArguments += "--detach"
    & docker @ComposeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Nie udało się uruchomić kontenera SatPlan."
    }

    $ContainerId = (& docker compose ps -q satplan).Trim()
    if ([string]::IsNullOrWhiteSpace($ContainerId)) {
        throw "Docker Compose nie zwrócił identyfikatora kontenera SatPlan."
    }

    $Deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
    $LastState = "starting"
    while ((Get-Date) -lt $Deadline) {
        $LastState = (& docker inspect `
            --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" `
            $ContainerId).Trim()

        if ($LastState -eq "healthy") {
            break
        }
        if ($LastState -in @("unhealthy", "exited", "dead")) {
            & docker compose logs --tail 120 satplan
            throw "Kontener zakończył kontrolę ze stanem: $LastState"
        }
        Start-Sleep -Seconds 2
    }

    if ($LastState -ne "healthy") {
        & docker compose logs --tail 120 satplan
        throw "Przekroczono czas oczekiwania na healthcheck ($HealthTimeoutSeconds s)."
    }

    $Url = "http://localhost:$Port"
    Write-Host "SatPlan działa: $Url"
    Write-Host "Logi: docker compose logs -f satplan"
    Write-Host "Zatrzymanie: .\scripts\stop_satplan.ps1"

    if ($OpenBrowser) {
        Start-Process $Url
    }
}
finally {
    Pop-Location
}
