param(
    [switch]$Docker,
    [switch]$NoCache,
    [switch]$KeepContainer
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$CondaPython = Join-Path $HOME ".conda\envs\satplan\python.exe"
if (Test-Path $CondaPython) {
    $Python = $CondaPython
}
else {
    $PythonCommand = Get-Command python -ErrorAction Stop
    $Python = $PythonCommand.Source
}

function Invoke-CheckedCommand {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "== $Name =="
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

function Wait-ContainerHealthy {
    param(
        [string]$ContainerName = "satplan",
        [int]$Attempts = 60
    )

    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        $Status = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $ContainerName 2>$null
        if ($LASTEXITCODE -eq 0 -and $Status.Trim() -eq "healthy") {
            return
        }
        if ($LASTEXITCODE -eq 0 -and $Status.Trim() -in @("unhealthy", "exited", "dead")) {
            docker compose logs --tail 150 satplan
            throw "Container entered terminal state: $Status"
        }
        Start-Sleep -Seconds 2
    }

    docker compose logs --tail 150 satplan
    throw "Container did not become healthy in time."
}

$Version = (Get-Content .\VERSION -Raw).Trim()
if ($Version -ne "1.2.0") {
    throw "Expected VERSION=1.2.0, found '$Version'."
}

Write-Host "Project: $ProjectRoot"
Write-Host "Python:  $Python"
Write-Host "Version: $Version"

Invoke-CheckedCommand "Dependency consistency" {
    & $Python -m pip check
}
Invoke-CheckedCommand "Pytest" {
    & $Python -m pytest -q
}
Invoke-CheckedCommand "Ruff" {
    & $Python -m ruff check app tests streamlit_app.py scripts
}
Invoke-CheckedCommand "Scenario check" {
    & $Python -m app.cli check
}
Invoke-CheckedCommand "Repository audit" {
    & $Python -m app.cli audit --strict
}
Invoke-CheckedCommand "Runtime health" {
    & $Python -m app.cli health --skip-http
}
Invoke-CheckedCommand "Offline demo and full E2E" {
    & $Python -m app.cli release-check --algorithm ALL --cp-sat-time-limit 2
}
Invoke-CheckedCommand "Repository cleanup dry-run" {
    & $Python .\scripts\cleanup_repository.py --project-root . --dry-run
}

if ($Docker) {
    Write-Host ""
    Write-Host "== Docker final verification =="

    docker compose down
    if ($LASTEXITCODE -ne 0) { throw "docker compose down failed." }

    if ($NoCache) {
        docker compose build --no-cache satplan
        if ($LASTEXITCODE -ne 0) { throw "Docker no-cache build failed." }
        docker compose up -d
    }
    else {
        docker compose up --build -d
    }
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed." }

    Wait-ContainerHealthy
    docker compose ps
    Write-Host "Docker status: healthy"

    Invoke-CheckedCommand "Container scenario check" {
        docker compose exec -T satplan python -m app.cli check
    }
    Invoke-CheckedCommand "Container audit" {
        docker compose exec -T satplan python -m app.cli audit --strict
    }
    Invoke-CheckedCommand "Container health" {
        docker compose exec -T satplan python -m app.cli health --skip-http
    }
    Invoke-CheckedCommand "Container release check" {
        docker compose exec -T satplan python -m app.cli release-check --algorithm GREEDY --cp-sat-time-limit 2
    }

    if (-not $KeepContainer) {
        docker compose down
        if ($LASTEXITCODE -ne 0) { throw "docker compose down failed." }
        Write-Host "Container stopped after verification."
    }
}

Write-Host ""
Write-Host "FINAL RELEASE 1.2.0: READY"
