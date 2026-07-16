from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

from app.analysis.disruption_report import build_schedule_change_rows
from app.analysis.experimental_validation import (
    ExperimentPairRecord,
    ExperimentalValidationResult,
)
from app.models.schedule import ScheduleEntry
from app.services.disruption_service import DisruptionReplanningResult
from app.services.replanning_service import ReplanningResult


REPLANNING_CHANGE_COLUMNS = [
    "change_type",
    "opportunity_id",
    "request_id",
    "satellite_id",
    "sensor_type",
    "start_utc",
    "end_utc",
    "status",
    "objective_contribution",
]

DISRUPTION_EVENT_COLUMNS = [
    "event_type",
    "object_id",
    "effective_at_utc",
    "value",
    "reason",
]

EXPERIMENT_SUMMARY_COLUMNS = [
    "profile_id",
    "profile_name",
    "algorithm",
    "run_count",
    "objective_mean",
    "objective_std",
    "objective_min",
    "objective_max",
    "satisfaction_ratio_mean",
    "satisfaction_ratio_std",
    "mandatory_satisfaction_ratio_mean",
    "fully_satisfied_requests_mean",
    "unassigned_requests_mean",
    "runtime_mean_s",
    "runtime_std_s",
]

EXPERIMENT_PAIR_COLUMNS = [
    "profile_id",
    "repetition",
    "random_seed",
    "resource_ratio",
    "opportunity_dropout_ratio",
    "dropped_opportunity_count",
    "greedy_objective_value",
    "cp_sat_objective_value",
    "objective_difference",
    "objective_improvement_pct",
    "greedy_fully_satisfied_requests",
    "cp_sat_fully_satisfied_requests",
    "fully_satisfied_difference",
    "greedy_mandatory_satisfied_requests",
    "cp_sat_mandatory_satisfied_requests",
    "mandatory_satisfied_difference",
    "greedy_runtime_s",
    "cp_sat_runtime_s",
    "runtime_ratio",
    "cp_sat_solver_status",
]


@dataclass(frozen=True)
class ReplanningMetrics:
    previous_objective_value: float
    new_objective_value: float
    objective_delta: float
    executed_count: int
    frozen_count: int
    fixed_count: int
    unchanged_count: int
    added_count: int
    removed_count: int
    total_acquisitions: int
    fully_satisfied_requests: int
    total_active_requests: int
    solver_status: str
    schedule_status: str


@dataclass(frozen=True)
class DisruptionMetrics:
    previous_objective_value: float
    new_objective_value: float
    objective_delta: float
    outage_invalidated_count: int
    weather_invalidated_count: int
    invalidated_previous_selection_count: int
    added_urgent_request_count: int
    unchanged_count: int
    added_count: int
    removed_count: int
    fully_satisfied_requests: int
    total_active_requests: int
    mandatory_satisfied_requests: int
    mandatory_requests: int
    solver_status: str
    schedule_status: str


def build_replanning_metrics(result: ReplanningResult) -> ReplanningMetrics:
    previous_objective = float(
        result.previous_schedule.objective_value or 0.0
    )
    new_objective = float(result.schedule.objective_value or 0.0)

    return ReplanningMetrics(
        previous_objective_value=previous_objective,
        new_objective_value=new_objective,
        objective_delta=new_objective - previous_objective,
        executed_count=result.executed_count,
        frozen_count=result.frozen_count,
        fixed_count=result.fixed_count,
        unchanged_count=len(
            result.unchanged_replannable_opportunity_ids
        ),
        added_count=len(result.added_opportunity_ids),
        removed_count=len(result.removed_opportunity_ids),
        total_acquisitions=result.schedule.total_acquisitions,
        fully_satisfied_requests=(
            result.analysis.fully_satisfied_requests
        ),
        total_active_requests=result.analysis.total_active_requests,
        solver_status=result.solver_status,
        schedule_status=result.schedule.status.value,
    )


def build_replanning_changes_dataframe(
    result: ReplanningResult,
    *,
    include_unchanged: bool = True,
) -> pd.DataFrame:
    previous_by_id = {
        entry.opportunity_id: entry
        for entry in result.previous_schedule.active_entries
    }
    new_by_id = {
        entry.opportunity_id: entry
        for entry in result.schedule.active_entries
    }

    groups: list[tuple[str, Iterable[str], dict[str, ScheduleEntry]]] = [
        ("ADDED", result.added_opportunity_ids, new_by_id),
        ("REMOVED", result.removed_opportunity_ids, previous_by_id),
    ]

    if include_unchanged:
        groups.insert(
            0,
            (
                "UNCHANGED",
                result.unchanged_replannable_opportunity_ids,
                new_by_id,
            ),
        )

    rows: list[dict[str, object]] = []

    for change_type, opportunity_ids, source in groups:
        for opportunity_id in opportunity_ids:
            entry = source[opportunity_id]
            rows.append(
                {
                    "change_type": change_type,
                    "opportunity_id": entry.opportunity_id,
                    "request_id": entry.request_id,
                    "satellite_id": entry.satellite_id,
                    "sensor_type": entry.sensor_type.value,
                    "start_utc": entry.start_utc,
                    "end_utc": entry.end_utc,
                    "status": entry.status.value,
                    "objective_contribution": (
                        entry.objective_contribution
                    ),
                }
            )

    return pd.DataFrame(rows, columns=REPLANNING_CHANGE_COLUMNS)


def build_disruption_metrics(
    result: DisruptionReplanningResult,
) -> DisruptionMetrics:
    application = result.application_result

    return DisruptionMetrics(
        previous_objective_value=result.previous_objective_value,
        new_objective_value=result.new_objective_value,
        objective_delta=result.objective_delta,
        outage_invalidated_count=len(
            application.outage_invalidated_opportunity_ids
        ),
        weather_invalidated_count=len(
            application.weather_invalidated_opportunity_ids
        ),
        invalidated_previous_selection_count=len(
            result.invalidated_previous_selection_ids
        ),
        added_urgent_request_count=len(application.added_request_ids),
        unchanged_count=len(result.unchanged_opportunity_ids),
        added_count=len(result.added_opportunity_ids),
        removed_count=len(result.removed_opportunity_ids),
        fully_satisfied_requests=(
            result.analysis.fully_satisfied_requests
        ),
        total_active_requests=result.analysis.total_active_requests,
        mandatory_satisfied_requests=(
            result.analysis.mandatory_satisfied_requests
        ),
        mandatory_requests=result.analysis.mandatory_requests,
        solver_status=result.solver_status,
        schedule_status=result.schedule.status.value,
    )


def build_disruption_events_dataframe(
    result: DisruptionReplanningResult,
) -> pd.DataFrame:
    plan = result.application_result.plan
    rows: list[dict[str, object]] = []

    for outage in plan.satellite_outages:
        rows.append(
            {
                "event_type": "SATELLITE_OUTAGE",
                "object_id": outage.satellite_id,
                "effective_at_utc": outage.effective_from_utc,
                "value": None,
                "reason": outage.reason,
            }
        )

    for update in plan.cloud_cover_updates:
        rows.append(
            {
                "event_type": "CLOUD_COVER_UPDATE",
                "object_id": update.opportunity_id,
                "effective_at_utc": plan.occurred_at_utc,
                "value": update.cloud_cover,
                "reason": update.reason,
            }
        )

    for package in plan.urgent_requests:
        rows.append(
            {
                "event_type": "URGENT_REQUEST",
                "object_id": package.request.request_id,
                "effective_at_utc": (
                    package.request.earliest_start_utc
                ),
                "value": package.request.priority,
                "reason": package.request.notes,
            }
        )

    return pd.DataFrame(rows, columns=DISRUPTION_EVENT_COLUMNS)


def build_disruption_changes_dataframe(
    result: DisruptionReplanningResult,
) -> pd.DataFrame:
    return pd.DataFrame(build_schedule_change_rows(result))


def build_experiment_summary_dataframe(
    result: ExperimentalValidationResult,
) -> pd.DataFrame:
    rows = [asdict(record) for record in result.summary_records]
    return pd.DataFrame(rows, columns=EXPERIMENT_SUMMARY_COLUMNS)


def build_experiment_pairs_dataframe(
    result: ExperimentalValidationResult,
) -> pd.DataFrame:
    rows = [asdict(record) for record in result.pair_records]
    return pd.DataFrame(rows, columns=EXPERIMENT_PAIR_COLUMNS)


def build_experiment_runs_dataframe(
    result: ExperimentalValidationResult,
) -> pd.DataFrame:
    return pd.DataFrame(
        [asdict(record) for record in result.run_records]
    )


def build_experiment_profile_dataframe(
    result: ExperimentalValidationResult,
) -> pd.DataFrame:
    summary = build_experiment_summary_dataframe(result)
    pairs = build_experiment_pairs_dataframe(result)

    improvement = (
        pairs.groupby("profile_id", as_index=False)
        .agg(
            objective_improvement_pct=(
                "objective_improvement_pct",
                "mean",
            ),
            cp_sat_better_count=(
                "objective_difference",
                lambda values: int((values > 1e-9).sum()),
            ),
            comparison_count=("objective_difference", "size"),
        )
    )

    pivot = summary.pivot(
        index=["profile_id", "profile_name"],
        columns="algorithm",
        values=[
            "objective_mean",
            "fully_satisfied_requests_mean",
            "runtime_mean_s",
        ],
    )
    pivot.columns = [
        f"{metric}_{algorithm.lower()}"
        for metric, algorithm in pivot.columns
    ]
    pivot = pivot.reset_index()

    return pivot.merge(
        improvement,
        on="profile_id",
        how="left",
    )


def build_experiment_objective_figure(
    result: ExperimentalValidationResult,
) -> Figure:
    dataframe = build_experiment_summary_dataframe(result)
    figure = px.bar(
        dataframe,
        x="profile_id",
        y="objective_mean",
        color="algorithm",
        barmode="group",
        error_y="objective_std",
        labels={
            "profile_id": "Profil",
            "objective_mean": "Średnia funkcja celu",
            "algorithm": "Algorytm",
        },
        title="Średnia wartość funkcji celu",
    )
    figure.update_layout(legend_title_text="Algorytm")
    return figure


def build_experiment_satisfaction_figure(
    result: ExperimentalValidationResult,
) -> Figure:
    dataframe = build_experiment_summary_dataframe(result)
    figure = px.bar(
        dataframe,
        x="profile_id",
        y="fully_satisfied_requests_mean",
        color="algorithm",
        barmode="group",
        labels={
            "profile_id": "Profil",
            "fully_satisfied_requests_mean": (
                "Średnia liczba zrealizowanych zleceń"
            ),
            "algorithm": "Algorytm",
        },
        title="Realizacja zleceń",
    )
    return figure


def build_experiment_runtime_figure(
    result: ExperimentalValidationResult,
) -> Figure:
    dataframe = build_experiment_summary_dataframe(result)
    figure = px.bar(
        dataframe,
        x="profile_id",
        y="runtime_mean_s",
        color="algorithm",
        barmode="group",
        error_y="runtime_std_s",
        log_y=True,
        labels={
            "profile_id": "Profil",
            "runtime_mean_s": "Średni czas [s] — skala log",
            "algorithm": "Algorytm",
        },
        title="Czas obliczeń",
    )
    return figure


def build_experiment_improvement_figure(
    result: ExperimentalValidationResult,
) -> Figure:
    pairs = build_experiment_pairs_dataframe(result)
    averages = (
        pairs.groupby("profile_id", as_index=False)[
            "objective_improvement_pct"
        ]
        .mean()
        .sort_values("profile_id")
    )

    figure = px.bar(
        averages,
        x="profile_id",
        y="objective_improvement_pct",
        labels={
            "profile_id": "Profil",
            "objective_improvement_pct": "Poprawa CP-SAT [%]",
        },
        title="Średnia przewaga CP-SAT nad Greedy",
        text_auto=".2f",
    )
    return figure


def build_experiment_metadata_json(
    result: ExperimentalValidationResult,
) -> str:
    payload = {
        "base_scenario_id": result.base_scenario_id,
        "profiles": [asdict(profile) for profile in result.config.profiles],
        "repetitions": result.config.repetitions,
        "base_seed": result.config.base_seed,
        "memory_reserve_ratio": result.config.memory_reserve_ratio,
        "cp_sat_time_limit_s": result.config.cp_sat_time_limit_s,
        "cp_sat_num_search_workers": (
            result.config.cp_sat_num_search_workers
        ),
        "started_at_utc": result.started_at_utc.isoformat(),
        "completed_at_utc": result.completed_at_utc.isoformat(),
        "wall_clock_runtime_s": result.wall_clock_runtime_s,
        "cp_sat_better_objective_count": (
            result.cp_sat_better_objective_count
        ),
        "cp_sat_not_worse_objective_count": (
            result.cp_sat_not_worse_objective_count
        ),
        "mean_objective_improvement_pct": (
            result.mean_objective_improvement_pct
        ),
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def _pair_mean(
    records: Iterable[ExperimentPairRecord],
    field_name: str,
) -> float:
    values = [float(getattr(record, field_name)) for record in records]
    return sum(values) / len(values) if values else 0.0
