from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.services.comparison_service import (
    PlanningComparisonResult,
)
from app.ui.dataframes import (
    build_request_status_dataframe,
)
from app.ui.gantt import build_gantt_dataframe


COMPARISON_SUMMARY_COLUMNS = [
    "algorithm",
    "solver_status",
    "schedule_status",
    "objective_value",
    "fully_satisfied_requests",
    "partially_satisfied_requests",
    "unassigned_requests",
    "mandatory_satisfied_requests",
    "total_acquisitions",
    "sar_acquisitions",
    "optical_acquisitions",
    "satisfaction_ratio",
    "solver_runtime_s",
    "wall_clock_runtime_s",
]

REQUEST_COMPARISON_COLUMNS = [
    "request_id",
    "name",
    "request_mode",
    "priority",
    "is_mandatory",
    "greedy_status",
    "cp_sat_status",
    "status_outcome",
    "selection_relation",
    "greedy_entry_count",
    "cp_sat_entry_count",
    "greedy_sensor_types",
    "cp_sat_sensor_types",
    "greedy_satellites",
    "cp_sat_satellites",
    "greedy_opportunities",
    "cp_sat_opportunities",
]

STATUS_RANK = {
    "UNASSIGNED": 0,
    "PARTIALLY_SATISFIED": 1,
    "FULLY_SATISFIED": 2,
}


@dataclass(frozen=True)
class ComparisonMetrics:
    """KPI porównania Greedy i CP-SAT."""

    greedy_objective: float
    cp_sat_objective: float
    objective_difference: float
    objective_improvement_pct: float

    greedy_fully_satisfied: int
    cp_sat_fully_satisfied: int
    fully_satisfied_difference: int

    greedy_unassigned: int
    cp_sat_unassigned: int
    unassigned_reduction: int

    greedy_acquisitions: int
    cp_sat_acquisitions: int
    acquisition_difference: int

    greedy_runtime_s: float
    cp_sat_runtime_s: float
    cp_sat_solver_status: str


def build_comparison_metrics(
    comparison: PlanningComparisonResult,
) -> ComparisonMetrics:
    return ComparisonMetrics(
        greedy_objective=(
            comparison.greedy.objective_value
        ),
        cp_sat_objective=(
            comparison.cp_sat.objective_value
        ),
        objective_difference=(
            comparison.objective_difference
        ),
        objective_improvement_pct=(
            comparison.objective_improvement_pct
        ),
        greedy_fully_satisfied=(
            comparison
            .greedy
            .fully_satisfied_requests
        ),
        cp_sat_fully_satisfied=(
            comparison
            .cp_sat
            .fully_satisfied_requests
        ),
        fully_satisfied_difference=(
            comparison
            .fully_satisfied_difference
        ),
        greedy_unassigned=(
            comparison.greedy.unassigned_requests
        ),
        cp_sat_unassigned=(
            comparison.cp_sat.unassigned_requests
        ),
        unassigned_reduction=(
            comparison.unassigned_reduction
        ),
        greedy_acquisitions=(
            comparison.greedy.total_acquisitions
        ),
        cp_sat_acquisitions=(
            comparison.cp_sat.total_acquisitions
        ),
        acquisition_difference=(
            comparison.acquisition_difference
        ),
        greedy_runtime_s=(
            comparison.greedy.wall_clock_runtime_s
        ),
        cp_sat_runtime_s=(
            comparison.cp_sat.wall_clock_runtime_s
        ),
        cp_sat_solver_status=(
            comparison.cp_sat.solver_status
        ),
    )


def build_comparison_summary_dataframe(
    comparison: PlanningComparisonResult,
) -> pd.DataFrame:
    rows = [
        _summary_row(
            algorithm_label="Greedy",
            result=comparison.greedy,
        ),
        _summary_row(
            algorithm_label="CP-SAT",
            result=comparison.cp_sat,
        ),
    ]

    return pd.DataFrame(
        rows,
        columns=COMPARISON_SUMMARY_COLUMNS,
    )


def build_request_comparison_dataframe(
    comparison: PlanningComparisonResult,
) -> pd.DataFrame:
    greedy_status = build_request_status_dataframe(
        comparison.greedy
    ).set_index(
        "request_id"
    )

    cp_sat_status = build_request_status_dataframe(
        comparison.cp_sat
    ).set_index(
        "request_id"
    )

    greedy_entries = _entries_by_request(
        comparison.greedy.schedule.active_entries
    )

    cp_sat_entries = _entries_by_request(
        comparison.cp_sat.schedule.active_entries
    )

    rows: list[dict[str, Any]] = []

    for request in sorted(
        comparison.scenario.request_set.active_requests,
        key=lambda item: (
            -int(item.is_mandatory),
            -item.priority,
            item.request_id,
        ),
    ):
        request_id = request.request_id

        greedy_row = greedy_status.loc[
            request_id
        ]

        cp_sat_row = cp_sat_status.loc[
            request_id
        ]

        greedy_request_entries = greedy_entries.get(
            request_id,
            [],
        )

        cp_sat_request_entries = cp_sat_entries.get(
            request_id,
            [],
        )

        greedy_opportunities = tuple(
            sorted(
                entry.opportunity_id
                for entry in greedy_request_entries
            )
        )

        cp_sat_opportunities = tuple(
            sorted(
                entry.opportunity_id
                for entry in cp_sat_request_entries
            )
        )

        greedy_status_value = str(
            greedy_row[
                "fulfillment_status"
            ]
        )

        cp_sat_status_value = str(
            cp_sat_row[
                "fulfillment_status"
            ]
        )

        rows.append(
            {
                "request_id": request_id,
                "name": request.name,
                "request_mode": _enum_value(
                    request.request_mode
                ),
                "priority": request.priority,
                "is_mandatory": request.is_mandatory,
                "greedy_status": greedy_status_value,
                "cp_sat_status": cp_sat_status_value,
                "status_outcome": _status_outcome(
                    greedy_status=greedy_status_value,
                    cp_sat_status=cp_sat_status_value,
                ),
                "selection_relation": _selection_relation(
                    greedy_opportunities=(
                        greedy_opportunities
                    ),
                    cp_sat_opportunities=(
                        cp_sat_opportunities
                    ),
                ),
                "greedy_entry_count": len(
                    greedy_request_entries
                ),
                "cp_sat_entry_count": len(
                    cp_sat_request_entries
                ),
                "greedy_sensor_types": _joined_values(
                    entry.sensor_type
                    for entry in greedy_request_entries
                ),
                "cp_sat_sensor_types": _joined_values(
                    entry.sensor_type
                    for entry in cp_sat_request_entries
                ),
                "greedy_satellites": _joined_values(
                    entry.satellite_id
                    for entry in greedy_request_entries
                ),
                "cp_sat_satellites": _joined_values(
                    entry.satellite_id
                    for entry in cp_sat_request_entries
                ),
                "greedy_opportunities": "|".join(
                    greedy_opportunities
                ),
                "cp_sat_opportunities": "|".join(
                    cp_sat_opportunities
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=REQUEST_COMPARISON_COLUMNS,
    )


def build_objective_comparison_figure(
    comparison: PlanningComparisonResult,
) -> go.Figure:
    dataframe = build_comparison_summary_dataframe(
        comparison
    )

    figure = px.bar(
        dataframe,
        x="algorithm",
        y="objective_value",
        text="objective_value",
        labels={
            "algorithm": "Algorytm",
            "objective_value": "Funkcja celu",
        },
        title="Porównanie funkcji celu",
    )

    figure.update_traces(
        texttemplate="%{text:.3f}",
        textposition="outside",
    )

    figure.update_layout(
        height=430,
        showlegend=False,
        margin={
            "l": 30,
            "r": 20,
            "t": 70,
            "b": 30,
        },
    )

    return figure


def build_request_counts_comparison_figure(
    comparison: PlanningComparisonResult,
) -> go.Figure:
    summary = build_comparison_summary_dataframe(
        comparison
    )

    long_dataframe = summary.melt(
        id_vars=[
            "algorithm"
        ],
        value_vars=[
            "fully_satisfied_requests",
            "partially_satisfied_requests",
            "unassigned_requests",
        ],
        var_name="metric",
        value_name="value",
    )

    labels = {
        "fully_satisfied_requests": (
            "W pełni zrealizowane"
        ),
        "partially_satisfied_requests": (
            "Częściowo zrealizowane"
        ),
        "unassigned_requests": (
            "Nieprzypisane"
        ),
    }

    long_dataframe["metric"] = (
        long_dataframe["metric"].map(
            labels
        )
    )

    figure = px.bar(
        long_dataframe,
        x="metric",
        y="value",
        color="algorithm",
        barmode="group",
        text="value",
        labels={
            "algorithm": "Algorytm",
            "metric": "Status zlecenia",
            "value": "Liczba zleceń",
        },
        title="Porównanie realizacji zleceń",
    )

    figure.update_traces(
        textposition="outside"
    )

    figure.update_layout(
        height=430,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0.0,
        },
        margin={
            "l": 30,
            "r": 20,
            "t": 90,
            "b": 30,
        },
    )

    return figure


def build_comparison_gantt_dataframe(
    comparison: PlanningComparisonResult,
) -> pd.DataFrame:
    dataframes: list[pd.DataFrame] = []

    for label, result in (
        (
            "Greedy",
            comparison.greedy,
        ),
        (
            "CP-SAT",
            comparison.cp_sat,
        ),
    ):
        dataframe = build_gantt_dataframe(
            result
        ).copy()

        if dataframe.empty:
            continue

        dataframe["algorithm"] = label
        dataframe["lane"] = (
            dataframe["algorithm"]
            + " · "
            + dataframe["satellite_id"]
        )

        dataframes.append(
            dataframe
        )

    if not dataframes:
        return pd.DataFrame()

    return pd.concat(
        dataframes,
        ignore_index=True,
    ).sort_values(
        by=[
            "algorithm",
            "satellite_id",
            "start_utc",
            "entry_id",
        ],
        kind="stable",
        ignore_index=True,
    )


def build_comparison_gantt_figure(
    comparison: PlanningComparisonResult,
) -> go.Figure:
    dataframe = build_comparison_gantt_dataframe(
        comparison
    )

    if dataframe.empty:
        figure = go.Figure()

        figure.add_annotation(
            text="Oba harmonogramy są puste.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )

        figure.update_layout(
            height=420
        )

        return figure

    satellite_ids = [
        satellite.satellite_id
        for satellite
        in comparison.scenario.catalog.satellites
    ]

    lane_order = [
        *[
            f"Greedy · {satellite_id}"
            for satellite_id in satellite_ids
        ],
        *[
            f"CP-SAT · {satellite_id}"
            for satellite_id in satellite_ids
        ],
    ]

    visible_lanes = set(
        dataframe["lane"]
    )

    lane_order = [
        lane
        for lane in lane_order
        if lane in visible_lanes
    ]

    figure = px.timeline(
        dataframe,
        x_start="start_utc",
        x_end="end_utc",
        y="lane",
        color="algorithm",
        hover_name="request_id",
        hover_data={
            "satellite_id": True,
            "sensor_type": True,
            "mode_id": True,
            "priority": True,
            "is_mandatory": True,
            "start_utc": True,
            "end_utc": True,
            "duration_s": ":.3f",
            "objective_contribution": ":.3f",
            "lane": False,
            "algorithm": False,
        },
        category_orders={
            "lane": lane_order,
            "algorithm": [
                "Greedy",
                "CP-SAT",
            ],
        },
        labels={
            "lane": "Algorytm i satelita",
            "algorithm": "Algorytm",
            "request_id": "Zlecenie",
            "satellite_id": "Satelita",
            "sensor_type": "Sensor",
            "mode_id": "Tryb obrazowania",
            "priority": "Priorytet",
            "is_mandatory": "Obowiązkowe",
            "start_utc": "Początek UTC",
            "end_utc": "Koniec UTC",
            "duration_s": "Czas [s]",
            "objective_contribution": "Wkład do celu",
        },
        title="Wspólny Gantt Greedy i CP-SAT",
    )

    figure.update_yaxes(
        autorange="reversed",
        categoryorder="array",
        categoryarray=lane_order,
    )

    figure.update_xaxes(
        title_text="Czas UTC",
        tickformat="%H:%M<br>%d-%m-%Y",
        rangeslider={
            "visible": True,
            "thickness": 0.07,
        },
    )

    figure.update_layout(
        height=max(
            620,
            48 * len(lane_order) + 260,
        ),
        bargap=0.22,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0.0,
        },
        margin={
            "l": 40,
            "r": 20,
            "t": 95,
            "b": 40,
        },
    )

    return figure


def _summary_row(
    *,
    algorithm_label: str,
    result: Any,
) -> dict[str, Any]:
    return {
        "algorithm": algorithm_label,
        "solver_status": result.solver_status,
        "schedule_status": (
            result.schedule.status.value
        ),
        "objective_value": round(
            result.objective_value,
            6,
        ),
        "fully_satisfied_requests": (
            result.analysis.fully_satisfied_requests
        ),
        "partially_satisfied_requests": (
            result.analysis.partially_satisfied_requests
        ),
        "unassigned_requests": (
            result.analysis.unassigned_requests
        ),
        "mandatory_satisfied_requests": (
            result.analysis.mandatory_satisfied_requests
        ),
        "total_acquisitions": (
            result.analysis.total_acquisitions
        ),
        "sar_acquisitions": (
            result.analysis.sar_acquisitions
        ),
        "optical_acquisitions": (
            result.analysis.optical_acquisitions
        ),
        "satisfaction_ratio": round(
            result.analysis.satisfaction_ratio,
            6,
        ),
        "solver_runtime_s": round(
            float(
                result.schedule.solver_runtime_s
                or 0.0
            ),
            6,
        ),
        "wall_clock_runtime_s": round(
            result.wall_clock_runtime_s,
            6,
        ),
    }


def _entries_by_request(
    entries: Any,
) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)

    for entry in entries:
        grouped[
            entry.request_id
        ].append(
            entry
        )

    return grouped


def _status_outcome(
    *,
    greedy_status: str,
    cp_sat_status: str,
) -> str:
    greedy_rank = STATUS_RANK[
        greedy_status
    ]

    cp_sat_rank = STATUS_RANK[
        cp_sat_status
    ]

    if cp_sat_rank > greedy_rank:
        return "CP_SAT_BETTER"

    if greedy_rank > cp_sat_rank:
        return "GREEDY_BETTER"

    return "SAME_STATUS"


def _selection_relation(
    *,
    greedy_opportunities: tuple[str, ...],
    cp_sat_opportunities: tuple[str, ...],
) -> str:
    if (
        not greedy_opportunities
        and not cp_sat_opportunities
    ):
        return "NEITHER"

    if (
        greedy_opportunities
        and not cp_sat_opportunities
    ):
        return "GREEDY_ONLY"

    if (
        cp_sat_opportunities
        and not greedy_opportunities
    ):
        return "CP_SAT_ONLY"

    if greedy_opportunities == cp_sat_opportunities:
        return "BOTH_SAME"

    return "BOTH_DIFFERENT"


def _joined_values(
    values: Any,
) -> str:
    normalized = sorted(
        {
            _enum_value(value)
            for value in values
        }
    )

    return "|".join(
        normalized
    )


def _enum_value(
    value: Any,
) -> str:
    return str(
        getattr(
            value,
            "value",
            value,
        )
    )
