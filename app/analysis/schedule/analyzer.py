from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

from app.models.catalog import SystemCatalog
from app.models.enums import RequestMode, SensorType
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.models.schedule import Schedule, ScheduleEntry

from app.analysis.schedule.models import (
    EntryKPI,
    RequestDiagnostic,
    RequestFulfillmentStatus,
    SatelliteKPI,
    ScheduleAnalysis,
    UnassignedReasonCode,
)

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
