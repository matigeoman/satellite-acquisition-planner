from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_dockerfile_uses_python_311_non_root_and_healthcheck() -> None:
    dockerfile = _read("Dockerfile")

    assert "FROM python:3.11-slim" in dockerfile
    assert "USER satplan" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert '"python", "-m", "app.cli", "health", "--quiet"' in dockerfile
    assert '"streamlit", "run", "streamlit_app.py"' in dockerfile
    assert "python -m app.cli audit --strict" in dockerfile
    assert "requirements-lock.txt" in dockerfile
    assert "-c requirements-lock.txt" in dockerfile


def test_compose_has_persistent_volumes_configurable_port_and_security() -> None:
    compose = _read("docker-compose.yml")

    assert "${SATPLAN_PORT:-8501}:8501" in compose
    assert "satplan_generated:/opt/satplan/data/generated" in compose
    assert "satplan_imports:/opt/satplan/data/imports" in compose
    assert "no-new-privileges:true" in compose
    assert "healthcheck:" in compose
    assert "restart: unless-stopped" in compose


def test_windows_launchers_and_docker_workflow_are_present() -> None:
    start = _read("scripts/start_satplan.ps1")
    stop = _read("scripts/stop_satplan.ps1")
    workflow = _read(".github/workflows/docker.yml")

    assert "docker compose up" not in start
    assert '@("compose", "up")' in start
    assert "docker inspect" in start
    assert "healthy" in start
    assert "--volumes" in stop
    assert "docker/build-push-action@v6" in workflow
    assert "Wait for container health" in workflow
    assert "python -m app.cli health --quiet" in workflow


def test_release_version_is_consistent_in_container_assets() -> None:
    version = _read("VERSION").strip()
    dockerfile = _read("Dockerfile")
    compose = _read("docker-compose.yml")
    workflow = _read(".github/workflows/docker.yml")

    assert version == "1.3.0"
    assert f"ARG APP_VERSION={version}" in dockerfile
    assert f"image: satplan:{version}" in compose
    assert f"APP_VERSION={version}" in workflow


def test_development_tools_are_not_runtime_dependencies() -> None:
    runtime = _read("requirements.txt")
    development = _read("requirements-dev.txt")
    lock = _read("requirements-lock.txt")

    assert "pytest" not in runtime.lower()
    assert "ruff" not in runtime.lower()
    assert "pytest" in development.lower()
    assert "ruff" in development.lower()
    assert "pytest==" in lock.lower()
    assert "ruff==" in lock.lower()
