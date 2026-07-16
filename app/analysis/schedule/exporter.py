from __future__ import annotations

import csv
from pathlib import Path

from app.analysis.schedule.models import ScheduleAnalysis

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
