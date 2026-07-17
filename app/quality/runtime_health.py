from __future__ import annotations

import json
import platform
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ortools.sat.python import cp_model

from app.config.paths import ProjectPaths
from app.services.scenario_service import ScenarioService
from app.version import __version__


@dataclass(frozen=True, slots=True)
class RuntimeHealthCheck:
    name: str
    healthy: bool
    message: str


@dataclass(frozen=True, slots=True)
class RuntimeHealthReport:
    generated_at_utc: datetime
    application_version: str
    python_version: str
    checks: tuple[RuntimeHealthCheck, ...]

    @property
    def healthy(self) -> bool:
        return all(check.healthy for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "application_version": self.application_version,
            "python_version": self.python_version,
            "healthy": self.healthy,
            "checks": [asdict(check) for check in self.checks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def _success(name: str, message: str) -> RuntimeHealthCheck:
    return RuntimeHealthCheck(name=name, healthy=True, message=message)


def _failure(name: str, message: str) -> RuntimeHealthCheck:
    return RuntimeHealthCheck(name=name, healthy=False, message=message)


def _check_python() -> RuntimeHealthCheck:
    current = platform.python_version()
    if tuple(int(part) for part in current.split(".")[:2]) < (3, 11):
        return _failure("python", f"Wymagany Python >= 3.11; wykryto {current}.")
    return _success("python", f"Python {current} jest dostępny.")


def _check_cp_sat() -> RuntimeHealthCheck:
    try:
        model = cp_model.CpModel()
        variable = model.new_bool_var("runtime_health")
        model.add(variable == 1)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 1.0
        solver.parameters.num_search_workers = 1
        status = solver.solve(model)
    except Exception as error:  # noqa: BLE001 - health check must report runtime errors
        return _failure("cp-sat", f"Błąd uruchomienia solvera: {error}")

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _failure("cp-sat", f"Nieoczekiwany status solvera: {status}")
    if solver.value(variable) != 1:
        return _failure("cp-sat", "Solver zwrócił niepoprawne rozwiązanie testowe.")
    return _success("cp-sat", "Solver OR-Tools CP-SAT działa poprawnie.")


def _check_scenario(paths: ProjectPaths) -> RuntimeHealthCheck:
    try:
        scenario = ScenarioService(project_root=paths.root).load("EXAMPLE")
    except Exception as error:  # noqa: BLE001 - health check reports full failures
        return _failure("example-scenario", f"Nie można wczytać EXAMPLE: {error}")

    return _success(
        "example-scenario",
        (
            "Scenariusz EXAMPLE jest dostępny: "
            f"{scenario.satellite_count} satelitów, "
            f"{scenario.active_request_count} zleceń."
        ),
    )


def _probe_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=".satplan-health-",
        suffix=".tmp",
        dir=directory,
        delete=True,
    ) as handle:
        handle.write("ok")
        handle.flush()


def _check_writable_storage(paths: ProjectPaths) -> RuntimeHealthCheck:
    directories = (
        paths.generated_reports,
        paths.generated_orbits,
        paths.stk_imports,
    )
    try:
        for directory in directories:
            _probe_directory(directory)
    except OSError as error:
        return _failure("writable-storage", f"Brak zapisu danych trwałych: {error}")

    relative = ", ".join(str(path.relative_to(paths.root)) for path in directories)
    return _success("writable-storage", f"Katalogi są zapisywalne: {relative}.")


def _check_streamlit_http(url: str, timeout_s: float) -> RuntimeHealthCheck:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"satplan-health/{__version__}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            status = int(response.status)
            body = response.read(512).decode("utf-8", errors="replace").strip()
    except (OSError, urllib.error.URLError) as error:
        return _failure("streamlit-http", f"Endpoint {url} nie odpowiada: {error}")

    if status != 200:
        return _failure("streamlit-http", f"Endpoint {url} zwrócił HTTP {status}.")
    if body and body.lower() not in {"ok", "healthy"}:
        return _failure(
            "streamlit-http",
            f"Endpoint {url} zwrócił nieoczekiwaną odpowiedź: {body!r}.",
        )
    return _success("streamlit-http", f"Streamlit odpowiada pod {url}.")


def run_runtime_healthcheck(
    paths: ProjectPaths,
    *,
    streamlit_url: str | None = None,
    timeout_s: float = 3.0,
    http_checker: Callable[[str, float], RuntimeHealthCheck] = _check_streamlit_http,
) -> RuntimeHealthReport:
    """Check the runtime, solver, reference data, storage and optional HTTP UI."""

    checks = [
        _check_python(),
        _check_cp_sat(),
        _check_scenario(paths),
        _check_writable_storage(paths),
    ]
    if streamlit_url is not None:
        checks.append(http_checker(streamlit_url, timeout_s))

    return RuntimeHealthReport(
        generated_at_utc=datetime.now(timezone.utc),
        application_version=__version__,
        python_version=platform.python_version(),
        checks=tuple(checks),
    )


__all__ = [
    "RuntimeHealthCheck",
    "RuntimeHealthReport",
    "run_runtime_healthcheck",
]
