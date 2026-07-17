from __future__ import annotations

import importlib
import importlib.util
import json
import platform
import re
import sys
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
    "VERSION",
    "CHANGELOG.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements-ui.txt",
    "requirements-dev.txt",
    "streamlit_app.py",
    "app",
    "data/scenarios",
    "data/reference_schedules",
    "docs/index.md",
    ".github/workflows/quality.yml",
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
}

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
    missing = [relative for relative in _REQUIRED_PATHS if not (paths.root / relative).exists()]
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
    missing = [label for label, module in _REQUIRED_MODULES if importlib.util.find_spec(module) is None]
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
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
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
        return _fail("scenario-integrity", "Nie udało się zwalidować scenariuszy.", repr(error))
    return _pass("scenario-integrity", "Scenariusze i referencje modeli są spójne.", *details)


def _check_imports(_: ProjectPaths) -> AuditCheck:
    errors: list[str] = []
    for module_name in _SMOKE_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as error:  # noqa: BLE001 - smoke audit records import errors
            errors.append(f"{module_name}: {type(error).__name__}: {error}")
    if errors:
        return _fail("module-imports", "Niektóre główne moduły nie importują się poprawnie.", *errors)
    return _pass("module-imports", f"Import głównych modułów zakończony powodzeniem ({len(_SMOKE_IMPORTS)}).")


def _check_output_layout(paths: ProjectPaths) -> AuditCheck:
    try:
        paths.ensure_output_directories()
    except OSError as error:
        return _fail("output-layout", "Nie można przygotować katalogów wynikowych.", str(error))

    expected = (
        paths.generated_schedules,
        paths.generated_reports,
        paths.generated_benchmarks,
        paths.generated_orbits,
        paths.stk_imports,
    )
    missing = [str(path.relative_to(paths.root)) for path in expected if not path.is_dir()]
    if missing:
        return _fail("output-layout", "Brakuje katalogów wynikowych.", *missing)
    return _pass("output-layout", "Katalogi wynikowe i importowe są dostępne.")


def _check_legacy_cesium(paths: ProjectPaths) -> AuditCheck:
    legacy = (
        paths.root / "app/visualization/cesium_scene.py",
        paths.root / "app/ui/components/cesium_globe.py",
    )
    present = [str(path.relative_to(paths.root)) for path in legacy if path.exists()]
    if present:
        return _info(
            "legacy-cesium",
            "Repozytorium zawiera nieaktywne moduły historycznego renderera Cesium.",
            *present,
        )
    return _pass("legacy-cesium", "Brak nieaktywnych modułów Cesium.")


_CHECKS: tuple[Callable[[ProjectPaths], AuditCheck], ...] = (
    _check_runtime,
    _check_version,
    _check_required_paths,
    _check_dependencies,
    _check_utf8,
    _check_json,
    _check_scenarios,
    _check_imports,
    _check_output_layout,
    _check_legacy_cesium,
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
