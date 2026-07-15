from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from app.models.enums import (
    RequestMode,
    SensorType,
)
from app.services.planning_service import (
    PlanningResult,
)


SCHEDULE_ENTRY_COLUMNS = [
    "entry_id",
    "opportunity_id",
    "request_id",
    "satellite_id",
    "sensor_type",
    "mode_id",
    "status",
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
]


REQUEST_STATUS_COLUMNS = [
    "request_id",
    "name",
    "request_mode",
    "priority",
    "is_mandatory",
    "fulfillment_status",
    "scheduled_entry_count",
    "scheduled_sensor_types",
    "feasible_opportunity_count",
    "earliest_start_utc",
    "latest_end_utc",
    "reason_code",
]


SATELLITE_USAGE_COLUMNS = [
    "satellite_id",
    "name",
    "sensor_type",
    "status",
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
]


def build_schedule_entries_dataframe(
    result: PlanningResult,
) -> pd.DataFrame:
    """Buduje tabelę aktywnych wpisów harmonogramu."""

    opportunities_by_id = {
        opportunity.opportunity_id: opportunity
        for opportunity
        in result.scenario.opportunity_set.opportunities
    }

    rows: list[dict[str, Any]] = []

    for entry in result.schedule.active_entries:
        try:
            opportunity = opportunities_by_id[
                entry.opportunity_id
            ]
        except KeyError as error:
            raise KeyError(
                "Harmonogram odwołuje się do nieznanej okazji: "
                f"{entry.opportunity_id}"
            ) from error

        rows.append(
            {
                "entry_id": entry.entry_id,
                "opportunity_id": entry.opportunity_id,
                "request_id": entry.request_id,
                "satellite_id": entry.satellite_id,
                "sensor_type": _enum_value(
                    entry.sensor_type
                ),
                "mode_id": entry.mode_id,
                "status": _enum_value(
                    entry.status
                ),
                "start_utc": entry.start_utc,
                "end_utc": entry.end_utc,
                "duration_s": round(
                    entry.duration_s,
                    6,
                ),
                "estimated_data_volume_mb": round(
                    entry.estimated_data_volume_mb,
                    6,
                ),
                "objective_contribution": round(
                    entry.objective_contribution,
                    6,
                ),
                "quality_score": round(
                    opportunity.quality_score,
                    6,
                ),
                "coverage_ratio": round(
                    opportunity.coverage_ratio,
                    6,
                ),
                "cloud_cover": opportunity.cloud_cover,
                "incidence_angle_deg": (
                    opportunity.incidence_angle_deg
                ),
                "off_nadir_angle_deg": (
                    opportunity.off_nadir_angle_deg
                ),
            }
        )

    dataframe = pd.DataFrame(
        rows,
        columns=SCHEDULE_ENTRY_COLUMNS,
    )

    if dataframe.empty:
        return dataframe

    return dataframe.sort_values(
        by=[
            "start_utc",
            "satellite_id",
            "entry_id",
        ],
        kind="stable",
        ignore_index=True,
    )


def build_request_status_dataframe(
    result: PlanningResult,
) -> pd.DataFrame:
    """Buduje tabelę realizacji wszystkich aktywnych zleceń."""

    entries_by_request: dict[
        str,
        list[Any],
    ] = defaultdict(list)

    for entry in result.schedule.active_entries:
        entries_by_request[
            entry.request_id
        ].append(entry)

    feasible_counts: dict[str, int] = defaultdict(int)

    for opportunity in (
        result
        .scenario
        .opportunity_set
        .feasible_opportunities
    ):
        feasible_counts[
            opportunity.request_id
        ] += 1

    rows: list[dict[str, Any]] = []

    for request in sorted(
        result.scenario.request_set.active_requests,
        key=lambda item: (
            -int(item.is_mandatory),
            -item.priority,
            item.request_id,
        ),
    ):
        entries = entries_by_request.get(
            request.request_id,
            [],
        )

        scheduled_sensor_types = sorted(
            {
                _enum_value(
                    entry.sensor_type
                )
                for entry in entries
            }
        )

        fulfillment_status = (
            _request_fulfillment_status(
                request_mode=request.request_mode,
                scheduled_sensor_types=set(
                    scheduled_sensor_types
                ),
                scheduled_entry_count=len(entries),
            )
        )

        reason_code = _request_reason_code(
            fulfillment_status=fulfillment_status,
            feasible_opportunity_count=(
                feasible_counts.get(
                    request.request_id,
                    0,
                )
            ),
        )

        rows.append(
            {
                "request_id": request.request_id,
                "name": request.name,
                "request_mode": _enum_value(
                    request.request_mode
                ),
                "priority": request.priority,
                "is_mandatory": request.is_mandatory,
                "fulfillment_status": (
                    fulfillment_status
                ),
                "scheduled_entry_count": len(
                    entries
                ),
                "scheduled_sensor_types": "|".join(
                    scheduled_sensor_types
                ),
                "feasible_opportunity_count": (
                    feasible_counts.get(
                        request.request_id,
                        0,
                    )
                ),
                "earliest_start_utc": (
                    request.earliest_start_utc
                ),
                "latest_end_utc": (
                    request.latest_end_utc
                ),
                "reason_code": reason_code,
            }
        )

    return pd.DataFrame(
        rows,
        columns=REQUEST_STATUS_COLUMNS,
    )


def build_unfulfilled_requests_dataframe(
    result: PlanningResult,
) -> pd.DataFrame:
    """Zwraca zlecenia niezrealizowane lub częściowe."""

    dataframe = build_request_status_dataframe(
        result
    )

    if dataframe.empty:
        return dataframe

    return dataframe.loc[
        dataframe["fulfillment_status"]
        != "FULLY_SATISFIED"
    ].reset_index(
        drop=True
    )


def build_satellite_usage_dataframe(
    result: PlanningResult,
) -> pd.DataFrame:
    """Buduje zestawienie wykorzystania zasobów satelitów."""

    entries_by_satellite: dict[
        str,
        list[Any],
    ] = defaultdict(list)

    for entry in result.schedule.active_entries:
        entries_by_satellite[
            entry.satellite_id
        ].append(entry)

    rows: list[dict[str, Any]] = []

    for satellite in sorted(
        result.scenario.catalog.satellites,
        key=lambda item: item.satellite_id,
    ):
        entries = entries_by_satellite.get(
            satellite.satellite_id,
            [],
        )

        sensor = (
            result
            .scenario
            .catalog
            .get_sensor(
                satellite.sensor_id
            )
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
            * (
                1.0
                - result
                .schedule
                .memory_reserve_ratio
            )
        )

        final_memory_usage_mb = (
            satellite.initial_memory_usage_mb
            + generated_data_mb
        )

        acquisition_utilization_ratio = (
            acquisition_count
            / satellite.max_acquisitions_per_day
            if satellite.max_acquisitions_per_day > 0
            else 0.0
        )

        imaging_utilization_ratio = (
            imaging_time_s
            / satellite.max_imaging_time_per_day_s
            if satellite.max_imaging_time_per_day_s > 0.0
            else 0.0
        )

        memory_utilization_ratio = (
            final_memory_usage_mb
            / planning_memory_limit_mb
            if planning_memory_limit_mb > 0.0
            else None
        )

        rows.append(
            {
                "satellite_id": satellite.satellite_id,
                "name": getattr(
                    satellite,
                    "name",
                    satellite.satellite_id,
                ),
                "sensor_type": _enum_value(
                    sensor.sensor_type
                ),
                "status": _enum_value(
                    satellite.status
                ),
                "scheduled_acquisitions": (
                    acquisition_count
                ),
                "acquisition_limit": (
                    satellite
                    .max_acquisitions_per_day
                ),
                "acquisition_utilization_ratio": round(
                    acquisition_utilization_ratio,
                    6,
                ),
                "imaging_time_s": round(
                    imaging_time_s,
                    6,
                ),
                "imaging_time_limit_s": (
                    satellite
                    .max_imaging_time_per_day_s
                ),
                "imaging_utilization_ratio": round(
                    imaging_utilization_ratio,
                    6,
                ),
                "generated_data_mb": round(
                    generated_data_mb,
                    6,
                ),
                "initial_memory_usage_mb": (
                    satellite.initial_memory_usage_mb
                ),
                "planning_memory_limit_mb": round(
                    planning_memory_limit_mb,
                    6,
                ),
                "final_memory_usage_mb": round(
                    final_memory_usage_mb,
                    6,
                ),
                "memory_utilization_ratio": (
                    None
                    if memory_utilization_ratio is None
                    else round(
                        memory_utilization_ratio,
                        6,
                    )
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=SATELLITE_USAGE_COLUMNS,
    )


def _request_fulfillment_status(
    *,
    request_mode: RequestMode,
    scheduled_sensor_types: set[str],
    scheduled_entry_count: int,
) -> str:
    if request_mode == RequestMode.DUAL_REQUIRED:
        required_sensor_types = {
            SensorType.SAR.value,
            SensorType.OPTICAL.value,
        }

        if (
            scheduled_sensor_types
            == required_sensor_types
            and scheduled_entry_count >= 2
        ):
            return "FULLY_SATISFIED"

        if scheduled_entry_count > 0:
            return "PARTIALLY_SATISFIED"

        return "UNASSIGNED"

    if scheduled_entry_count > 0:
        return "FULLY_SATISFIED"

    return "UNASSIGNED"


def _request_reason_code(
    *,
    fulfillment_status: str,
    feasible_opportunity_count: int,
) -> str:
    if fulfillment_status == "FULLY_SATISFIED":
        return ""

    if fulfillment_status == "PARTIALLY_SATISFIED":
        return "MISSING_REQUIRED_SENSOR"

    if feasible_opportunity_count == 0:
        return "NO_FEASIBLE_OPPORTUNITIES"

    return "NOT_SELECTED"


def _enum_value(
    value: Any,
) -> str:
    enum_value = getattr(
        value,
        "value",
        value,
    )

    return str(
        enum_value
    )