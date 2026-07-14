from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from statistics import mean

from app.models.catalog import SystemCatalog
from app.models.enums import RequestMode, SensorType
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.models.schedule import Schedule, ScheduleEntry


class RequestFulfillmentStatus(str, Enum):
    """Stan realizacji pojedynczego zlecenia."""

    FULLY_SATISFIED = "FULLY_SATISFIED"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    UNASSIGNED = "UNASSIGNED"


class UnassignedReasonCode(str, Enum):
    """Kod przyczyny braku pełnej realizacji zlecenia."""

    NO_FEASIBLE_OPPORTUNITY = "NO_FEASIBLE_OPPORTUNITY"
    MISSING_SAR_OPPORTUNITY = "MISSING_SAR_OPPORTUNITY"
    MISSING_OPTICAL_OPPORTUNITY = "MISSING_OPTICAL_OPPORTUNITY"
    SATELLITE_INACTIVE = "SATELLITE_INACTIVE"
    TRANSITION_CONFLICT = "TRANSITION_CONFLICT"
    MEMORY_LIMIT = "MEMORY_LIMIT"
    ACQUISITION_LIMIT = "ACQUISITION_LIMIT"
    IMAGING_TIME_LIMIT = "IMAGING_TIME_LIMIT"
    GREEDY_ORDERING = "GREEDY_ORDERING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SatelliteKPI:
    """Wskaźniki wykorzystania pojedynczego satelity."""

    satellite_id: str
    sensor_type: str
    scheduled_acquisitions: int
    imaging_time_s: float
    imaging_time_limit_s: float
    imaging_utilization_ratio: float
    generated_data_mb: float
    initial_memory_usage_mb: float
    planning_memory_limit_mb: float
    final_memory_usage_mb: float
    memory_utilization_ratio: float
    acquisition_limit: int
    acquisition_utilization_ratio: float


@dataclass(frozen=True)
class RequestDiagnostic:
    """Wynik realizacji oraz diagnostyka pojedynczego zlecenia."""

    request_id: str
    request_mode: str
    priority: int
    is_mandatory: bool
    fulfillment_status: str
    scheduled_entry_count: int
    scheduled_sensor_types: tuple[str, ...]
    feasible_opportunity_count: int
    feasible_sar_count: int
    feasible_optical_count: int
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class EntryKPI:
    """Wiersz raportu szczegółowego zaplanowanej akwizycji."""

    entry_id: str
    opportunity_id: str
    request_id: str
    satellite_id: str
    sensor_type: str
    mode_id: str
    start_utc: str
    end_utc: str
    duration_s: float
    estimated_data_volume_mb: float
    objective_contribution: float
    quality_score: float
    coverage_ratio: float
    cloud_cover: float | None
    incidence_angle_deg: float | None
    off_nadir_angle_deg: float


@dataclass(frozen=True)
class ScheduleAnalysis:
    """Kompletny raport KPI dla harmonogramu."""

    schedule_id: str
    schedule_status: str

    total_active_requests: int
    requests_with_entries: int
    fully_satisfied_requests: int
    partially_satisfied_requests: int
    unassigned_requests: int

    mandatory_requests: int
    mandatory_satisfied_requests: int

    satisfaction_ratio: float
    mandatory_satisfaction_ratio: float

    total_acquisitions: int
    sar_acquisitions: int
    optical_acquisitions: int

    total_duration_s: float
    total_data_volume_mb: float
    objective_value: float

    average_selected_quality: float
    average_selected_coverage: float
    selected_to_feasible_ratio: float

    request_diagnostics: tuple[RequestDiagnostic, ...]
    satellite_kpis: tuple[SatelliteKPI, ...]
    entry_kpis: tuple[EntryKPI, ...]

    unassigned_reason_counts: dict[str, int]

    def kpi_rows(self) -> list[dict[str, object]]:
        """Zwraca główne KPI w formacie przeznaczonym do CSV."""

        rows: list[dict[str, object]] = [
            {
                "metric": "schedule_id",
                "value": self.schedule_id,
            },
            {
                "metric": "schedule_status",
                "value": self.schedule_status,
            },
            {
                "metric": "total_active_requests",
                "value": self.total_active_requests,
            },
            {
                "metric": "requests_with_entries",
                "value": self.requests_with_entries,
            },
            {
                "metric": "fully_satisfied_requests",
                "value": self.fully_satisfied_requests,
            },
            {
                "metric": "partially_satisfied_requests",
                "value": self.partially_satisfied_requests,
            },
            {
                "metric": "unassigned_requests",
                "value": self.unassigned_requests,
            },
            {
                "metric": "mandatory_requests",
                "value": self.mandatory_requests,
            },
            {
                "metric": "mandatory_satisfied_requests",
                "value": self.mandatory_satisfied_requests,
            },
            {
                "metric": "satisfaction_ratio",
                "value": self.satisfaction_ratio,
            },
            {
                "metric": "mandatory_satisfaction_ratio",
                "value": self.mandatory_satisfaction_ratio,
            },
            {
                "metric": "total_acquisitions",
                "value": self.total_acquisitions,
            },
            {
                "metric": "sar_acquisitions",
                "value": self.sar_acquisitions,
            },
            {
                "metric": "optical_acquisitions",
                "value": self.optical_acquisitions,
            },
            {
                "metric": "total_duration_s",
                "value": self.total_duration_s,
            },
            {
                "metric": "total_data_volume_mb",
                "value": self.total_data_volume_mb,
            },
            {
                "metric": "objective_value",
                "value": self.objective_value,
            },
            {
                "metric": "average_selected_quality",
                "value": self.average_selected_quality,
            },
            {
                "metric": "average_selected_coverage",
                "value": self.average_selected_coverage,
            },
            {
                "metric": "selected_to_feasible_ratio",
                "value": self.selected_to_feasible_ratio,
            },
        ]

        for reason, count in sorted(
            self.unassigned_reason_counts.items()
        ):
            rows.append(
                {
                    "metric": f"unassigned_reason_{reason}",
                    "value": count,
                }
            )

        return rows


def analyze_schedule(
    *,
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    schedule: Schedule,
) -> ScheduleAnalysis:
    """Analizuje harmonogram i oblicza KPI oraz diagnostykę."""

    _validate_analysis_inputs(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        schedule=schedule,
    )

    opportunities_by_id = {
        opportunity.opportunity_id: opportunity
        for opportunity in opportunity_set.opportunities
    }

    feasible_by_request: dict[
        str,
        list[AcquisitionOpportunity],
    ] = defaultdict(list)

    for opportunity in opportunity_set.feasible_opportunities:
        feasible_by_request[opportunity.request_id].append(
            opportunity
        )

    entries_by_request: dict[
        str,
        list[ScheduleEntry],
    ] = defaultdict(list)

    entries_by_satellite: dict[
        str,
        list[ScheduleEntry],
    ] = defaultdict(list)

    for entry in schedule.active_entries:
        entries_by_request[entry.request_id].append(entry)
        entries_by_satellite[entry.satellite_id].append(entry)

    selected_opportunity_ids = {
        entry.opportunity_id
        for entry in schedule.active_entries
    }

    diagnostics: list[RequestDiagnostic] = []

    for request in request_set.active_requests:
        entries = entries_by_request.get(
            request.request_id,
            [],
        )

        candidates = feasible_by_request.get(
            request.request_id,
            [],
        )

        fulfillment_status = _determine_fulfillment_status(
            request,
            entries,
        )

        if (
            fulfillment_status
            == RequestFulfillmentStatus.FULLY_SATISFIED
        ):
            reasons: tuple[str, ...] = ()
        else:
            reasons = tuple(
                reason.value
                for reason in _diagnose_request(
                    request=request,
                    candidates=candidates,
                    schedule=schedule,
                    catalog=catalog,
                    entries_by_satellite=entries_by_satellite,
                    selected_opportunity_ids=(
                        selected_opportunity_ids
                    ),
                )
            )

        diagnostics.append(
            RequestDiagnostic(
                request_id=request.request_id,
                request_mode=request.request_mode.value,
                priority=request.priority,
                is_mandatory=request.is_mandatory,
                fulfillment_status=fulfillment_status.value,
                scheduled_entry_count=len(entries),
                scheduled_sensor_types=tuple(
                    sorted(
                        {
                            entry.sensor_type.value
                            for entry in entries
                        }
                    )
                ),
                feasible_opportunity_count=len(candidates),
                feasible_sar_count=sum(
                    candidate.sensor_type == SensorType.SAR
                    for candidate in candidates
                ),
                feasible_optical_count=sum(
                    candidate.sensor_type
                    == SensorType.OPTICAL
                    for candidate in candidates
                ),
                reason_codes=reasons,
            )
        )

    satellite_kpis = tuple(
        _build_satellite_kpi(
            catalog=catalog,
            schedule=schedule,
            satellite_id=satellite.satellite_id,
            entries=entries_by_satellite.get(
                satellite.satellite_id,
                [],
            ),
        )
        for satellite in sorted(
            catalog.satellites,
            key=lambda item: item.satellite_id,
        )
    )

    entry_kpis = tuple(
        _build_entry_kpi(
            entry,
            opportunities_by_id[entry.opportunity_id],
        )
        for entry in sorted(
            schedule.active_entries,
            key=lambda item: (
                item.start_utc,
                item.satellite_id,
                item.entry_id,
            ),
        )
    )

    fully_satisfied = sum(
        diagnostic.fulfillment_status
        == RequestFulfillmentStatus.FULLY_SATISFIED.value
        for diagnostic in diagnostics
    )

    partially_satisfied = sum(
        diagnostic.fulfillment_status
        == RequestFulfillmentStatus.PARTIALLY_SATISFIED.value
        for diagnostic in diagnostics
    )

    unassigned = sum(
        diagnostic.fulfillment_status
        == RequestFulfillmentStatus.UNASSIGNED.value
        for diagnostic in diagnostics
    )

    mandatory_diagnostics = [
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.is_mandatory
    ]

    mandatory_satisfied = sum(
        diagnostic.fulfillment_status
        == RequestFulfillmentStatus.FULLY_SATISFIED.value
        for diagnostic in mandatory_diagnostics
    )

    total_requests = len(diagnostics)
    mandatory_requests = len(mandatory_diagnostics)

    satisfaction_ratio = _safe_ratio(
        fully_satisfied,
        total_requests,
    )

    mandatory_satisfaction_ratio = _safe_ratio(
        mandatory_satisfied,
        mandatory_requests,
    )

    selected_opportunities = [
        opportunities_by_id[entry.opportunity_id]
        for entry in schedule.active_entries
    ]

    average_quality = _safe_mean(
        [
            opportunity.quality_score
            for opportunity in selected_opportunities
        ]
    )

    average_coverage = _safe_mean(
        [
            opportunity.coverage_ratio
            for opportunity in selected_opportunities
        ]
    )

    reason_counts = Counter(
        reason
        for diagnostic in diagnostics
        for reason in diagnostic.reason_codes
    )

    return ScheduleAnalysis(
        schedule_id=schedule.schedule_id,
        schedule_status=schedule.status.value,
        total_active_requests=total_requests,
        requests_with_entries=len(
            {
                entry.request_id
                for entry in schedule.active_entries
            }
        ),
        fully_satisfied_requests=fully_satisfied,
        partially_satisfied_requests=partially_satisfied,
        unassigned_requests=unassigned,
        mandatory_requests=mandatory_requests,
        mandatory_satisfied_requests=mandatory_satisfied,
        satisfaction_ratio=round(
            satisfaction_ratio,
            6,
        ),
        mandatory_satisfaction_ratio=round(
            mandatory_satisfaction_ratio,
            6,
        ),
        total_acquisitions=schedule.total_acquisitions,
        sar_acquisitions=sum(
            entry.sensor_type == SensorType.SAR
            for entry in schedule.active_entries
        ),
        optical_acquisitions=sum(
            entry.sensor_type == SensorType.OPTICAL
            for entry in schedule.active_entries
        ),
        total_duration_s=round(
            schedule.total_duration_s,
            6,
        ),
        total_data_volume_mb=round(
            schedule.total_data_volume_mb,
            6,
        ),
        objective_value=round(
            schedule.objective_value or 0.0,
            6,
        ),
        average_selected_quality=round(
            average_quality,
            6,
        ),
        average_selected_coverage=round(
            average_coverage,
            6,
        ),
        selected_to_feasible_ratio=round(
            _safe_ratio(
                schedule.total_acquisitions,
                len(
                    opportunity_set.feasible_opportunities
                ),
            ),
            6,
        ),
        request_diagnostics=tuple(diagnostics),
        satellite_kpis=satellite_kpis,
        entry_kpis=entry_kpis,
        unassigned_reason_counts=dict(
            sorted(reason_counts.items())
        ),
    )


def export_schedule_analysis(
    analysis: ScheduleAnalysis,
    output_directory: str | Path,
    *,
    prefix: str = "greedy",
) -> dict[str, Path]:
    """Eksportuje raport KPI do czterech plików CSV."""

    directory = Path(output_directory)

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths = {
        "kpi": directory / f"{prefix}_kpi.csv",
        "satellites": directory / f"{prefix}_satellites.csv",
        "requests": directory / f"{prefix}_requests.csv",
        "entries": directory / f"{prefix}_entries.csv",
    }

    _write_csv(
        paths["kpi"],
        fieldnames=["metric", "value"],
        rows=analysis.kpi_rows(),
    )

    _write_csv(
        paths["satellites"],
        fieldnames=[
            "satellite_id",
            "sensor_type",
            "scheduled_acquisitions",
            "acquisition_limit",
            "acquisition_utilization_ratio",
            "imaging_time_s",
            "imaging_time_limit_s",
            "imaging_utilization_ratio",
            "generated_data_mb",
            "initial_memory_usage_mb",
            "planning_memory_limit_mb",
            "final_memory_usage_mb",
            "memory_utilization_ratio",
        ],
        rows=[
            {
                "satellite_id": item.satellite_id,
                "sensor_type": item.sensor_type,
                "scheduled_acquisitions": (
                    item.scheduled_acquisitions
                ),
                "acquisition_limit": item.acquisition_limit,
                "acquisition_utilization_ratio": (
                    item.acquisition_utilization_ratio
                ),
                "imaging_time_s": item.imaging_time_s,
                "imaging_time_limit_s": (
                    item.imaging_time_limit_s
                ),
                "imaging_utilization_ratio": (
                    item.imaging_utilization_ratio
                ),
                "generated_data_mb": item.generated_data_mb,
                "initial_memory_usage_mb": (
                    item.initial_memory_usage_mb
                ),
                "planning_memory_limit_mb": (
                    item.planning_memory_limit_mb
                ),
                "final_memory_usage_mb": (
                    item.final_memory_usage_mb
                ),
                "memory_utilization_ratio": (
                    item.memory_utilization_ratio
                ),
            }
            for item in analysis.satellite_kpis
        ],
    )

    _write_csv(
        paths["requests"],
        fieldnames=[
            "request_id",
            "request_mode",
            "priority",
            "is_mandatory",
            "fulfillment_status",
            "scheduled_entry_count",
            "scheduled_sensor_types",
            "feasible_opportunity_count",
            "feasible_sar_count",
            "feasible_optical_count",
            "reason_codes",
        ],
        rows=[
            {
                "request_id": item.request_id,
                "request_mode": item.request_mode,
                "priority": item.priority,
                "is_mandatory": item.is_mandatory,
                "fulfillment_status": (
                    item.fulfillment_status
                ),
                "scheduled_entry_count": (
                    item.scheduled_entry_count
                ),
                "scheduled_sensor_types": "|".join(
                    item.scheduled_sensor_types
                ),
                "feasible_opportunity_count": (
                    item.feasible_opportunity_count
                ),
                "feasible_sar_count": (
                    item.feasible_sar_count
                ),
                "feasible_optical_count": (
                    item.feasible_optical_count
                ),
                "reason_codes": "|".join(
                    item.reason_codes
                ),
            }
            for item in analysis.request_diagnostics
        ],
    )

    _write_csv(
        paths["entries"],
        fieldnames=[
            "entry_id",
            "opportunity_id",
            "request_id",
            "satellite_id",
            "sensor_type",
            "mode_id",
            "start_utc",
            "end_utc",
            "duration_s",
            "estimated_data_volume_mb",
            "objective_contribution",
            "quality_score",
            "coverage_ratio",
            "cloud_cover",
            "incidence_angle_deg",
            "off_nadir_angle_deg",
        ],
        rows=[
            {
                "entry_id": item.entry_id,
                "opportunity_id": item.opportunity_id,
                "request_id": item.request_id,
                "satellite_id": item.satellite_id,
                "sensor_type": item.sensor_type,
                "mode_id": item.mode_id,
                "start_utc": item.start_utc,
                "end_utc": item.end_utc,
                "duration_s": item.duration_s,
                "estimated_data_volume_mb": (
                    item.estimated_data_volume_mb
                ),
                "objective_contribution": (
                    item.objective_contribution
                ),
                "quality_score": item.quality_score,
                "coverage_ratio": item.coverage_ratio,
                "cloud_cover": item.cloud_cover,
                "incidence_angle_deg": (
                    item.incidence_angle_deg
                ),
                "off_nadir_angle_deg": (
                    item.off_nadir_angle_deg
                ),
            }
            for item in analysis.entry_kpis
        ],
    )

    return paths


def _validate_analysis_inputs(
    *,
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    schedule: Schedule,
) -> None:
    opportunity_set.validate_against(
        catalog,
        request_set,
    )

    if (
        schedule.horizon_start_utc
        != request_set.horizon_start_utc
        or schedule.horizon_end_utc
        != request_set.horizon_end_utc
    ):
        raise ValueError(
            "Horyzont harmonogramu jest niezgodny "
            "ze zbiorem zleceń"
        )

    request_ids = {
        request.request_id
        for request in request_set.requests
    }

    opportunity_ids = {
        opportunity.opportunity_id
        for opportunity in opportunity_set.opportunities
    }

    satellite_ids = {
        satellite.satellite_id
        for satellite in catalog.satellites
    }

    for entry in schedule.active_entries:
        if entry.request_id not in request_ids:
            raise ValueError(
                f"Wpis {entry.entry_id} odwołuje się "
                "do nieistniejącego zlecenia"
            )

        if entry.opportunity_id not in opportunity_ids:
            raise ValueError(
                f"Wpis {entry.entry_id} odwołuje się "
                "do nieistniejącej okazji"
            )

        if entry.satellite_id not in satellite_ids:
            raise ValueError(
                f"Wpis {entry.entry_id} odwołuje się "
                "do nieistniejącego satelity"
            )


def _determine_fulfillment_status(
    request: ObservationRequest,
    entries: list[ScheduleEntry],
) -> RequestFulfillmentStatus:
    if not entries:
        return RequestFulfillmentStatus.UNASSIGNED

    if request.request_mode == RequestMode.DUAL_REQUIRED:
        sensor_types = {
            entry.sensor_type
            for entry in entries
        }

        if (
            len(entries) >= 2
            and sensor_types
            == {
                SensorType.SAR,
                SensorType.OPTICAL,
            }
        ):
            return RequestFulfillmentStatus.FULLY_SATISFIED

        return RequestFulfillmentStatus.PARTIALLY_SATISFIED

    return RequestFulfillmentStatus.FULLY_SATISFIED


def _diagnose_request(
    *,
    request: ObservationRequest,
    candidates: list[AcquisitionOpportunity],
    schedule: Schedule,
    catalog: SystemCatalog,
    entries_by_satellite: dict[str, list[ScheduleEntry]],
    selected_opportunity_ids: set[str],
) -> list[UnassignedReasonCode]:
    remaining_candidates = [
        candidate
        for candidate in candidates
        if candidate.opportunity_id
        not in selected_opportunity_ids
    ]

    if not remaining_candidates:
        if not candidates:
            return [
                UnassignedReasonCode.NO_FEASIBLE_OPPORTUNITY
            ]

        return [
            UnassignedReasonCode.UNKNOWN
        ]

    if request.request_mode == RequestMode.DUAL_REQUIRED:
        sar_candidates = [
            candidate
            for candidate in remaining_candidates
            if candidate.sensor_type == SensorType.SAR
        ]

        optical_candidates = [
            candidate
            for candidate in remaining_candidates
            if candidate.sensor_type == SensorType.OPTICAL
        ]

        missing_reasons: list[UnassignedReasonCode] = []

        if not sar_candidates:
            missing_reasons.append(
                UnassignedReasonCode.MISSING_SAR_OPPORTUNITY
            )

        if not optical_candidates:
            missing_reasons.append(
                UnassignedReasonCode.MISSING_OPTICAL_OPPORTUNITY
            )

        if missing_reasons:
            return missing_reasons

        combined_reasons: set[UnassignedReasonCode] = set()

        for sar_candidate in sar_candidates:
            sar_reasons = _candidate_block_reasons(
                candidate=sar_candidate,
                schedule=schedule,
                catalog=catalog,
                entries_by_satellite=entries_by_satellite,
            )

            for optical_candidate in optical_candidates:
                optical_reasons = _candidate_block_reasons(
                    candidate=optical_candidate,
                    schedule=schedule,
                    catalog=catalog,
                    entries_by_satellite=entries_by_satellite,
                )

                if not sar_reasons and not optical_reasons:
                    return [
                        UnassignedReasonCode.GREEDY_ORDERING
                    ]

                combined_reasons.update(sar_reasons)
                combined_reasons.update(optical_reasons)

        return _sorted_reasons(combined_reasons)

    combined_reasons: set[UnassignedReasonCode] = set()

    for candidate in remaining_candidates:
        reasons = _candidate_block_reasons(
            candidate=candidate,
            schedule=schedule,
            catalog=catalog,
            entries_by_satellite=entries_by_satellite,
        )

        if not reasons:
            return [
                UnassignedReasonCode.GREEDY_ORDERING
            ]

        combined_reasons.update(reasons)

    return _sorted_reasons(combined_reasons)


def _candidate_block_reasons(
    *,
    candidate: AcquisitionOpportunity,
    schedule: Schedule,
    catalog: SystemCatalog,
    entries_by_satellite: dict[str, list[ScheduleEntry]],
) -> set[UnassignedReasonCode]:
    satellite = catalog.get_satellite(
        candidate.satellite_id
    )

    sensor = catalog.get_sensor(
        satellite.sensor_id
    )

    reasons: set[UnassignedReasonCode] = set()

    if not satellite.is_available_for_planning:
        reasons.add(
            UnassignedReasonCode.SATELLITE_INACTIVE
        )

    satellite_entries = entries_by_satellite.get(
        satellite.satellite_id,
        [],
    )

    if (
        len(satellite_entries) + 1
        > satellite.max_acquisitions_per_day
    ):
        reasons.add(
            UnassignedReasonCode.ACQUISITION_LIMIT
        )

    used_imaging_time_s = sum(
        entry.duration_s
        for entry in satellite_entries
    )

    if (
        used_imaging_time_s
        + candidate.duration_s
        > satellite.max_imaging_time_per_day_s
        + 1e-9
    ):
        reasons.add(
            UnassignedReasonCode.IMAGING_TIME_LIMIT
        )

    used_data_mb = sum(
        entry.estimated_data_volume_mb
        for entry in satellite_entries
    )

    planning_memory_limit_mb = (
        satellite.memory_capacity_mb
        * (1.0 - schedule.memory_reserve_ratio)
    )

    projected_memory_usage_mb = (
        satellite.initial_memory_usage_mb
        + used_data_mb
        + candidate.estimated_data_volume_mb
    )

    if (
        projected_memory_usage_mb
        > planning_memory_limit_mb
        + 1e-9
    ):
        reasons.add(
            UnassignedReasonCode.MEMORY_LIMIT
        )

    transition_time_s = max(
        satellite.minimum_transition_time_s,
        sensor.warmup_time_s
        + sensor.cooldown_time_s,
    )

    for entry in satellite_entries:
        separated_before = (
            candidate.end_utc
            + _seconds(transition_time_s)
            <= entry.start_utc
        )

        separated_after = (
            entry.end_utc
            + _seconds(transition_time_s)
            <= candidate.start_utc
        )

        if not separated_before and not separated_after:
            reasons.add(
                UnassignedReasonCode.TRANSITION_CONFLICT
            )
            break

    return reasons


def _build_satellite_kpi(
    *,
    catalog: SystemCatalog,
    schedule: Schedule,
    satellite_id: str,
    entries: list[ScheduleEntry],
) -> SatelliteKPI:
    satellite = catalog.get_satellite(
        satellite_id
    )

    sensor = catalog.get_sensor(
        satellite.sensor_id
    )

    acquisition_count = len(entries)

    imaging_time_s = sum(
        entry.duration_s
        for entry in entries
    )

    generated_data_mb = sum(
        entry.estimated_data_volume_mb
        for entry in entries
    )

    planning_memory_limit_mb = (
        satellite.memory_capacity_mb
        * (1.0 - schedule.memory_reserve_ratio)
    )

    final_memory_usage_mb = (
        satellite.initial_memory_usage_mb
        + generated_data_mb
    )

    return SatelliteKPI(
        satellite_id=satellite.satellite_id,
        sensor_type=sensor.sensor_type.value,
        scheduled_acquisitions=acquisition_count,
        imaging_time_s=round(
            imaging_time_s,
            6,
        ),
        imaging_time_limit_s=(
            satellite.max_imaging_time_per_day_s
        ),
        imaging_utilization_ratio=round(
            _safe_ratio(
                imaging_time_s,
                satellite.max_imaging_time_per_day_s,
            ),
            6,
        ),
        generated_data_mb=round(
            generated_data_mb,
            6,
        ),
        initial_memory_usage_mb=(
            satellite.initial_memory_usage_mb
        ),
        planning_memory_limit_mb=round(
            planning_memory_limit_mb,
            6,
        ),
        final_memory_usage_mb=round(
            final_memory_usage_mb,
            6,
        ),
        memory_utilization_ratio=round(
            _safe_ratio(
                final_memory_usage_mb,
                planning_memory_limit_mb,
            ),
            6,
        ),
        acquisition_limit=(
            satellite.max_acquisitions_per_day
        ),
        acquisition_utilization_ratio=round(
            _safe_ratio(
                acquisition_count,
                satellite.max_acquisitions_per_day,
            ),
            6,
        ),
    )


def _build_entry_kpi(
    entry: ScheduleEntry,
    opportunity: AcquisitionOpportunity,
) -> EntryKPI:
    return EntryKPI(
        entry_id=entry.entry_id,
        opportunity_id=entry.opportunity_id,
        request_id=entry.request_id,
        satellite_id=entry.satellite_id,
        sensor_type=entry.sensor_type.value,
        mode_id=entry.mode_id,
        start_utc=entry.start_utc.isoformat(),
        end_utc=entry.end_utc.isoformat(),
        duration_s=round(
            entry.duration_s,
            6,
        ),
        estimated_data_volume_mb=round(
            entry.estimated_data_volume_mb,
            6,
        ),
        objective_contribution=round(
            entry.objective_contribution,
            6,
        ),
        quality_score=round(
            opportunity.quality_score,
            6,
        ),
        coverage_ratio=round(
            opportunity.coverage_ratio,
            6,
        ),
        cloud_cover=opportunity.cloud_cover,
        incidence_angle_deg=(
            opportunity.incidence_angle_deg
        ),
        off_nadir_angle_deg=(
            opportunity.off_nadir_angle_deg
        ),
    )


def _write_csv(
    path: Path,
    *,
    fieldnames: list[str],
    rows: list[dict[str, object]],
) -> None:
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def _safe_ratio(
    numerator: float,
    denominator: float,
) -> float:
    if denominator <= 0.0:
        return 0.0

    return numerator / denominator


def _safe_mean(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    return mean(values)


def _sorted_reasons(
    reasons: set[UnassignedReasonCode],
) -> list[UnassignedReasonCode]:
    if not reasons:
        return [
            UnassignedReasonCode.UNKNOWN
        ]

    return sorted(
        reasons,
        key=lambda reason: reason.value,
    )


def _seconds(value: float):
    from datetime import timedelta

    return timedelta(seconds=value)