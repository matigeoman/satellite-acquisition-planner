from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.services.planning_service import PlanningResult


GANTT_COLUMNS = [
    "entry_id",
    "opportunity_id",
    "request_id",
    "request_name",
    "request_mode",
    "priority",
    "is_mandatory",
    "satellite_id",
    "sensor_type",
    "mode_id",
    "entry_status",
    "start_utc",
    "end_utc",
    "duration_s",
    "estimated_data_volume_mb",
    "objective_contribution",
    "quality_score",
    "coverage_ratio",
]


def build_gantt_dataframe(
    result: PlanningResult,
) -> pd.DataFrame:
    """Buduje dane źródłowe interaktywnego wykresu Gantta."""

    requests_by_id = {
        request.request_id: request
        for request
        in result.scenario.request_set.active_requests
    }

    opportunities_by_id = {
        opportunity.opportunity_id: opportunity
        for opportunity
        in result.scenario.opportunity_set.opportunities
    }

    rows: list[dict[str, Any]] = []

    for entry in result.schedule.active_entries:
        try:
            request = requests_by_id[
                entry.request_id
            ]
        except KeyError as error:
            raise KeyError(
                "Harmonogram odwołuje się do nieznanego "
                f"zlecenia: {entry.request_id}"
            ) from error

        try:
            opportunity = opportunities_by_id[
                entry.opportunity_id
            ]
        except KeyError as error:
            raise KeyError(
                "Harmonogram odwołuje się do nieznanej "
                f"okazji: {entry.opportunity_id}"
            ) from error

        rows.append(
            {
                "entry_id": entry.entry_id,
                "opportunity_id": entry.opportunity_id,
                "request_id": entry.request_id,
                "request_name": request.name,
                "request_mode": _enum_value(
                    request.request_mode
                ),
                "priority": request.priority,
                "is_mandatory": request.is_mandatory,
                "satellite_id": entry.satellite_id,
                "sensor_type": _enum_value(
                    entry.sensor_type
                ),
                "mode_id": entry.mode_id,
                "entry_status": _enum_value(
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
            }
        )

    dataframe = pd.DataFrame(
        rows,
        columns=GANTT_COLUMNS,
    )

    if dataframe.empty:
        return dataframe

    dataframe["start_utc"] = pd.to_datetime(
        dataframe["start_utc"],
        utc=True,
    )

    dataframe["end_utc"] = pd.to_datetime(
        dataframe["end_utc"],
        utc=True,
    )

    return dataframe.sort_values(
        by=[
            "start_utc",
            "satellite_id",
            "entry_id",
        ],
        kind="stable",
        ignore_index=True,
    )


def build_gantt_figure(
    result: PlanningResult,
    *,
    satellite_ids: Iterable[str] | None = None,
    sensor_types: Iterable[str] | None = None,
    full_horizon: bool = False,
) -> go.Figure:
    """
    Buduje interaktywny wykres Gantta.

    Domyślny zakres osi czasu obejmuje akwizycje z niewielkim
    marginesem. Opcja full_horizon pokazuje cały horyzont planowania.
    """

    dataframe = build_gantt_dataframe(
        result
    )

    selected_satellites = (
        None
        if satellite_ids is None
        else {
            str(satellite_id)
            for satellite_id in satellite_ids
        }
    )

    selected_sensor_types = (
        None
        if sensor_types is None
        else {
            _enum_value(sensor_type)
            for sensor_type in sensor_types
        }
    )

    if selected_satellites is not None:
        dataframe = dataframe.loc[
            dataframe["satellite_id"].isin(
                selected_satellites
            )
        ]

    if selected_sensor_types is not None:
        dataframe = dataframe.loc[
            dataframe["sensor_type"].isin(
                selected_sensor_types
            )
        ]

    dataframe = dataframe.reset_index(
        drop=True
    )

    if dataframe.empty:
        return _build_empty_gantt_figure()

    satellite_order = [
        satellite.satellite_id
        for satellite
        in result.scenario.catalog.satellites
        if (
            selected_satellites is None
            or satellite.satellite_id
            in selected_satellites
        )
    ]

    visible_satellites = set(
        dataframe["satellite_id"]
    )

    satellite_order = [
        satellite_id
        for satellite_id in satellite_order
        if satellite_id in visible_satellites
    ]

    figure = px.timeline(
        dataframe,
        x_start="start_utc",
        x_end="end_utc",
        y="satellite_id",
        color="sensor_type",
        hover_name="request_id",
        hover_data={
            "request_name": True,
            "request_mode": True,
            "priority": True,
            "is_mandatory": True,
            "satellite_id": True,
            "sensor_type": True,
            "mode_id": True,
            "start_utc": True,
            "end_utc": True,
            "duration_s": ":.3f",
            "estimated_data_volume_mb": ":.3f",
            "objective_contribution": ":.3f",
            "quality_score": ":.3f",
            "coverage_ratio": ":.3f",
            "entry_id": False,
            "opportunity_id": False,
        },
        category_orders={
            "satellite_id": satellite_order,
            "sensor_type": [
                "SAR",
                "OPTICAL",
            ],
        },
        labels={
            "request_id": "Zlecenie",
            "request_name": "Nazwa",
            "request_mode": "Tryb zlecenia",
            "priority": "Priorytet",
            "is_mandatory": "Obowiązkowe",
            "satellite_id": "Satelita",
            "sensor_type": "Sensor",
            "mode_id": "Tryb obrazowania",
            "start_utc": "Początek UTC",
            "end_utc": "Koniec UTC",
            "duration_s": "Czas [s]",
            "estimated_data_volume_mb": "Dane [MB]",
            "objective_contribution": "Wkład do celu",
            "quality_score": "Jakość",
            "coverage_ratio": "Pokrycie",
        },
        title="Harmonogram akwizycji satelitarnych",
    )

    figure.update_yaxes(
        autorange="reversed",
        title_text="Satelita",
        categoryorder="array",
        categoryarray=satellite_order,
    )

    figure.update_xaxes(
        title_text="Czas UTC",
        type="date",
        tickformat="%H:%M<br>%d-%m-%Y",
        showgrid=True,
        rangeslider={
            "visible": True,
            "thickness": 0.08,
        },
    )

    x_start, x_end = _calculate_time_range(
        result=result,
        dataframe=dataframe,
        full_horizon=full_horizon,
    )

    figure.update_xaxes(
        range=[
            x_start,
            x_end,
        ]
    )

    figure.update_traces(
        marker_line_width=1,
        opacity=0.9,
    )

    chart_height = max(
        520,
        75 * len(satellite_order) + 220,
    )

    figure.update_layout(
        height=chart_height,
        barmode="overlay",
        bargap=0.25,
        hovermode="closest",
        legend={
            "title": {
                "text": "Sensor",
            },
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0.0,
        },
        margin={
            "l": 40,
            "r": 30,
            "t": 95,
            "b": 40,
        },
    )

    return figure


def _calculate_time_range(
    *,
    result: PlanningResult,
    dataframe: pd.DataFrame,
    full_horizon: bool,
) -> tuple[Any, Any]:
    horizon_start = (
        result.schedule.horizon_start_utc
    )

    horizon_end = (
        result.schedule.horizon_end_utc
    )

    if full_horizon:
        return (
            horizon_start,
            horizon_end,
        )

    first_start = (
        dataframe["start_utc"]
        .min()
        .to_pydatetime()
    )

    last_end = (
        dataframe["end_utc"]
        .max()
        .to_pydatetime()
    )

    acquisition_span = (
        last_end
        - first_start
    )

    proportional_padding = (
        acquisition_span
        * 0.05
    )

    minimum_padding = timedelta(
        minutes=10
    )

    padding = max(
        proportional_padding,
        minimum_padding,
    )

    visible_start = max(
        horizon_start,
        first_start - padding,
    )

    visible_end = min(
        horizon_end,
        last_end + padding,
    )

    if visible_start >= visible_end:
        return (
            horizon_start,
            horizon_end,
        )

    return (
        visible_start,
        visible_end,
    )


def _build_empty_gantt_figure() -> go.Figure:
    figure = go.Figure()

    figure.add_annotation(
        text=(
            "Brak akwizycji spełniających "
            "wybrane kryteria."
        ),
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={
            "size": 16,
        },
    )

    figure.update_xaxes(
        visible=False
    )

    figure.update_yaxes(
        visible=False
    )

    figure.update_layout(
        title="Harmonogram akwizycji satelitarnych",
        height=420,
        margin={
            "l": 20,
            "r": 20,
            "t": 70,
            "b": 20,
        },
    )

    return figure


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