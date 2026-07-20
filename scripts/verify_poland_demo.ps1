param(
    [switch]$Docker,
    [switch]$StartApp
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

function Invoke-PythonStep {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "== $Name =="
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

Write-Host "Project: $ProjectRoot"
Write-Host "Python:  $Python"

Invoke-PythonStep "Pytest" @("-m", "pytest", "-q")
Invoke-PythonStep "Ruff" @(
    "-m", "ruff", "check", "app", "tests", "streamlit_app.py", "scripts"
)
Invoke-PythonStep "Scenario check" @("-m", "app.cli", "check")
Invoke-PythonStep "Repository audit" @("-m", "app.cli", "audit", "--strict")
Invoke-PythonStep "Runtime health" @("-m", "app.cli", "health", "--skip-http")
Invoke-PythonStep "Release check" @(
    "-m", "app.cli", "release-check",
    "--algorithm", "BOTH",
    "--cp-sat-time-limit", "2"
)

if ($Docker) {
    Write-Host ""
    Write-Host "== Docker build and healthcheck =="
    docker compose down
    if ($LASTEXITCODE -ne 0) { throw "docker compose down failed." }

    docker compose up --build -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed." }

    Start-Sleep -Seconds 15
    docker compose ps
    if ($LASTEXITCODE -ne 0) { throw "docker compose ps failed." }

    $Health = docker inspect --format "{{.State.Health.Status}}" satplan
    if ($LASTEXITCODE -ne 0) { throw "Docker health inspection failed." }
    if ($Health.Trim() -ne "healthy") {
        docker compose logs --tail 120 satplan
        throw "Container is not healthy: $Health"
    }
    Write-Host "Docker status: healthy"
}

if ($StartApp) {
    Write-Host ""
    Write-Host "Starting Streamlit on http://localhost:8501"
    & $Python -m streamlit run .\streamlit_app.py
}
else {
    Write-Host ""
    Write-Host "All requested checks passed."
}
