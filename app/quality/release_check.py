from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config.paths import ProjectPaths
from app.models.enums import PlanningAlgorithm
from app.projects import ProjectArchiveService, ProjectMetadata
from app.projects.history import (
    PROJECT_METADATA_STATE_KEY,
    SCHEDULE_HISTORY_STATE_KEY,
    build_schedule_history_entry,
)
from app.projects.service import (
    AOI_STATE_KEY,
    CUSTOM_REQUESTS_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
)
from app.quality.audit import AuditReport, run_project_audit
from app.reporting import ScientificReportConfig, ScientificReportService
from app.services import PlanningOptions, PlanningService, ScenarioService
from app.services.contracts import PlanningResult
from app.version import __version__


@dataclass(frozen=True, slots=True)
class ReleaseCheckStep:
    name: str
    passed: bool
    message: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReleaseCheckReport:
    generated_at_utc: datetime
    application_version: str
    project_root: Path
    steps: tuple[ReleaseCheckStep, ...]
    artifact_paths: tuple[Path, ...]

    @property
    def failures(self) -> tuple[ReleaseCheckStep, ...]:
        return tuple(step for step in self.steps if not step.passed)

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "application_version": self.application_version,
            "project_root": str(self.project_root),
            "passed": self.passed,
            "failure_count": len(self.failures),
            "steps": [asdict(step) for step in self.steps],
            "artifact_paths": [str(path) for path in self.artifact_paths],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def _step(name: str, passed: bool, message: str, *details: str) -> ReleaseCheckStep:
    return ReleaseCheckStep(name, passed, message, tuple(details))


def _audit_step(audit: AuditReport) -> ReleaseCheckStep:
    if audit.failures:
        return _step(
            "repository-audit",
            False,
            "Audyt repozytorium wykrył błędy.",
            *(f"{item.name}: {item.message}" for item in audit.failures),
        )
    return _step(
        "repository-audit",
        True,
        "Audyt repozytorium zakończył się bez błędów.",
        f"Kontrole: {len(audit.checks)}",
        f"Ostrzeżenia: {len(audit.warnings)}",
    )


def _build_state(result: PlanningResult) -> dict[str, Any]:
    requests = list(result.scenario.request_set.requests)
    now = datetime.now(timezone.utc)
    state: dict[str, Any] = {
        CUSTOM_REQUESTS_STATE_KEY: requests,
        PLANNING_RESULT_STATE_KEY: result,
        SCHEDULE_HISTORY_STATE_KEY: [
            build_schedule_history_entry(result, event_type="RELEASE_CHECK")
        ],
        PROJECT_METADATA_STATE_KEY: ProjectMetadata(
            project_id="PROJECT-RELEASE-CHECK",
            name="SatPlan release check",
            description=(
                "Deterministyczny test E2E: scenariusz, planowanie, archiwum "
                "projektu oraz raport naukowy."
            ),
            created_at_utc=now,
            exported_at_utc=now,
        ),
    }
    if requests:
        state[AOI_STATE_KEY] = requests[0].geometry
    return state


def _run_planner(
    scenario_service: ScenarioService,
    planning_service: PlanningService,
    *,
    algorithm: PlanningAlgorithm,
    cp_sat_time_limit_s: float,
) -> PlanningResult:
    scenario = scenario_service.load("EXAMPLE")
    return planning_service.run(
        scenario=scenario,
        options=PlanningOptions(
            algorithm=algorithm,
            memory_reserve_ratio=0.15,
            use_dynamic_transition_model=True,
            cp_sat_time_limit_s=cp_sat_time_limit_s,
            cp_sat_num_search_workers=1,
            cp_sat_random_seed=20260717,
        ),
        schedule_id=f"SCHEDULE-RELEASE-{algorithm.value.replace('_', '-')}",
        schedule_name=f"Release check — {algorithm.value.replace('_', '-')}",
    )


def run_release_check(
    paths: ProjectPaths,
    *,
    algorithms: tuple[PlanningAlgorithm, ...] = (
        PlanningAlgorithm.GREEDY,
        PlanningAlgorithm.CP_SAT,
    ),
    cp_sat_time_limit_s: float = 2.0,
    output_directory: Path | None = None,
) -> ReleaseCheckReport:
    """Uruchamia deterministyczny test E2E przygotowujący wydanie."""

    steps: list[ReleaseCheckStep] = []
    artifacts: list[Path] = []
    audit = run_project_audit(paths)
    steps.append(_audit_step(audit))

    scenario_service = ScenarioService(project_root=paths.root)
    planning_service = PlanningService()
    results: dict[PlanningAlgorithm, PlanningResult] = {}

    try:
        scenario = scenario_service.load("EXAMPLE")
    except Exception as error:  # noqa: BLE001 - report must preserve failure
        steps.append(
            _step(
                "scenario-load",
                False,
                "Nie udało się wczytać scenariusza EXAMPLE.",
                repr(error),
            )
        )
        return ReleaseCheckReport(
            generated_at_utc=datetime.now(timezone.utc),
            application_version=__version__,
            project_root=paths.root,
            steps=tuple(steps),
            artifact_paths=(),
        )

    steps.append(
        _step(
            "scenario-load",
            True,
            "Scenariusz EXAMPLE jest spójny.",
            f"Satelity: {scenario.satellite_count}",
            f"Zlecenia: {scenario.active_request_count}",
            f"Okazje: {scenario.opportunity_count}",
        )
    )

    for algorithm in algorithms:
        try:
            result = _run_planner(
                scenario_service,
                planning_service,
                algorithm=algorithm,
                cp_sat_time_limit_s=cp_sat_time_limit_s,
            )
        except Exception as error:  # noqa: BLE001 - report all solver failures
            steps.append(
                _step(
                    f"planning-{algorithm.value.lower()}",
                    False,
                    f"Planowanie {algorithm.value} zakończyło się błędem.",
                    repr(error),
                )
            )
            continue

        results[algorithm] = result
        steps.append(
            _step(
                f"planning-{algorithm.value.lower()}",
                result.total_acquisitions > 0,
                f"Planowanie {algorithm.value} zakończyło się poprawnie.",
                f"Status solvera: {result.solver_status}",
                f"Akwizycje: {result.total_acquisitions}",
                f"Zrealizowane zlecenia: {result.fully_satisfied_requests}",
                f"Funkcja celu: {result.objective_value:.3f}",
            )
        )

    preferred = results.get(PlanningAlgorithm.CP_SAT) or results.get(
        PlanningAlgorithm.GREEDY
    )
    if preferred is None:
        steps.append(
            _step(
                "artifact-pipeline",
                False,
                "Brak harmonogramu do walidacji archiwum i raportu.",
            )
        )
        return ReleaseCheckReport(
            generated_at_utc=datetime.now(timezone.utc),
            application_version=__version__,
            project_root=paths.root,
            steps=tuple(steps),
            artifact_paths=(),
        )

    state = _build_state(preferred)
    archive_service = ProjectArchiveService()
    try:
        exported = archive_service.export_project(
            state,
            project_name="SatPlan release check",
            description="Automatyczny test przenośnego archiwum projektu.",
            author="",
        )
        preview = archive_service.preview_archive(exported.archive_bytes)
        archive_ok = (
            preview.request_count == preferred.scenario.active_request_count
            and preview.file_count >= 4
            and len(exported.archive_bytes) > 0
        )
    except Exception as error:  # noqa: BLE001
        steps.append(
            _step(
                "project-archive-roundtrip",
                False,
                "Eksport lub walidacja archiwum projektu nie powiodły się.",
                repr(error),
            )
        )
        exported = None
    else:
        steps.append(
            _step(
                "project-archive-roundtrip",
                archive_ok,
                "Archiwum projektu przeszło eksport i walidację importu.",
                f"Pliki: {preview.file_count}",
                f"Zlecenia: {preview.request_count}",
                f"Rozmiar ZIP: {len(exported.archive_bytes)} B",
            )
        )

    try:
        report = ScientificReportService().build(
            state,
            config=ScientificReportConfig(
                title="SatPlan — raport kontroli wydania",
                description="Automatyczny test generatora wyników.",
                include_stk_validation=False,
                include_benchmarks=False,
            ),
        )
        required_report_files = {
            "report.html",
            "report.docx",
            "results.xlsx",
            "report.json",
        }
        report_ok = required_report_files.issubset(report.included_files)
    except Exception as error:  # noqa: BLE001
        steps.append(
            _step(
                "scientific-report",
                False,
                "Generator raportu naukowego zakończył się błędem.",
                repr(error),
            )
        )
        report = None
    else:
        steps.append(
            _step(
                "scientific-report",
                report_ok,
                "Pakiet raportowy HTML/DOCX/XLSX/JSON został wygenerowany.",
                f"Pliki: {len(report.included_files)}",
                f"Rozmiar ZIP: {report.size_bytes} B",
            )
        )

    if output_directory is not None:
        output_directory = Path(output_directory)
        if not output_directory.is_absolute():
            output_directory = paths.root / output_directory
        output_directory.mkdir(parents=True, exist_ok=True)
        if exported is not None:
            archive_path = output_directory / "release-check.satplan.zip"
            archive_path.write_bytes(exported.archive_bytes)
            artifacts.append(archive_path)
        if report is not None:
            report_path = output_directory / "release-check-report.zip"
            report_path.write_bytes(report.archive_bytes)
            artifacts.append(report_path)

    return ReleaseCheckReport(
        generated_at_utc=datetime.now(timezone.utc),
        application_version=__version__,
        project_root=paths.root,
        steps=tuple(steps),
        artifact_paths=tuple(artifacts),
    )


__all__ = [
    "ReleaseCheckReport",
    "ReleaseCheckStep",
    "run_release_check",
]
