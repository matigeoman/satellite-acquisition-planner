from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

import plotly.graph_objects as go

from app.integrations.orbits import SatelliteFamily, SatelliteGroundTrack


_SAR_COLORS = ("#4cc9f0", "#4895ef", "#4361ee", "#3a0ca3")
_EO_COLORS = ("#ffb703", "#fb8500")


def _track_color(track: SatelliteGroundTrack, family_index: int) -> str:
    palette = (
        _SAR_COLORS
        if track.satellite.family == SatelliteFamily.ICEYE
        else _EO_COLORS
    )
    return palette[family_index % len(palette)]


def _split_dateline_values(
    longitudes: Iterable[float],
    latitudes: Iterable[float],
    customdata: Iterable[tuple[str, float]],
) -> tuple[
    list[float | None],
    list[float | None],
    list[tuple[str, float] | None],
]:
    output_lon: list[float | None] = []
    output_lat: list[float | None] = []
    output_data: list[tuple[str, float] | None] = []
    previous: float | None = None
    for longitude, latitude, data in zip(longitudes, latitudes, customdata):
        if previous is not None and abs(longitude - previous) > 180.0:
            output_lon.append(None)
            output_lat.append(None)
            output_data.append(None)
        output_lon.append(longitude)
        output_lat.append(latitude)
        output_data.append(data)
        previous = longitude
    return output_lon, output_lat, output_data


def _split_dateline(
    longitudes: Iterable[float],
    latitudes: Iterable[float],
) -> tuple[list[float | None], list[float | None]]:
    """Wstawia przerwy, aby linia nie przecinała mapy przy ±180°."""

    longitude_values = list(longitudes)
    latitude_values = list(latitudes)
    data = [("", 0.0)] * len(longitude_values)
    output_lon, output_lat, _output_data = _split_dateline_values(
        longitude_values,
        latitude_values,
        data,
    )
    return output_lon, output_lat


def _format_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def build_ground_track_figure(
    tracks: Iterable[SatelliteGroundTrack],
    *,
    visible_slot_ids: set[str] | None = None,
) -> go.Figure:
    """Buduje interaktywną mapę śladów naziemnych na ciemnym podkładzie."""

    figure = go.Figure()
    family_counts = {
        SatelliteFamily.ICEYE: 0,
        SatelliteFamily.PLEIADES_NEO: 0,
    }
    displayed_tracks = [
        track
        for track in tracks
        if track.states
        and (
            visible_slot_ids is None
            or track.satellite.slot_id in visible_slot_ids
        )
    ]

    for track in displayed_tracks:
        family_index = family_counts[track.satellite.family]
        family_counts[track.satellite.family] += 1
        color = _track_color(track, family_index)
        label = (
            f"{track.satellite.slot_id} — "
            f"{track.satellite.record.object_name}"
        )
        longitudes, latitudes, customdata = _split_dateline_values(
            (state.longitude_deg for state in track.states),
            (state.latitude_deg for state in track.states),
            (
                (_format_time(state.timestamp_utc), state.altitude_km)
                for state in track.states
            ),
        )
        figure.add_trace(
            go.Scattermap(
                lon=longitudes,
                lat=latitudes,
                customdata=customdata,
                mode="lines",
                name=label,
                line={"width": 3.3, "color": color},
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "Czas: %{customdata[0]}<br>"
                    "Szerokość: %{lat:.3f}°<br>"
                    "Długość: %{lon:.3f}°<br>"
                    "Wysokość: %{customdata[1]:.1f} km<extra></extra>"
                ),
            )
        )
        first = track.states[0]
        figure.add_trace(
            go.Scattermap(
                lon=[first.longitude_deg],
                lat=[first.latitude_deg],
                mode="markers",
                name=f"Pozycja {track.satellite.slot_id}",
                marker={
                    "size": 16,
                    "color": color,
                },
                showlegend=False,
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    f"Czas: {_format_time(first.timestamp_utc)}<br>"
                    f"Wysokość: {first.altitude_km:.1f} km<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        height=610,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        map={
            "style": "carto-darkmatter",
            "center": {"lat": 10.0, "lon": 15.0},
            "zoom": 0.55,
        },
        legend={
            "orientation": "v",
            "x": 0.012,
            "y": 0.985,
            "xanchor": "left",
            "yanchor": "top",
            "bgcolor": "rgba(8, 13, 22, 0.84)",
            "bordercolor": "rgba(255,255,255,0.24)",
            "borderwidth": 1,
            "font": {"size": 14, "color": "#f4f7fb"},
        },
        hoverlabel={
            "font_size": 15,
            "bgcolor": "#101722",
            "bordercolor": "#6f7d90",
        },
        uirevision="public-orbit-map-v2",
    )
    return figure
