from __future__ import annotations

from datetime import datetime
from math import asin, atan2, cos, pi, sin, sqrt
from typing import Sequence

import plotly.graph_objects as go

from app.integrations.orbits import SatelliteFamily, SatelliteGroundTrack
from app.integrations.orbits.coordinates import gmst_radians
from app.tracking import (
    LiveSatelliteState,
    ObserverSite,
    SkyTrack,
    spherical_circle,
    sun_unit_vector_eci,
)


SAR_COLOR = "#ff636a"
EO_COLOR = "#50a9ff"
OBSERVER_COLOR = "#f8fafc"
FOOTPRINT_COLOR = "#34d399"
TERMINATOR_COLOR = "rgba(226, 232, 240, 0.55)"
BACKGROUND_COLOR = "#07111f"
OCEAN_COLOR = "#071827"
LAND_COLOR = "#2b4050"
GRID_COLOR = "rgba(148, 163, 184, 0.25)"


def _family_color(family: SatelliteFamily) -> str:
    return SAR_COLOR if family == SatelliteFamily.ICEYE else EO_COLOR


def _split_antimeridian(
    longitudes: Sequence[float],
    latitudes: Sequence[float],
) -> tuple[list[float | None], list[float | None]]:
    output_lon: list[float | None] = []
    output_lat: list[float | None] = []
    previous: float | None = None
    for longitude, latitude in zip(longitudes, latitudes, strict=True):
        if previous is not None and abs(longitude - previous) > 180.0:
            output_lon.append(None)
            output_lat.append(None)
        output_lon.append(float(longitude))
        output_lat.append(float(latitude))
        previous = float(longitude)
    return output_lon, output_lat


def build_sky_map_figure(
    *,
    states: Sequence[LiveSatelliteState],
    tracks: Sequence[SkyTrack],
    minimum_elevation_deg: float = 0.0,
    selected_slot_id: str | None = None,
    height_px: int = 650,
) -> go.Figure:
    """Buduje lokalną mapę nieba w układzie azymut–elewacja."""

    figure = go.Figure()
    state_by_slot = {state.slot_id: state for state in states}
    for track in tracks:
        is_selected = (
            selected_slot_id is None or track.slot_id == selected_slot_id
        )
        visible = tuple(
            sample
            for sample in track.samples
            if sample.elevation_deg >= minimum_elevation_deg
        )
        if len(visible) >= 2:
            figure.add_trace(
                go.Scatterpolar(
                    r=[90.0 - sample.elevation_deg for sample in visible],
                    theta=[sample.azimuth_deg for sample in visible],
                    mode="lines",
                    line={
                        "color": _family_color(track.family),
                        "width": 3.2 if is_selected else 1.5,
                    },
                    opacity=0.95 if is_selected else 0.42,
                    name=f"{track.slot_id} · trajektoria",
                    hovertemplate=(
                        f"{track.slot_id}<br>"
                        "Azymut: %{theta:.1f}°<br>"
                        "Elewacja: %{customdata[0]:.1f}°<br>"
                        "Odległość: %{customdata[1]:.0f} km<extra></extra>"
                    ),
                    customdata=[
                        [sample.elevation_deg, sample.range_km]
                        for sample in visible
                    ],
                    showlegend=False,
                )
            )

        current = state_by_slot.get(track.slot_id)
        if current is None or current.topocentric.elevation_deg < minimum_elevation_deg:
            continue
        figure.add_trace(
            go.Scatterpolar(
                r=[90.0 - current.topocentric.elevation_deg],
                theta=[current.topocentric.azimuth_deg],
                mode="markers+text",
                text=[track.slot_id],
                textposition="top center",
                marker={
                    "size": 17 if is_selected else 10,
                    "color": _family_color(track.family),
                    "line": {
                        "color": "#f8fafc" if is_selected else "#0f172a",
                        "width": 2.2 if is_selected else 1.0,
                    },
                },
                name=track.slot_id,
                customdata=[
                    [
                        current.topocentric.elevation_deg,
                        current.topocentric.range_km,
                        current.object_name,
                    ]
                ],
                hovertemplate=(
                    "%{customdata[2]}<br>"
                    "Azymut: %{theta:.1f}°<br>"
                    "Elewacja: %{customdata[0]:.1f}°<br>"
                    "Odległość: %{customdata[1]:.0f} km<extra></extra>"
                ),
                showlegend=False,
            )
        )

    figure.update_layout(
        height=height_px,
        margin={"l": 35, "r": 35, "t": 55, "b": 35},
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        font={"color": "#e2e8f0"},
        title={"text": "Lokalna mapa nieba", "x": 0.5},
        polar={
            "bgcolor": "#0b1728",
            "radialaxis": {
                "range": [0, 90],
                "tickvals": [0, 15, 30, 45, 60, 75, 90],
                "ticktext": ["90°", "75°", "60°", "45°", "30°", "15°", "0°"],
                "gridcolor": GRID_COLOR,
                "linecolor": "rgba(226, 232, 240, 0.45)",
                "angle": 90,
                "title": {"text": "Elewacja"},
            },
            "angularaxis": {
                "direction": "clockwise",
                "rotation": 90,
                "tickmode": "array",
                "tickvals": [0, 45, 90, 135, 180, 225, 270, 315],
                "ticktext": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                "gridcolor": GRID_COLOR,
                "linecolor": "rgba(226, 232, 240, 0.45)",
            },
        },
        showlegend=False,
        template=None,
        uirevision="satplan-sky-map-v2",
    )
    if not figure.data:
        figure.add_annotation(
            text="Brak satelitów nad wybranym progiem elewacji",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 16, "color": "#cbd5e1"},
        )
    return figure


def _terminator_points(
    timestamp_utc: datetime,
    samples: int = 181,
) -> tuple[list[float | None], list[float | None]]:
    sun_eci = sun_unit_vector_eci(timestamp_utc)
    theta = gmst_radians(
        2451545.0 + (timestamp_utc.timestamp() - 946728000.0) / 86400.0
    )
    sun_ecef = (
        cos(theta) * sun_eci[0] + sin(theta) * sun_eci[1],
        -sin(theta) * sun_eci[0] + cos(theta) * sun_eci[1],
        sun_eci[2],
    )
    reference = (0.0, 0.0, 1.0)
    if abs(sun_ecef[2]) > 0.95:
        reference = (1.0, 0.0, 0.0)
    cross = (
        sun_ecef[1] * reference[2] - sun_ecef[2] * reference[1],
        sun_ecef[2] * reference[0] - sun_ecef[0] * reference[2],
        sun_ecef[0] * reference[1] - sun_ecef[1] * reference[0],
    )
    norm = sqrt(sum(value * value for value in cross))
    first = tuple(value / norm for value in cross)
    second = (
        sun_ecef[1] * first[2] - sun_ecef[2] * first[1],
        sun_ecef[2] * first[0] - sun_ecef[0] * first[2],
        sun_ecef[0] * first[1] - sun_ecef[1] * first[0],
    )
    longitudes: list[float] = []
    latitudes: list[float] = []
    for index in range(samples):
        angle = 2.0 * pi * index / (samples - 1)
        x = cos(angle) * first[0] + sin(angle) * second[0]
        y = cos(angle) * first[1] + sin(angle) * second[1]
        z = cos(angle) * first[2] + sin(angle) * second[2]
        longitude = (180.0 / pi) * atan2(y, x)
        latitude = (180.0 / pi) * asin(max(-1.0, min(1.0, z)))
        longitudes.append(longitude)
        latitudes.append(latitude)
    return _split_antimeridian(longitudes, latitudes)


def build_live_ground_map_figure(
    *,
    observer: ObserverSite,
    states: Sequence[LiveSatelliteState],
    tracks: Sequence[SatelliteGroundTrack],
    timestamp_utc: datetime,
    selected_slot_id: str | None = None,
    footprint_radius_km: float = 75.0,
    show_ground_tracks: bool = True,
    show_footprint: bool = True,
    show_terminator: bool = True,
    projection_type: str = "natural earth",
    height_px: int = 650,
) -> go.Figure:
    """Buduje globalną mapę aktualnych pozycji, śladów i footprintu."""

    figure = go.Figure()
    if show_ground_tracks:
        for track in tracks:
            is_selected = track.satellite.slot_id == selected_slot_id
            longitudes, latitudes = _split_antimeridian(
                [state.longitude_deg for state in track.states],
                [state.latitude_deg for state in track.states],
            )
            figure.add_trace(
                go.Scattergeo(
                    lon=longitudes,
                    lat=latitudes,
                    mode="lines",
                    line={
                        "color": _family_color(track.satellite.family),
                        "width": 3.0 if is_selected else 1.35,
                    },
                    opacity=0.92 if is_selected else 0.38,
                    name=f"{track.satellite.slot_id} · ground track",
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    if show_terminator:
        terminator_lon, terminator_lat = _terminator_points(timestamp_utc)
        figure.add_trace(
            go.Scattergeo(
                lon=terminator_lon,
                lat=terminator_lat,
                mode="lines",
                line={"color": TERMINATOR_COLOR, "width": 1.4, "dash": "dot"},
                name="Terminator",
                hoverinfo="skip",
                showlegend=False,
            )
        )

    figure.add_trace(
        go.Scattergeo(
            lon=[observer.longitude_deg],
            lat=[observer.latitude_deg],
            mode="markers+text",
            text=[observer.name],
            textposition="top center",
            marker={
                "size": 11,
                "color": OBSERVER_COLOR,
                "symbol": "diamond",
                "line": {"color": "#0f172a", "width": 1.2},
            },
            hovertemplate=(
                f"{observer.name}<br>"
                f"{observer.latitude_deg:.4f}°, {observer.longitude_deg:.4f}°"
                "<extra></extra>"
            ),
            showlegend=False,
        )
    )

    selected_state: LiveSatelliteState | None = None
    for state in states:
        if state.slot_id == selected_slot_id:
            selected_state = state
        figure.add_trace(
            go.Scattergeo(
                lon=[state.propagated.longitude_deg],
                lat=[state.propagated.latitude_deg],
                mode="markers+text",
                text=[state.slot_id],
                textposition="top center",
                marker={
                    "size": 12 if state.slot_id == selected_slot_id else 9,
                    "color": _family_color(state.family),
                    "line": {
                        "color": "#f8fafc" if state.slot_id == selected_slot_id else "#0f172a",
                        "width": 2 if state.slot_id == selected_slot_id else 1,
                    },
                },
                customdata=[
                    [
                        state.object_name,
                        state.propagated.altitude_km,
                        state.topocentric.elevation_deg,
                    ]
                ],
                hovertemplate=(
                    "%{customdata[0]}<br>"
                    "Pozycja: %{lat:.2f}°, %{lon:.2f}°<br>"
                    "Wysokość: %{customdata[1]:.0f} km<br>"
                    "Elewacja lokalna: %{customdata[2]:.1f}°<extra></extra>"
                ),
                showlegend=False,
            )
        )

    if show_footprint and selected_state is not None:
        footprint_lon, footprint_lat = spherical_circle(
            center_latitude_deg=selected_state.propagated.latitude_deg,
            center_longitude_deg=selected_state.propagated.longitude_deg,
            radius_km=footprint_radius_km,
        )
        split_lon, split_lat = _split_antimeridian(footprint_lon, footprint_lat)
        figure.add_trace(
            go.Scattergeo(
                lon=split_lon,
                lat=split_lat,
                mode="lines",
                line={"color": FOOTPRINT_COLOR, "width": 2.2},
                fill="toself" if all(value is not None for value in split_lon) else None,
                fillcolor="rgba(52, 211, 153, 0.10)",
                name="Referencyjny footprint",
                hovertemplate=(
                    f"Referencyjny promień footprintu: {footprint_radius_km:.0f} km"
                    "<extra></extra>"
                ),
                showlegend=False,
            )
        )

    if projection_type == "orthographic":
        center_longitude = (
            selected_state.propagated.longitude_deg
            if selected_state is not None
            else observer.longitude_deg
        )
        center_latitude = (
            selected_state.propagated.latitude_deg
            if selected_state is not None
            else observer.latitude_deg
        )
        projection = {
            "type": "orthographic",
            "rotation": {"lon": center_longitude, "lat": center_latitude},
            "scale": 1.2,
        }
    else:
        projection = {"type": "natural earth"}

    figure.update_geos(
        projection=projection,
        showland=True,
        landcolor=LAND_COLOR,
        showocean=True,
        oceancolor=OCEAN_COLOR,
        showlakes=True,
        lakecolor=OCEAN_COLOR,
        showcountries=True,
        countrycolor="rgba(203, 213, 225, 0.30)",
        showcoastlines=True,
        coastlinecolor="rgba(226, 232, 240, 0.36)",
        showframe=True,
        framecolor="rgba(148, 163, 184, 0.45)",
        bgcolor=BACKGROUND_COLOR,
        lonaxis={"showgrid": True, "gridcolor": GRID_COLOR, "dtick": 30},
        lataxis={"showgrid": True, "gridcolor": GRID_COLOR, "dtick": 15},
    )
    figure.update_layout(
        height=height_px,
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        paper_bgcolor=BACKGROUND_COLOR,
        font={"color": "#e2e8f0"},
        title={
            "text": (
                "Globus śledzący"
                if projection_type == "orthographic"
                else "Położenie i ślad naziemny"
            ),
            "x": 0.5,
        },
        showlegend=False,
        template=None,
        uirevision=f"satplan-ground-map-{projection_type}-v2",
    )
    return figure


__all__ = [
    "build_live_ground_map_figure",
    "build_sky_map_figure",
]
