from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

import plotly.graph_objects as go

from app.integrations.orbits import SatelliteFamily, SatelliteGroundTrack


_SAR_COLORS = ("#4cc9f0", "#4895ef", "#4361ee", "#3a0ca3")
_EO_COLORS = ("#ffb703", "#fb8500")
_BACKGROUND_COLOR = "#07111f"
_OCEAN_COLOR = "#071827"
_LAND_COLOR = "#2b4050"
_GRID_COLOR = "rgba(148, 163, 184, 0.24)"


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
        output_lon.append(float(longitude))
        output_lat.append(float(latitude))
        output_data.append(data)
        previous = float(longitude)
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
    """Buduje mapę śladów naziemnych ograniczoną do jednego świata."""

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
            go.Scattergeo(
                lon=longitudes,
                lat=latitudes,
                customdata=customdata,
                mode="lines",
                # Krótka nazwa zapobiega obcinaniu poziomej legendy.
                # Pełna nazwa obiektu pozostaje w dymku po najechaniu.
                name=track.satellite.slot_id,
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
            go.Scattergeo(
                lon=[first.longitude_deg],
                lat=[first.latitude_deg],
                mode="markers",
                name=f"Pozycja {track.satellite.slot_id}",
                marker={
                    "size": 12,
                    "color": color,
                    "line": {"color": "#f8fafc", "width": 1.0},
                },
                showlegend=False,
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    f"Czas: {_format_time(first.timestamp_utc)}<br>"
                    f"Wysokość: {first.altitude_km:.1f} km<extra></extra>"
                ),
            )
        )

    figure.update_geos(
        projection={"type": "equirectangular"},
        resolution=50,
        showland=True,
        landcolor=_LAND_COLOR,
        showocean=True,
        oceancolor=_OCEAN_COLOR,
        showlakes=True,
        lakecolor=_OCEAN_COLOR,
        showcountries=True,
        countrycolor="rgba(203, 213, 225, 0.28)",
        showcoastlines=True,
        coastlinecolor="rgba(226, 232, 240, 0.36)",
        showframe=True,
        framecolor="rgba(148, 163, 184, 0.45)",
        bgcolor=_BACKGROUND_COLOR,
        lonaxis={
            "range": [-180.0, 180.0],
            "showgrid": True,
            "gridcolor": _GRID_COLOR,
            "dtick": 30,
        },
        lataxis={
            "range": [-90.0, 90.0],
            "showgrid": True,
            "gridcolor": _GRID_COLOR,
            "dtick": 15,
        },
    )
    figure.update_layout(
        height=660,
        margin={"l": 8, "r": 8, "t": 76, "b": 8},
        paper_bgcolor=_BACKGROUND_COLOR,
        plot_bgcolor=_BACKGROUND_COLOR,
        font={"color": "#f4f7fb"},
        legend={
            "orientation": "h",
            "x": 0.5,
            "y": 1.035,
            "xanchor": "center",
            "yanchor": "bottom",
            "bgcolor": "rgba(8, 13, 22, 0.90)",
            "bordercolor": "rgba(255,255,255,0.24)",
            "borderwidth": 1,
            "font": {"size": 12, "color": "#f4f7fb"},
        },
        hoverlabel={
            "font_size": 15,
            "bgcolor": "#101722",
            "bordercolor": "#6f7d90",
        },
        uirevision="public-orbit-geo-v5",
    )
    return figure
