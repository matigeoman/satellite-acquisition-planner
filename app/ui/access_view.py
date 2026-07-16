from __future__ import annotations

from collections import defaultdict

import pandas as pd
import plotly.graph_objects as go

from app.geospatial.aoi import geometry_bounds, geometry_centroid
from app.integrations.access import AccessCalculationResult
from app.models.enums import SensorType
from app.models.geometry import PointGeometry, TargetGeometry


_SAR_COLORS = ("#4cc9f0", "#4895ef", "#4361ee", "#3a0ca3")
_EO_COLORS = ("#ffb703", "#fb8500")


def _slot_colors(result: AccessCalculationResult) -> dict[str, str]:
    by_type: dict[SensorType, list[str]] = defaultdict(list)
    for window in result.windows:
        if window.satellite_id not in by_type[window.sensor_type]:
            by_type[window.sensor_type].append(window.satellite_id)

    output: dict[str, str] = {}
    for sensor_type, slot_ids in by_type.items():
        palette = _SAR_COLORS if sensor_type == SensorType.SAR else _EO_COLORS
        for index, slot_id in enumerate(slot_ids):
            output[slot_id] = palette[index % len(palette)]
    return output


def _map_zoom(geometry: TargetGeometry) -> float:
    if isinstance(geometry, PointGeometry):
        return 5.0
    (south, west), (north, east) = geometry_bounds(geometry)
    extent = max(north - south, east - west)
    if extent < 0.2:
        return 7.0
    if extent < 1.0:
        return 5.5
    if extent < 5.0:
        return 4.0
    return 2.5


def build_access_map_figure(
    result: AccessCalculationResult,
    geometry: TargetGeometry,
) -> go.Figure:
    """Mapa AOI i fragmentów śladów należących do okien dostępu."""

    figure = go.Figure()
    colors = _slot_colors(result)
    center_longitude, center_latitude = geometry_centroid(geometry)

    if isinstance(geometry, PointGeometry):
        longitude, latitude = geometry.coordinates
        figure.add_trace(
            go.Scattermap(
                lon=[longitude],
                lat=[latitude],
                mode="markers",
                name="Punkt zainteresowania",
                marker={
                    "size": 18,
                    "color": "#f72585",
                },
                hovertemplate=(
                    "<b>Punkt zainteresowania</b><br>"
                    "Szerokość: %{lat:.5f}°<br>"
                    "Długość: %{lon:.5f}°<extra></extra>"
                ),
            )
        )
    else:
        ring = geometry.coordinates[0]
        figure.add_trace(
            go.Scattermap(
                lon=[position[0] for position in ring],
                lat=[position[1] for position in ring],
                mode="lines",
                fill="toself",
                name="AOI",
                line={"width": 3, "color": "#f72585"},
                fillcolor="rgba(247, 37, 133, 0.20)",
                hovertemplate="<b>Poligon zainteresowania</b><extra></extra>",
            )
        )

    legend_seen: set[str] = set()
    for window in result.windows:
        if not window.path:
            continue
        label = f"{window.satellite_id} — {window.satellite_name}"
        showlegend = window.satellite_id not in legend_seen
        legend_seen.add(window.satellite_id)
        color = colors.get(window.satellite_id, "#e5e7eb")
        figure.add_trace(
            go.Scattermap(
                lon=[point.satellite_longitude_deg for point in window.path],
                lat=[point.satellite_latitude_deg for point in window.path],
                customdata=[
                    (
                        point.timestamp_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        point.off_nadir_angle_deg,
                        point.incidence_angle_deg,
                        window.mode_name,
                    )
                    for point in window.path
                ],
                mode="lines",
                name=label,
                legendgroup=window.satellite_id,
                showlegend=showlegend,
                line={
                    "width": 5,
                    "color": color,
                },
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "Tryb: %{customdata[3]}<br>"
                    "Czas: %{customdata[0]}<br>"
                    "Off-nadir: %{customdata[1]:.2f}°<br>"
                    "Incidence: %{customdata[2]:.2f}°<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        height=620,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        map={
            "style": "carto-darkmatter",
            "center": {"lat": center_latitude, "lon": center_longitude},
            "zoom": _map_zoom(geometry),
        },
        legend={
            "orientation": "v",
            "x": 0.012,
            "y": 0.985,
            "bgcolor": "rgba(8, 13, 22, 0.84)",
            "bordercolor": "rgba(255,255,255,0.24)",
            "borderwidth": 1,
            "font": {"size": 14, "color": "#f4f7fb"},
        },
        hoverlabel={"font_size": 15, "bgcolor": "#101722"},
        uirevision=f"access-map-{result.request_id}",
    )
    return figure


def build_access_timeline_figure(
    result: AccessCalculationResult,
) -> go.Figure:
    """Buduje oś czasu okien w układzie satelita / tryb."""

    figure = go.Figure()
    colors = _slot_colors(result)
    legend_seen: set[SensorType] = set()
    for window in result.windows:
        row_label = f"{window.satellite_id} · {window.mode_name}"
        showlegend = window.sensor_type not in legend_seen
        legend_seen.add(window.sensor_type)
        figure.add_trace(
            go.Scatter(
                x=[window.start_utc, window.end_utc],
                y=[row_label, row_label],
                mode="lines+markers",
                name=(
                    "ICEYE SAR"
                    if window.sensor_type == SensorType.SAR
                    else "Pléiades Neo EO"
                ),
                legendgroup=window.sensor_type.value,
                showlegend=showlegend,
                line={
                    "width": 12,
                    "color": colors.get(window.satellite_id, "#e5e7eb"),
                },
                marker={"size": 8},
                customdata=[
                    [
                        window.window_id,
                        window.duration_s,
                        window.observation_side.value,
                        window.coverage_ratio,
                    ],
                    [
                        window.window_id,
                        window.duration_s,
                        window.observation_side.value,
                        window.coverage_ratio,
                    ],
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Czas: %{x|%Y-%m-%d %H:%M:%S UTC}<br>"
                    "Długość okna: %{customdata[1]:.0f} s<br>"
                    "Strona: %{customdata[2]}<br>"
                    "Pokrycie: %{customdata[3]:.1%}<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        height=max(430, min(900, 240 + len(result.windows) * 18)),
        margin={"l": 10, "r": 10, "t": 25, "b": 35},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20, 28, 40, 0.72)",
        xaxis={
            "title": "Czas UTC",
            "gridcolor": "rgba(255,255,255,0.12)",
            "showgrid": True,
        },
        yaxis={
            "title": "Satelita i tryb",
            "gridcolor": "rgba(255,255,255,0.08)",
            "automargin": True,
        },
        legend={"orientation": "h", "y": 1.08},
        hoverlabel={"font_size": 15, "bgcolor": "#101722"},
    )
    return figure


def access_windows_dataframe(result: AccessCalculationResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Okno": window.window_id,
                "Satelita": window.satellite_id,
                "Obiekt publiczny": window.satellite_name,
                "Sensor": window.sensor_type.value,
                "Tryb": window.mode_name,
                "Początek UTC": window.start_utc.isoformat(),
                "Koniec UTC": window.end_utc.isoformat(),
                "Czas [s]": round(window.duration_s, 1),
                "Strona": window.observation_side.value,
                "Pokrycie": round(window.coverage_ratio, 4),
                "Off-nadir min [°]": round(
                    window.minimum_off_nadir_deg,
                    2,
                ),
                "Off-nadir max [°]": round(
                    window.maximum_off_nadir_deg,
                    2,
                ),
                "Incidence min [°]": round(
                    window.minimum_incidence_angle_deg,
                    2,
                ),
                "Incidence max [°]": round(
                    window.maximum_incidence_angle_deg,
                    2,
                ),
                "Słońce w optimum [°]": (
                    None
                    if window.peak_sun_elevation_deg is None
                    else round(window.peak_sun_elevation_deg, 2)
                ),
                "Epoka OMM": window.orbit_epoch_utc.isoformat(),
            }
            for window in result.windows
        ]
    )
