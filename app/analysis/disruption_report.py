from __future__ import annotations

import csv
from pathlib import Path

from app.services.disruption_service import DisruptionReplanningResult


def build_disruption_summary_rows(
    result: DisruptionReplanningResult,
) -> list[dict[str, object]]:
    """Buduje główne KPI reakcji na zakłócenie."""

    application = result.application_result
    replanning = result.replanning_result

    return [
        {"metric": "plan_id", "value": application.plan.plan_id},
        {
            "metric": "occurred_at_utc",
            "value": application.plan.occurred_at_utc.isoformat(),
        },
        {
            "metric": "frozen_until_utc",
            "value": replanning.frozen_until_utc.isoformat(),
        },
        {
            "metric": "outage_satellites",
            "value": ",".join(
                outage.satellite_id
                for outage in application.plan.satellite_outages
            ),
        },
        {
            "metric": "outage_invalidated_opportunities",
            "value": len(application.outage_invalidated_opportunity_ids),
        },
        {
            "metric": "weather_invalidated_opportunities",
            "value": len(application.weather_invalidated_opportunity_ids),
        },
        {
            "metric": "added_urgent_requests",
            "value": len(application.added_request_ids),
        },
        {
            "metric": "added_urgent_opportunities",
            "value": len(application.added_opportunity_ids),
        },
        {
            "metric": "invalidated_previous_selections",
            "value": len(result.invalidated_previous_selection_ids),
        },
        {
            "metric": "unchanged_future_acquisitions",
            "value": len(result.unchanged_opportunity_ids),
        },
        {
            "metric": "added_future_acquisitions",
            "value": len(result.added_opportunity_ids),
        },
        {
            "metric": "removed_future_acquisitions",
            "value": len(result.removed_opportunity_ids),
        },
        {
            "metric": "previous_objective_value",
            "value": round(result.previous_objective_value, 6),
        },
        {
            "metric": "new_objective_value",
            "value": round(result.new_objective_value, 6),
        },
        {
            "metric": "objective_delta",
            "value": round(result.objective_delta, 6),
        },
        {
            "metric": "fully_satisfied_requests",
            "value": result.analysis.fully_satisfied_requests,
        },
        {
            "metric": "unassigned_requests",
            "value": result.analysis.unassigned_requests,
        },
        {
            "metric": "mandatory_satisfied_requests",
            "value": result.analysis.mandatory_satisfied_requests,
        },
    ]


def build_schedule_change_rows(
    result: DisruptionReplanningResult,
) -> list[dict[str, object]]:
    """Buduje listę dodanych i usuniętych akwizycji."""

    previous_by_id = {
        entry.opportunity_id: entry
        for entry in result.previous_schedule.active_entries
    }
    new_by_id = {
        entry.opportunity_id: entry
        for entry in result.schedule.active_entries
    }

    rows: list[dict[str, object]] = []

    for change_type, opportunity_ids, source in (
        ("ADDED", result.added_opportunity_ids, new_by_id),
        ("REMOVED", result.removed_opportunity_ids, previous_by_id),
    ):
        for opportunity_id in opportunity_ids:
            entry = source[opportunity_id]
            rows.append(
                {
                    "change_type": change_type,
                    "opportunity_id": opportunity_id,
                    "request_id": entry.request_id,
                    "satellite_id": entry.satellite_id,
                    "sensor_type": entry.sensor_type.value,
                    "start_utc": entry.start_utc.isoformat(),
                    "end_utc": entry.end_utc.isoformat(),
                    "objective_contribution": (
                        entry.objective_contribution
                    ),
                }
            )

    return rows


def export_disruption_report(
    result: DisruptionReplanningResult,
    output_directory: str | Path,
    *,
    prefix: str = "disruption",
) -> dict[str, Path]:
    """Eksportuje podsumowanie zdarzeń i zmian harmonogramu."""

    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)

    paths = {
        "summary": directory / f"{prefix}_summary.csv",
        "changes": directory / f"{prefix}_changes.csv",
    }

    _write_csv(
        paths["summary"],
        fieldnames=["metric", "value"],
        rows=build_disruption_summary_rows(result),
    )
    _write_csv(
        paths["changes"],
        fieldnames=[
            "change_type",
            "opportunity_id",
            "request_id",
            "satellite_id",
            "sensor_type",
            "start_utc",
            "end_utc",
            "objective_contribution",
        ],
        rows=build_schedule_change_rows(result),
    )

    return paths


def _write_csv(
    path: Path,
    *,
    fieldnames: list[str],
    rows: list[dict[str, object]],
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
