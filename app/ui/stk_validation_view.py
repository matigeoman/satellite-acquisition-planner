from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from app.integrations.access.models import GeometricAccessWindow
from app.integrations.stk_validation import (
    AccessValidationResult,
    AerValidationResult,
    StkAccessInterval,
)


def access_matches_dataframe(result: AccessValidationResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Okno modelu": item.model_window_id,
                "Przedział STK": item.stk_interval_id,
                "Start model UTC": item.model_start_utc,
                "Start STK UTC": item.stk_start_utc,
                "Błąd startu [s]": item.start_error_s,
                "Koniec model UTC": item.model_end_utc,
                "Koniec STK UTC": item.stk_end_utc,
                "Błąd końca [s]": item.end_error_s,
                "Czas model [s]": item.model_duration_s,
                "Czas STK [s]": item.stk_duration_s,
                "Błąd czasu [s]": item.duration_error_s,
                "Nakładanie [s]": item.overlap_s,
                "Współczynnik nakładania": item.overlap_ratio,
            }
            for item in result.matched
        ]
    )


def aer_matches_dataframe(result: AerValidationResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Czas STK UTC": item.timestamp_utc,
                "Czas model UTC": item.model_timestamp_utc,
                "Przesunięcie czasu [s]": item.time_offset_s,
                "Azymut model [°]": item.model_azimuth_deg,
                "Azymut STK [°]": item.stk_azimuth_deg,
                "Błąd azymutu [°]": item.azimuth_error_deg,
                "Elewacja model [°]": item.model_elevation_deg,
                "Elewacja STK [°]": item.stk_elevation_deg,
                "Błąd elewacji [°]": item.elevation_error_deg,
                "Zasięg model [km]": item.model_range_km,
                "Zasięg STK [km]": item.stk_range_km,
                "Błąd zasięgu [km]": item.range_error_km,
            }
            for item in result.matched
        ]
    )


def build_access_comparison_figure(
    model_windows: tuple[GeometricAccessWindow, ...],
    stk_intervals: tuple[StkAccessInterval, ...],
) -> go.Figure:
    figure = go.Figure()
    for index, window in enumerate(model_windows):
        figure.add_trace(
            go.Scatter(
                x=[window.start_utc, window.end_utc],
                y=["Model SatPlan", "Model SatPlan"],
                mode="lines+markers",
                line={"width": 10},
                marker={"size": 7},
                name="Model SatPlan",
                legendgroup="model",
                showlegend=index == 0,
                customdata=[[window.window_id], [window.window_id]],
                hovertemplate=(
                    "%{customdata[0]}<br>%{x|%Y-%m-%d %H:%M:%S UTC}<extra></extra>"
                ),
            )
        )
    for index, interval in enumerate(stk_intervals):
        figure.add_trace(
            go.Scatter(
                x=[interval.start_utc, interval.end_utc],
                y=["STK", "STK"],
                mode="lines+markers",
                line={"width": 10},
                marker={"size": 7},
                name="STK",
                legendgroup="stk",
                showlegend=index == 0,
                customdata=[[interval.interval_id], [interval.interval_id]],
                hovertemplate=(
                    "%{customdata[0]}<br>%{x|%Y-%m-%d %H:%M:%S UTC}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        title="Porównanie okien modelu i STK",
        height=330,
        margin={"l": 20, "r": 20, "t": 55, "b": 30},
        legend={"orientation": "h", "y": 1.13, "x": 0.0},
        xaxis_title="Czas UTC",
        yaxis_title=None,
        hovermode="closest",
        uirevision="stk-access-comparison",
    )
    return figure


def build_aer_error_figure(result: AerValidationResult) -> go.Figure:
    figure = go.Figure()
    timestamps = [item.timestamp_utc for item in result.matched]
    figure.add_trace(
        go.Scatter(
            x=timestamps,
            y=[item.azimuth_error_deg for item in result.matched],
            mode="lines+markers",
            name="Azymut [°]",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=timestamps,
            y=[item.elevation_error_deg for item in result.matched],
            mode="lines+markers",
            name="Elewacja [°]",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=timestamps,
            y=[item.range_error_km for item in result.matched],
            mode="lines+markers",
            name="Zasięg [km]",
            yaxis="y2",
        )
    )
    figure.update_layout(
        title="Błędy geometrii AER w czasie",
        height=430,
        margin={"l": 20, "r": 45, "t": 55, "b": 30},
        xaxis_title="Czas UTC",
        yaxis={"title": "Błąd kąta [°]", "zeroline": True},
        yaxis2={
            "title": "Błąd zasięgu [km]",
            "overlaying": "y",
            "side": "right",
            "zeroline": False,
        },
        legend={"orientation": "h", "y": 1.13, "x": 0.0},
        uirevision="stk-aer-comparison",
    )
    return figure
