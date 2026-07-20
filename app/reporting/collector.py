from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.analysis.algorithm_benchmark import AlgorithmBenchmarkResult
from app.integrations.stk_validation import AccessValidationResult, AerValidationResult
from app.models.request import ObservationRequest
from app.projects.history import PROJECT_METADATA_STATE_KEY, SCHEDULE_HISTORY_STATE_KEY
from app.projects.models import APPLICATION_VERSION, ProjectMetadata
from app.projects.service import (
    ACCESS_RESULT_STATE_KEY,
    BENCHMARK_RESULT_STATE_KEY,
    CUSTOM_REQUESTS_STATE_KEY,
    OPPORTUNITY_BUILDS_STATE_KEY,
    ORBIT_SNAPSHOT_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
)
from app.reporting.models import ScientificReportConfig, ScientificReportSnapshot
from app.services.contracts import PlanningResult
from app.services.orbit_service import PublicConstellationSnapshot


_STK_ACCESS_STATE_KEY = "stk_access_validation_result"
_STK_AER_STATE_KEY = "stk_aer_validation_result"


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    value = _enum_value(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (tuple, list, set)):
        return " | ".join(str(_serialize_value(item)) for item in value)
    if isinstance(value, dict):
        return " | ".join(
            f"{key}={_serialize_value(item)}" for key, item in sorted(value.items())
        )
    return str(value)


def _row(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _serialize_value(value) for key, value in payload.items()}


def _object_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return {"value": str(value)}


def _satellite_rows(
    snapshot: PublicConstellationSnapshot | None,
    planning: PlanningResult | None,
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    if planning is not None:
        for satellite in planning.scenario.catalog.satellites:
            sensor = planning.scenario.catalog.get_sensor(satellite.sensor_id)
            orbit = planning.scenario.catalog.get_orbit(satellite.orbit_id)
            rows.append(
                _row(
                    {
                        "satellite_id": satellite.satellite_id,
                        "name": satellite.name,
                        "sensor_type": sensor.sensor_type,
                        "sensor_id": satellite.sensor_id,
                        "orbit_id": satellite.orbit_id,
                        "altitude_km": orbit.altitude_km,
                        "inclination_deg": orbit.inclination_deg,
                        "memory_capacity_mb": satellite.memory_capacity_mb,
                        "max_acquisitions_per_day": (
                            satellite.max_acquisitions_per_day
                        ),
                        "max_imaging_time_per_day_s": (
                            satellite.max_imaging_time_per_day_s
                        ),
                        "source_type": satellite.source_type,
                    }
                )
            )
        return tuple(rows)

    if snapshot is not None:
        for satellite in snapshot.satellites:
            record = satellite.record
            rows.append(
                _row(
                    {
                        "satellite_id": satellite.slot_id,
                        "name": record.object_name,
                        "family": satellite.family,
                        "norad_cat_id": record.norad_cat_id,
                        "epoch_utc": record.epoch_utc,
                        "inclination_deg": record.inclination_deg,
                        "eccentricity": record.eccentricity,
                        "orbital_period_minutes": record.orbital_period_minutes,
                        "source": "CelesTrak OMM/GP",
                    }
                )
            )
    return tuple(rows)


def _request_rows(requests: list[ObservationRequest]) -> tuple[dict[str, Any], ...]:
    return tuple(
        _row(
            {
                "request_id": request.request_id,
                "name": request.name,
                "mode": request.request_mode,
                "sensor_types": request.requested_sensor_types,
                "priority": request.priority,
                "mandatory": request.is_mandatory,
                "earliest_start_utc": request.earliest_start_utc,
                "latest_end_utc": request.latest_end_utc,
                "max_resolution_m": request.max_resolution_m,
                "minimum_coverage_ratio": request.minimum_coverage_ratio,
                "max_cloud_cover": request.max_cloud_cover,
                "max_incidence_angle_deg": request.max_incidence_angle_deg,
                "max_off_nadir_deg": request.max_off_nadir_deg,
                "max_dual_separation_h": request.max_dual_separation_hours,
                "status": request.status,
            }
        )
        for request in requests
    )


def _access_rows(access: Any) -> tuple[dict[str, Any], ...]:
    if access is None:
        return ()
    return tuple(_row(window.to_dict()) for window in access.windows)


def _opportunity_rows(builds: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for request_id in sorted(builds):
        build = builds[request_id]
        for opportunity in build.opportunities:
            rows.append(_row(opportunity.model_dump(mode="json")))
    return tuple(rows)


def _schedule_rows(planning: PlanningResult | None) -> tuple[dict[str, Any], ...]:
    if planning is None:
        return ()
    return tuple(
        _row(entry.model_dump(mode="json"))
        for entry in planning.schedule.active_entries
    )


def _diagnostic_rows(planning: PlanningResult | None) -> tuple[dict[str, Any], ...]:
    if planning is None:
        return ()
    return tuple(_row(asdict(item)) for item in planning.analysis.request_diagnostics)


def _satellite_kpi_rows(planning: PlanningResult | None) -> tuple[dict[str, Any], ...]:
    if planning is None:
        return ()
    return tuple(_row(asdict(item)) for item in planning.analysis.satellite_kpis)


def _benchmark_rows(
    benchmark: AlgorithmBenchmarkResult | None,
) -> tuple[dict[str, Any], ...]:
    if benchmark is None:
        return ()
    return tuple(_row(asdict(item)) for item in benchmark.run_records)


def _benchmark_summary_rows(
    benchmark: AlgorithmBenchmarkResult | None,
) -> tuple[dict[str, Any], ...]:
    if benchmark is None:
        return ()
    return tuple(_row(asdict(item)) for item in benchmark.summary_records)


def _history_rows(history: Any) -> tuple[dict[str, Any], ...]:
    return tuple(_row(item) for item in history or ())


def _stk_rows(value: Any) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    return tuple(_row(item.to_dict()) for item in value.matched)


def _overview_metrics(
    *,
    requests: list[ObservationRequest],
    satellites: tuple[dict[str, Any], ...],
    access_rows: tuple[dict[str, Any], ...],
    opportunity_rows: tuple[dict[str, Any], ...],
    planning: PlanningResult | None,
    benchmark: AlgorithmBenchmarkResult | None,
    history: Any,
    access_validation: AccessValidationResult | None,
) -> tuple[dict[str, Any], ...]:
    feasible_opportunities = sum(
        str(row.get("is_feasible", "")).lower() in {"true", "1"}
        for row in opportunity_rows
    )
    metrics: list[dict[str, Any]] = [
        {"metric": "Satelity", "value": len(satellites), "unit": "szt."},
        {"metric": "Zlecenia", "value": len(requests), "unit": "szt."},
        {"metric": "Okna dostępu", "value": len(access_rows), "unit": "szt."},
        {
            "metric": "Okazje akwizycyjne",
            "value": len(opportunity_rows),
            "unit": "szt.",
        },
        {
            "metric": "Wykonalne okazje",
            "value": feasible_opportunities,
            "unit": "szt.",
        },
        {
            "metric": "Wersje harmonogramu",
            "value": len(history or ()),
            "unit": "szt.",
        },
    ]
    if planning is not None:
        metrics.extend(
            [
                {
                    "metric": "Algorytm",
                    "value": planning.algorithm.value,
                    "unit": "",
                },
                {
                    "metric": "Funkcja celu",
                    "value": round(planning.objective_value, 3),
                    "unit": "pkt",
                },
                {
                    "metric": "Zrealizowane zlecenia",
                    "value": planning.fully_satisfied_requests,
                    "unit": "szt.",
                },
                {
                    "metric": "Akwizycje w planie",
                    "value": planning.total_acquisitions,
                    "unit": "szt.",
                },
                {
                    "metric": "Stopień realizacji",
                    "value": round(planning.analysis.satisfaction_ratio * 100.0, 2),
                    "unit": "%",
                },
            ]
        )
    if benchmark is not None:
        metrics.extend(
            [
                {
                    "metric": "Przebiegi benchmarku",
                    "value": len(benchmark.run_records),
                    "unit": "szt.",
                },
                {
                    "metric": "CP-SAT lepszy",
                    "value": benchmark.cp_sat_better_count,
                    "unit": "par",
                },
            ]
        )
    if access_validation is not None:
        metrics.extend(
            [
                {
                    "metric": "Dopasowanie okien STK",
                    "value": round(access_validation.match_rate * 100.0, 2),
                    "unit": "%",
                },
                {
                    "metric": "MAE startu względem STK",
                    "value": round(
                        access_validation.start_error_statistics_s.mean_absolute_error,
                        3,
                    ),
                    "unit": "s",
                },
            ]
        )
    return tuple(metrics)


def _narrative(
    planning: PlanningResult | None,
    benchmark: AlgorithmBenchmarkResult | None,
    access_validation: AccessValidationResult | None,
    aer_validation: AerValidationResult | None,
) -> dict[str, str]:
    methodology = (
        "Dostępność geometryczną wyznaczono na podstawie publicznych elementów "
        "orbitalnych OMM/GP i propagacji SGP4. Okazje optyczne oceniono z użyciem "
        "prognozy zachmurzenia Open-Meteo, natomiast harmonogram zbudowano "
        "algorytmem Greedy lub CP-SAT z uwzględnieniem zasobów i przeorientowań."
    )
    results = "Brak harmonogramu w bieżącej sesji."
    if planning is not None:
        analysis = planning.analysis
        results = (
            f"Algorytm {planning.algorithm.value} wybrał "
            f"{analysis.total_acquisitions} akwizycji i w pełni zrealizował "
            f"{analysis.fully_satisfied_requests} z "
            f"{analysis.total_active_requests} aktywnych zleceń. "
            f"Stopień realizacji wyniósł {analysis.satisfaction_ratio:.1%}, "
            f"a wartość funkcji celu {analysis.objective_value:.3f}."
        )
    benchmark_text = "Brak wyników benchmarku w bieżącej sesji."
    if benchmark is not None:
        benchmark_text = (
            f"Benchmark obejmował {len(benchmark.run_records)} przebiegów. "
            f"CP-SAT uzyskał wyższą wartość funkcji celu w "
            f"{benchmark.cp_sat_better_count} porównaniach i nie był gorszy w "
            f"{benchmark.cp_sat_not_worse_count} porównaniach. Średnia zmiana "
            f"wartości celu wyniosła "
            f"{benchmark.mean_objective_improvement_pct:.2f}%."
        )
    validation_text = "Brak zaimportowanych wyników walidacji STK."
    if access_validation is not None:
        validation_text = (
            f"Dopasowano {len(access_validation.matched)} okien, osiągając "
            f"skuteczność {access_validation.match_rate:.1%}. MAE granicy startu "
            f"wyniosło "
            f"{access_validation.start_error_statistics_s.mean_absolute_error:.2f} s, "
            f"a MAE długości "
            f"{access_validation.duration_error_statistics_s.mean_absolute_error:.2f} s."
        )
        if aer_validation is not None:
            validation_text += (
                f" Dla AER skuteczność dopasowania wyniosła "
                f"{aer_validation.match_rate:.1%}, a MAE elewacji "
                f"{aer_validation.elevation_error_statistics_deg.mean_absolute_error:.3f}°."
            )
    return {
        "methodology": methodology,
        "results": results,
        "benchmark": benchmark_text,
        "validation": validation_text,
        "interpretation": (
            "Wyniki należy interpretować jako ocenę modelu planistycznego "
            "opartego na danych publicznych. Nie stanowią potwierdzenia "
            "operacyjnej dostępności satelitów ani gwarancji taskingu operatora."
        ),
    }


def collect_report_snapshot(
    state: Mapping[str, Any],
    *,
    config: ScientificReportConfig,
) -> ScientificReportSnapshot:
    metadata = state.get(PROJECT_METADATA_STATE_KEY)
    if not isinstance(metadata, ProjectMetadata):
        metadata = None

    requests = list(state.get(CUSTOM_REQUESTS_STATE_KEY, ()))
    requests = [item for item in requests if isinstance(item, ObservationRequest)]
    snapshot = state.get(ORBIT_SNAPSHOT_STATE_KEY)
    if not isinstance(snapshot, PublicConstellationSnapshot):
        snapshot = None
    planning = state.get(PLANNING_RESULT_STATE_KEY)
    if not isinstance(planning, PlanningResult):
        planning = None
    benchmark = state.get(BENCHMARK_RESULT_STATE_KEY)
    if not isinstance(benchmark, AlgorithmBenchmarkResult):
        benchmark = None
    access = state.get(ACCESS_RESULT_STATE_KEY)
    builds = state.get(OPPORTUNITY_BUILDS_STATE_KEY, {})
    if not isinstance(builds, Mapping):
        builds = {}
    history = state.get(SCHEDULE_HISTORY_STATE_KEY, ())

    access_validation = state.get(_STK_ACCESS_STATE_KEY)
    if not isinstance(access_validation, AccessValidationResult):
        access_validation = None
    aer_validation = state.get(_STK_AER_STATE_KEY)
    if not isinstance(aer_validation, AerValidationResult):
        aer_validation = None

    satellite_rows = _satellite_rows(snapshot, planning)
    request_rows = _request_rows(requests)
    access_rows = _access_rows(access)
    opportunity_rows = _opportunity_rows(builds)
    schedule_rows = _schedule_rows(planning)
    diagnostic_rows = _diagnostic_rows(planning)
    satellite_kpi_rows = _satellite_kpi_rows(planning)
    benchmark_rows = _benchmark_rows(benchmark) if config.include_benchmarks else ()
    benchmark_summary_rows = (
        _benchmark_summary_rows(benchmark) if config.include_benchmarks else ()
    )
    stk_access_rows = (
        _stk_rows(access_validation) if config.include_stk_validation else ()
    )
    stk_aer_rows = _stk_rows(aer_validation) if config.include_stk_validation else ()

    warnings: list[str] = []
    if planning is None:
        warnings.append("Bieżąca sesja nie zawiera harmonogramu.")
    if benchmark is None and config.include_benchmarks:
        warnings.append("Bieżąca sesja nie zawiera benchmarku algorytmów.")
    if access_validation is None and config.include_stk_validation:
        warnings.append("Bieżąca sesja nie zawiera walidacji okien względem STK.")
    if not requests:
        warnings.append("Bieżąca sesja nie zawiera zleceń użytkownika.")

    limitations = (
        "Publiczne OMM/GP oraz propagacja SGP4 nie są precyzyjnymi efemerydami operatora.",
        "Profile ICEYE i Pléiades Neo są publicznym modelem badawczym, nie pełną specyfikacją operacyjną.",
        "Prognoza zachmurzenia wpływa wyłącznie na okazje optyczne; SAR pozostaje niezależny od chmur.",
        "Geometria footprintu i pokrycia AOI jest uproszczona względem narzędzi operatorskich.",
        "Wynik harmonogramowania zależy od przyjętych wag funkcji celu i limitów zasobów.",
    )

    return ScientificReportSnapshot(
        generated_at_utc=datetime.now(timezone.utc),
        title=config.title.strip(),
        author=config.author.strip(),
        institution=config.institution.strip(),
        description=config.description.strip(),
        include_methodology=config.include_methodology,
        include_limitations=config.include_limitations,
        include_stk_validation=config.include_stk_validation,
        include_benchmarks=config.include_benchmarks,
        project_name=metadata.name if metadata else "Bieżąca sesja SatPlan",
        project_id=metadata.project_id if metadata else "SESSION-REPORT",
        application_version=(
            metadata.application_version if metadata else APPLICATION_VERSION
        ),
        overview_metrics=_overview_metrics(
            requests=requests,
            satellites=satellite_rows,
            access_rows=access_rows,
            opportunity_rows=opportunity_rows,
            planning=planning,
            benchmark=benchmark,
            history=history,
            access_validation=access_validation,
        ),
        satellite_rows=satellite_rows,
        request_rows=request_rows,
        access_rows=access_rows,
        opportunity_rows=opportunity_rows,
        schedule_rows=schedule_rows,
        request_diagnostic_rows=diagnostic_rows,
        satellite_kpi_rows=satellite_kpi_rows,
        benchmark_rows=benchmark_rows,
        benchmark_summary_rows=benchmark_summary_rows,
        schedule_history_rows=_history_rows(history),
        stk_access_rows=stk_access_rows,
        stk_aer_rows=stk_aer_rows,
        narrative=_narrative(
            planning,
            benchmark if config.include_benchmarks else None,
            access_validation if config.include_stk_validation else None,
            aer_validation if config.include_stk_validation else None,
        ),
        limitations=limitations if config.include_limitations else (),
        warnings=tuple(warnings),
    )
