from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config.paths import ProjectPaths
from app.integrations.access import AccessCalculationResult
from app.integrations.orbits import Sgp4OrbitPropagator
from app.models.enums import PlanningAlgorithm, SensorType
from app.projects import ProjectArchiveService, ProjectMetadata
from app.projects.codec import decode_access_result, decode_orbit_snapshot
from app.projects.history import (
    PROJECT_METADATA_STATE_KEY,
    SCHEDULE_HISTORY_STATE_KEY,
    build_schedule_history_entry,
)
from app.projects.service import (
    ACCESS_RESULT_STATE_KEY,
    AOI_STATE_KEY,
    CUSTOM_REQUESTS_STATE_KEY,
    ORBIT_SNAPSHOT_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
)
from app.quality.audit import AuditReport, run_project_audit
from app.reporting import ScientificReportConfig, ScientificReportService
from app.services import (
    PlanningOptions,
    PlanningService,
    ReplanningService,
    ScenarioService,
)
from app.services.contracts import PlanningResult, ReplanningResult
from app.services.orbit_service import PublicConstellationSnapshot
from app.tracking import LiveTrackingService, ObserverSite
from app.version import __version__


RELEASE_SCENARIO_ID = "POLAND_DEMO"
DEMO_ARTIFACT_DIRECTORY = Path("examples") / "poland_demo"


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


def _build_state(
    result: PlanningResult,
    *,
    orbit_snapshot: PublicConstellationSnapshot | None = None,
    access_result: AccessCalculationResult | None = None,
) -> dict[str, Any]:
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
                "Deterministyczny test E2E: scenariusz, OMM, SGP4, access, "
                "pogoda EO, planowanie, przeplanowanie, archiwum projektu "
                "oraz raport naukowy."
            ),
            created_at_utc=now,
            exported_at_utc=now,
        ),
    }
    if requests:
        state[AOI_STATE_KEY] = requests[0].geometry
    if orbit_snapshot is not None:
        state[ORBIT_SNAPSHOT_STATE_KEY] = orbit_snapshot
    if access_result is not None:
        state[ACCESS_RESULT_STATE_KEY] = access_result
    return state


def _run_planner(
    scenario_service: ScenarioService,
    planning_service: PlanningService,
    *,
    algorithm: PlanningAlgorithm,
    cp_sat_time_limit_s: float,
) -> PlanningResult:
    scenario = scenario_service.load(RELEASE_SCENARIO_ID)
    return planning_service.run(
        scenario=scenario,
        options=PlanningOptions(
            algorithm=algorithm,
            memory_reserve_ratio=0.15,
            enable_downlink_planning=True,
            require_full_downlink=True,
            allow_simultaneous_imaging_downlink=False,
            downlink_capacity_reserve_ratio=0.10,
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
        scenario = scenario_service.load(RELEASE_SCENARIO_ID)
    except Exception as error:  # noqa: BLE001 - report must preserve failure
        steps.append(
            _step(
                "scenario-load",
                False,
                f"Nie udało się wczytać scenariusza {RELEASE_SCENARIO_ID}.",
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
            f"Scenariusz {RELEASE_SCENARIO_ID} jest spójny.",
            f"Satelity: {scenario.satellite_count}",
            f"Zlecenia: {scenario.active_request_count}",
            f"Okazje: {scenario.opportunity_count}",
            f"Downlinki: {scenario.downlink_opportunity_count}",
        )
    )

    orbit_snapshot: PublicConstellationSnapshot | None = None
    access_result: AccessCalculationResult | None = None
    try:
        artifact_directory = paths.root / DEMO_ARTIFACT_DIRECTORY
        orbit_payload = json.loads(
            (artifact_directory / "orbits_omm.json").read_text(encoding="utf-8")
        )
        access_payload = json.loads(
            (artifact_directory / "access_windows.json").read_text(encoding="utf-8")
        )
        orbit_snapshot = decode_orbit_snapshot(orbit_payload)
        access_result = decode_access_result(access_payload)
        first_track = Sgp4OrbitPropagator().ground_track(
            orbit_snapshot.satellites[0],
            start_utc=scenario.request_set.horizon_start_utc,
            duration=timedelta(minutes=5),
            step=timedelta(minutes=1),
        )
        reference_ok = (
            len(orbit_snapshot.satellites) == 6
            and len(first_track.states) == 6
            and len(access_result.windows) >= 3
            and access_result.request_id
            in {request.request_id for request in scenario.request_set.requests}
        )
    except Exception as error:  # noqa: BLE001
        steps.append(
            _step(
                "demo-orbit-access",
                False,
                "Walidacja OMM, SGP4 i okien dostępu demo nie powiodła się.",
                repr(error),
            )
        )
    else:
        steps.append(
            _step(
                "demo-orbit-access",
                reference_ok,
                "Dane OMM, propagacja SGP4 i okna dostępu demo są spójne.",
                f"Obiekty OMM: {len(orbit_snapshot.satellites)}",
                f"Stany próbnej propagacji: {len(first_track.states)}",
                f"Okna dostępu: {len(access_result.windows)}",
            )
        )

    if orbit_snapshot is not None:
        try:
            observer = ObserverSite(
                name="WAT Warszawa",
                latitude_deg=52.2532,
                longitude_deg=20.8997,
                altitude_m=110.0,
            )
            tracking_service = LiveTrackingService()
            tracking_states = tracking_service.current_states(
                orbit_snapshot,
                observer=observer,
                timestamp_utc=scenario.request_set.horizon_start_utc,
            )
            tracking_passes = tracking_service.predict_passes(
                orbit_snapshot,
                observer=observer,
                start_utc=scenario.request_set.horizon_start_utc,
                duration=timedelta(hours=24),
                step=timedelta(seconds=60),
                minimum_elevation_deg=0.0,
            )
            tracking_ok = (
                len(tracking_states) == len(orbit_snapshot.satellites)
                and len(tracking_passes) > 0
                and all(state.topocentric.range_km > 0.0 for state in tracking_states)
                and all(0.0 <= item.quality_score <= 100.0 for item in tracking_passes)
                and all(item.time_above_10_deg_s >= 0.0 for item in tracking_passes)
            )
        except Exception as error:  # noqa: BLE001
            steps.append(
                _step(
                    "live-tracking-sky-map",
                    False,
                    "Mapa nieba i predykcja przelotów zakończyły się błędem.",
                    repr(error),
                )
            )
        else:
            steps.append(
                _step(
                    "live-tracking-sky-map",
                    tracking_ok,
                    "Śledzenie SGP4 i predykcja AOS/MAX/LOS są spójne.",
                    f"Stany bieżące: {len(tracking_states)}",
                    f"Przeloty 24 h: {len(tracking_passes)}",
                    f"Obserwator: {observer.name}",
                    f"Najlepszy wynik: {max(item.quality_score for item in tracking_passes):.1f}",
                )
            )

    optical_opportunities = tuple(
        opportunity
        for opportunity in scenario.opportunity_set.opportunities
        if opportunity.sensor_type == SensorType.OPTICAL
    )
    optical_weather_complete = bool(optical_opportunities) and all(
        opportunity.cloud_cover is not None
        and opportunity.sun_elevation_deg is not None
        for opportunity in optical_opportunities
    )
    cloud_rejected = sum(
        opportunity.cloud_cover is not None and not opportunity.is_feasible
        for opportunity in optical_opportunities
    )
    steps.append(
        _step(
            "eo-weather-opportunities",
            optical_weather_complete and cloud_rejected > 0,
            "Dane zachmurzenia EO przechodzą do okazji demonstracyjnych.",
            f"Okazje EO: {len(optical_opportunities)}",
            f"EO odrzucone przez warunki: {cloud_rejected}",
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
        resource_ok = (
            len(result.schedule.resource_summaries)
            == result.scenario.satellite_count
            and all(
                summary.memory_feasible and summary.delivery_complete
                for summary in result.schedule.resource_summaries
            )
        )
        steps.append(
            _step(
                f"planning-{algorithm.value.lower()}",
                result.total_acquisitions > 0 and resource_ok,
                f"Planowanie {algorithm.value} zakończyło się poprawnie.",
                f"Status solvera: {result.solver_status}",
                f"Akwizycje: {result.total_acquisitions}",
                f"Zrealizowane zlecenia: {result.fully_satisfied_requests}",
                f"Funkcja celu: {result.objective_value:.3f}",
                f"Okna downlinku: {result.schedule.selected_downlink_windows}",
                (
                    "Wysłane dane: "
                    f"{result.schedule.total_downlinked_data_mb:.1f} MB"
                ),
            )
        )

    preferred = (
        results.get(PlanningAlgorithm.HYBRID)
        or results.get(PlanningAlgorithm.CP_SAT)
        or results.get(PlanningAlgorithm.GREEDY)
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

    replanning_result: ReplanningResult | None = None
    try:
        replanning_result = ReplanningService().run(
            scenario=preferred.scenario,
            previous_schedule=preferred.schedule,
            options=preferred.options,
            replan_at_utc=(
                preferred.scenario.request_set.horizon_start_utc
                + timedelta(hours=18)
            ),
            freeze_duration=timedelta(hours=2),
            schedule_id="SCHEDULE-RELEASE-REPLANNED",
            schedule_name="Release check — przeplanowanie",
        )
        replanning_ok = (
            replanning_result.schedule.total_acquisitions > 0
            and replanning_result.fixed_count > 0
            and replanning_result.schedule.horizon_start_utc
            == preferred.schedule.horizon_start_utc
            and replanning_result.schedule.horizon_end_utc
            == preferred.schedule.horizon_end_utc
        )
    except Exception as error:  # noqa: BLE001
        steps.append(
            _step(
                "replanning",
                False,
                "Dynamiczne przeplanowanie zakończyło się błędem.",
                repr(error),
            )
        )
    else:
        steps.append(
            _step(
                "replanning",
                replanning_ok,
                "Harmonogram przeszedł przeplanowanie z oknem zamrożonym.",
                f"Stałe akwizycje: {replanning_result.fixed_count}",
                f"Wynikowe akwizycje: {replanning_result.schedule.total_acquisitions}",
                f"Status solvera: {replanning_result.solver_status}",
            )
        )

    state = _build_state(
        preferred,
        orbit_snapshot=orbit_snapshot,
        access_result=access_result,
    )
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
