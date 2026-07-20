from __future__ import annotations

import importlib
import importlib.util
import json
import platform
import re
import sys
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Callable, Iterable

from app.config.paths import ProjectPaths
from app.services.scenario_service import ScenarioService
from app.version import __version__


class AuditStatus(StrEnum):
    PASS = "PASS"
    INFO = "INFO"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class AuditCheck:
    name: str
    status: AuditStatus
    message: str
    details: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status is AuditStatus.PASS


@dataclass(frozen=True, slots=True)
class AuditReport:
    generated_at_utc: datetime
    project_root: Path
    application_version: str
    python_version: str
    checks: tuple[AuditCheck, ...]

    @property
    def failures(self) -> tuple[AuditCheck, ...]:
        return tuple(check for check in self.checks if check.status is AuditStatus.FAIL)

    @property
    def warnings(self) -> tuple[AuditCheck, ...]:
        return tuple(check for check in self.checks if check.status is AuditStatus.WARN)

    @property
    def is_success(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "project_root": str(self.project_root),
            "application_version": self.application_version,
            "python_version": self.python_version,
            "success": self.is_success,
            "failure_count": len(self.failures),
            "warning_count": len(self.warnings),
            "checks": [
                {
                    **asdict(check),
                    "status": check.status.value,
                }
                for check in self.checks
            ],
        }


_REQUIRED_PATHS = (
    "README.md",
    ".editorconfig",
    ".gitattributes",
    "VERSION",
    "CHANGELOG.md",
    "RELEASE_NOTES.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements-ui.txt",
    "requirements-dev.txt",
    "streamlit_app.py",
    "app",
    "data/scenarios",
    "data/reference_schedules",
    "docs/index.md",
    "docs/docker.md",
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    "scripts/start_satplan.ps1",
    "scripts/start_satplan.bat",
    "scripts/stop_satplan.ps1",
    "scripts/stop_satplan.bat",
    ".github/workflows/quality.yml",
    ".github/workflows/docker.yml",
    ".gitignore",
    "app/demo/service.py",
    "app/quality/release_check.py",
    "docs/demo_and_release_check.md",
    "scripts/cleanup_repository.py",
    "scripts/verify_release.ps1",
)

_REQUIRED_MODULES = (
    ("pydantic", "pydantic"),
    ("ortools", "ortools"),
    ("sgp4", "sgp4"),
    ("pandas", "pandas"),
    ("plotly", "plotly"),
    ("streamlit", "streamlit"),
    ("folium", "folium"),
    ("python-docx", "docx"),
    ("XlsxWriter", "xlsxwriter"),
)

_SMOKE_IMPORTS = (
    "app.cli",
    "app.models",
    "app.planning",
    "app.services",
    "app.integrations.orbits",
    "app.integrations.weather",
    "app.integrations.stk_validation",
    "app.projects",
    "app.reporting",
    "app.visualization.plotly_globe",
    "app.demo",
    "app.quality.release_check",
)

_TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".csv",
    ".geojson",
    ".html",
    ".css",
    ".js",
    ".ps1",
    ".bat",
}

_TEXT_FILENAMES = {"Dockerfile", ".dockerignore", ".editorconfig", ".gitattributes"}

_EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
}

_MOJIBAKE_MARKERS = (
    chr(0x00C3),
    chr(0x00C4),
    chr(0x00C5),
    chr(0x00C2),
    chr(0x00E2) + chr(0x20AC),
    chr(0x00EF) + chr(0x00BB) + chr(0x00BF),
)
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


def _pass(name: str, message: str, *details: str) -> AuditCheck:
    return AuditCheck(name, AuditStatus.PASS, message, tuple(details))


def _info(name: str, message: str, *details: str) -> AuditCheck:
    return AuditCheck(name, AuditStatus.INFO, message, tuple(details))


def _warn(name: str, message: str, *details: str) -> AuditCheck:
    return AuditCheck(name, AuditStatus.WARN, message, tuple(details))


def _fail(name: str, message: str, *details: str) -> AuditCheck:
    return AuditCheck(name, AuditStatus.FAIL, message, tuple(details))


def _check_runtime(_: ProjectPaths) -> AuditCheck:
    current = sys.version_info[:2]
    if current < (3, 11):
        return _fail(
            "python-runtime",
            "Wymagany jest Python 3.11 lub nowszy.",
            platform.python_version(),
        )
    if current != (3, 11):
        return _warn(
            "python-runtime",
            "Projekt jest walidowany referencyjnie na Pythonie 3.11.",
            f"Bieżąca wersja: {platform.python_version()}",
        )
    return _pass(
        "python-runtime",
        "Wersja interpretera jest zgodna z konfiguracją referencyjną.",
        platform.python_version(),
    )


def _check_version(paths: ProjectPaths) -> AuditCheck:
    version_path = paths.root / "VERSION"
    try:
        raw = version_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        return _fail("application-version", "Nie można odczytać VERSION.", str(error))

    if not _SEMVER_PATTERN.fullmatch(raw):
        return _fail(
            "application-version",
            "VERSION nie jest zgodny z Semantic Versioning.",
            raw,
        )
    if raw != __version__:
        return _fail(
            "application-version",
            "Wersja w pliku i module aplikacji jest niespójna.",
            f"VERSION={raw}",
            f"app.version={__version__}",
        )
    return _pass("application-version", f"Wersja aplikacji: {raw}")


def _check_required_paths(paths: ProjectPaths) -> AuditCheck:
    missing = [
        relative for relative in _REQUIRED_PATHS if not (paths.root / relative).exists()
    ]
    if missing:
        return _fail(
            "required-paths",
            "Brakuje wymaganych plików lub katalogów.",
            *missing,
        )
    return _pass(
        "required-paths",
        f"Znaleziono wszystkie wymagane elementy ({len(_REQUIRED_PATHS)}).",
    )


def _check_dependencies(_: ProjectPaths) -> AuditCheck:
    missing = [
        label
        for label, module in _REQUIRED_MODULES
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        return _fail(
            "dependencies",
            "Brakuje wymaganych zależności Pythona.",
            *missing,
        )
    return _pass(
        "dependencies",
        f"Wszystkie wymagane zależności są dostępne ({len(_REQUIRED_MODULES)}).",
    )


def _iter_text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if (
            path.suffix.lower() not in _TEXT_SUFFIXES
            and path.name not in _TEXT_FILENAMES
        ):
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in _EXCLUDED_PARTS for part in relative_parts):
            continue
        if relative_parts[:2] == ("data", "generated"):
            continue
        yield path


def _check_utf8(paths: ProjectPaths) -> AuditCheck:
    decode_errors: list[str] = []
    mojibake: list[str] = []
    count = 0

    for path in _iter_text_files(paths.root):
        count += 1
        relative = str(path.relative_to(paths.root))
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            decode_errors.append(f"{relative}: {error}")
            continue
        for marker in _MOJIBAKE_MARKERS:
            if marker in text:
                mojibake.append(f"{relative}: podejrzany ciąg {marker!r}")
                break

    if decode_errors or mojibake:
        return _fail(
            "utf8-and-mojibake",
            "Wykryto problemy z kodowaniem tekstu.",
            *(decode_errors + mojibake),
        )
    return _pass(
        "utf8-and-mojibake",
        f"Pliki tekstowe są poprawnym UTF-8 bez typowych śladów mojibake ({count}).",
    )


def _check_windows_powershell_encoding(paths: ProjectPaths) -> AuditCheck:
    scripts = (
        paths.root / "scripts/start_satplan.ps1",
        paths.root / "scripts/stop_satplan.ps1",
    )
    errors: list[str] = []

    for script in scripts:
        relative = str(script.relative_to(paths.root))
        try:
            raw = script.read_bytes()
        except OSError as error:
            errors.append(f"{relative}: {error}")
            continue

        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            errors.append(f"{relative}: niepoprawny UTF-8: {error}")
            continue

        contains_non_ascii = any(ord(character) > 127 for character in text)
        if contains_non_ascii and not raw.startswith(b"\xef\xbb\xbf"):
            errors.append(
                f"{relative}: skrypt z polskimi znakami wymaga BOM UTF-8 "
                "dla Windows PowerShell 5.1"
            )

    if errors:
        return _fail(
            "windows-powershell-encoding",
            "Skrypty PowerShell nie są zgodne z Windows PowerShell 5.1.",
            *errors,
        )
    return _pass(
        "windows-powershell-encoding",
        "Skrypty PowerShell mają kodowanie zgodne z Windows PowerShell 5.1.",
    )


def _check_json(paths: ProjectPaths) -> AuditCheck:
    roots = (paths.scenarios, paths.reference_schedules)
    json_paths = sorted(path for root in roots for path in root.rglob("*.json"))
    errors: list[str] = []
    for path in json_paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            errors.append(f"{path.relative_to(paths.root)}: {error}")
    if errors:
        return _fail("json-syntax", "Niektóre pliki JSON są niepoprawne.", *errors)
    return _pass("json-syntax", f"Poprawnie odczytano {len(json_paths)} plików JSON.")


def _check_scenarios(paths: ProjectPaths) -> AuditCheck:
    try:
        service = ScenarioService(project_root=paths.root)
        details = []
        for scenario_id in service.scenario_ids:
            scenario = service.load(scenario_id)
            details.append(
                f"{scenario_id}: {scenario.satellite_count} sat., "
                f"{scenario.active_request_count} zleceń, "
                f"{scenario.opportunity_count} okazji"
            )
    except Exception as error:  # noqa: BLE001 - audit must report full failures
        return _fail(
            "scenario-integrity", "Nie udało się zwalidować scenariuszy.", repr(error)
        )
    return _pass(
        "scenario-integrity", "Scenariusze i referencje modeli są spójne.", *details
    )


def _check_imports(_: ProjectPaths) -> AuditCheck:
    errors: list[str] = []
    for module_name in _SMOKE_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as error:  # noqa: BLE001 - smoke audit records import errors
            errors.append(f"{module_name}: {type(error).__name__}: {error}")
    if errors:
        return _fail(
            "module-imports",
            "Niektóre główne moduły nie importują się poprawnie.",
            *errors,
        )
    return _pass(
        "module-imports",
        f"Import głównych modułów zakończony powodzeniem ({len(_SMOKE_IMPORTS)}).",
    )


def _check_output_layout(paths: ProjectPaths) -> AuditCheck:
    try:
        paths.ensure_output_directories()
    except OSError as error:
        return _fail(
            "output-layout", "Nie można przygotować katalogów wynikowych.", str(error)
        )

    expected = (
        paths.generated_schedules,
        paths.generated_reports,
        paths.generated_benchmarks,
        paths.generated_orbits,
        paths.stk_imports,
    )
    missing = [
        str(path.relative_to(paths.root)) for path in expected if not path.is_dir()
    ]
    if missing:
        return _fail("output-layout", "Brakuje katalogów wynikowych.", *missing)
    return _pass("output-layout", "Katalogi wynikowe i importowe są dostępne.")


def _check_docker_assets(paths: ProjectPaths) -> AuditCheck:
    dockerfile = paths.root / "Dockerfile"
    compose = paths.root / "docker-compose.yml"
    try:
        docker_text = dockerfile.read_text(encoding="utf-8")
        compose_text = compose.read_text(encoding="utf-8")
    except OSError as error:
        return _fail(
            "docker-assets", "Nie można odczytać konfiguracji Docker.", str(error)
        )

    required_docker_tokens = (
        "FROM python:3.11-slim",
        "USER satplan",
        "HEALTHCHECK",
        "python -m app.cli health",
        "streamlit_app.py",
    )
    required_compose_tokens = (
        "services:",
        "satplan:",
        "satplan_generated",
        "satplan_imports",
        "healthcheck:",
        "${SATPLAN_PORT:-8501}:8501",
    )
    missing = [
        f"Dockerfile: {token}"
        for token in required_docker_tokens
        if token not in docker_text
    ]
    missing.extend(
        f"docker-compose.yml: {token}"
        for token in required_compose_tokens
        if token not in compose_text
    )
    if missing:
        return _fail(
            "docker-assets",
            "Konfiguracja kontenera nie zawiera wymaganych zabezpieczeń lub usług.",
            *missing,
        )
    return _pass(
        "docker-assets",
        "Dockerfile, Compose, trwałe wolumeny i healthcheck są skonfigurowane.",
    )


def _repository_files(paths: ProjectPaths) -> tuple[Path, ...]:
    git_directory = paths.root / ".git"
    if git_directory.exists():
        try:
            completed = subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=paths.root,
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError):
            pass
        else:
            tracked = tuple(
                paths.root / item.decode("utf-8")
                for item in completed.stdout.split(b"\0")
                if item
            )
            return tuple(path for path in tracked if path.exists())

    return tuple(
        path
        for path in paths.root.rglob("*")
        if path.is_file()
        and not any(
            part in _EXCLUDED_PARTS for part in path.relative_to(paths.root).parts
        )
        and path.relative_to(paths.root).parts[:2] != ("data", "generated")
    )


def _check_repository_cleanliness(paths: ProjectPaths) -> AuditCheck:
    forbidden_exact = {
        "app/ui/components/cesium_globe.py",
        "app/visualization/czml.py",
        "app/ui/assets/earth_fallback.jpg",
        "docs/cesium_3d_globe.md",
        "tests/test_cesium_scene.py",
        "HOTFIX_README.txt",
        "RECOVERY_README.txt",
        "README_STAGE17_WINDOWS.txt",
        "run_stage17_checks.ps1",
        "report.docx",
        "main.py",
        "docs/algorithm_benchmarks.md",
        "docs/planning_architecture.md",
    }
    forbidden_suffixes = (".bak-stage", ".exe", ".msi")
    problems: list[str] = []

    for path in _repository_files(paths):
        relative = path.relative_to(paths.root).as_posix()
        name = path.name
        if relative in forbidden_exact:
            problems.append(relative)
            continue
        if name.endswith("_NOTES.txt"):
            problems.append(relative)
            continue
        if name.startswith("satplan-") and name.endswith(".zip"):
            problems.append(relative)
            continue
        if any(marker in name for marker in forbidden_suffixes):
            problems.append(relative)

    if problems:
        return _fail(
            "repository-cleanliness",
            "Repozytorium zawiera pliki robocze lub nieaktywny kod.",
            *sorted(set(problems)),
        )
    return _pass(
        "repository-cleanliness",
        "Brak plików tymczasowych, artefaktów roboczych i wycofanych modułów.",
    )


_CHECKS: tuple[Callable[[ProjectPaths], AuditCheck], ...] = (
    _check_runtime,
    _check_version,
    _check_required_paths,
    _check_dependencies,
    _check_utf8,
    _check_windows_powershell_encoding,
    _check_json,
    _check_scenarios,
    _check_imports,
    _check_output_layout,
    _check_docker_assets,
    _check_repository_cleanliness,
)


def run_project_audit(paths: ProjectPaths) -> AuditReport:
    """Execute deterministic repository and runtime checks."""

    checks = tuple(check(paths) for check in _CHECKS)
    return AuditReport(
        generated_at_utc=datetime.now(timezone.utc),
        project_root=paths.root,
        application_version=__version__,
        python_version=platform.python_version(),
        checks=checks,
    )


__all__ = [
    "AuditCheck",
    "AuditReport",
    "AuditStatus",
    "run_project_audit",
]
