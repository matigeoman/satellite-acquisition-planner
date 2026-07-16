from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import cos, pi, sin
from typing import Iterable, Sequence

import plotly.graph_objects as go

from app.geospatial.aoi import geometry_centroid
from app.integrations.access.models import AccessCalculationResult
from app.integrations.orbits.models import (
    PropagatedState,
    SatelliteFamily,
    SatelliteGroundTrack,
)
from app.models.geometry import PointGeometry
from app.models.request import ObservationRequest
from app.services.contracts.planning import PlanningResult


EARTH_RADIUS_KM = 6371.0
SAR_COLOR = "#ff636a"
EO_COLOR = "#50a9ff"
AOI_COLOR = "#facc15"
ACCESS_COLOR = "#f59e0b"
SCHEDULE_COLOR = "#34d399"
GRID_COLOR = "rgba(148, 163, 184, 0.28)"
OCEAN_COLOR = "#071a2c"
LAND_COLOR = "#27445d"


@dataclass(frozen=True, slots=True)
class PlotlyGlobeScene:
    """Dwie niezależne wizualizacje oparte wyłącznie na Plotly."""

    operational_figure: go.Figure
    spatial_figure: go.Figure
    start_utc: datetime
    end_utc: datetime
    focus_utc: datetime
    satellite_count: int
    request_count: int
    access_window_count: int
    scheduled_acquisition_count: int


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Czas wizualizacji musi zawierać strefę czasową")
    return value.astimezone(timezone.utc)


def _family_color(family: SatelliteFamily) -> str:
    if family == SatelliteFamily.ICEYE:
        return SAR_COLOR
    return EO_COLOR


def _family_name(family: SatelliteFamily) -> str:
    if family == SatelliteFamily.ICEYE:
        return "ICEYE SAR"
    return "Pléiades Neo EO"


def _nearest_state(
    track: SatelliteGroundTrack,
    timestamp_utc: datetime,
) -> PropagatedState:
    if not track.states:
        raise ValueError(f"Ślad {track.satellite.slot_id} nie zawiera stanów")
    target = _utc(timestamp_utc)
    return min(
        track.states,
        key=lambda state: abs((_utc(state.timestamp_utc) - target).total_seconds()),
    )


def _split_antimeridian(
    longitudes: Sequence[float],
    latitudes: Sequence[float],
) -> tuple[list[float | None], list[float | None]]:
    if len(longitudes) != len(latitudes):
        raise ValueError("Długości i szerokości muszą mieć taki sam rozmiar")

    split_lon: list[float | None] = []
    split_lat: list[float | None] = []
    previous: float | None = None
    for longitude, latitude in zip(longitudes, latitudes, strict=True):
        if previous is not None and abs(longitude - previous) > 180.0:
            split_lon.append(None)
            split_lat.append(None)
        split_lon.append(float(longitude))
        split_lat.append(float(latitude))
        previous = float(longitude)
    return split_lon, split_lat


def _cartesian(
    longitude_deg: float,
    latitude_deg: float,
    altitude_km: float = 0.0,
) -> tuple[float, float, float]:
    longitude = longitude_deg * pi / 180.0
    latitude = latitude_deg * pi / 180.0
    radius = EARTH_RADIUS_KM + altitude_km
    cos_latitude = cos(latitude)
    return (
        radius * cos_latitude * cos(longitude),
        radius * cos_latitude * sin(longitude),
        radius * sin(latitude),
    )


def _graticule_geo_trace() -> go.Scattergeo:
    longitudes: list[float | None] = []
    latitudes: list[float | None] = []

    for latitude in range(-60, 61, 30):
        for longitude in range(-180, 181, 3):
            longitudes.append(float(longitude))
            latitudes.append(float(latitude))
        longitudes.append(None)
        latitudes.append(None)

    for longitude in range(-150, 181, 30):
        for latitude in range(-90, 91, 3):
            longitudes.append(float(longitude))
            latitudes.append(float(latitude))
        longitudes.append(None)
        latitudes.append(None)

    return go.Scattergeo(
        lon=longitudes,
        lat=latitudes,
        mode="lines",
        line={"color": GRID_COLOR, "width": 0.8},
        hoverinfo="skip",
        showlegend=False,
        name="Siatka geograficzna",
    )


def _sphere_surface() -> go.Surface:
    latitudes = [(-90.0 + index * 5.0) for index in range(37)]
    longitudes = [(-180.0 + index * 5.0) for index in range(73)]
    x_values: list[list[float]] = []
    y_values: list[list[float]] = []
    z_values: list[list[float]] = []
    surface_values: list[list[float]] = []

    for latitude in latitudes:
        x_row: list[float] = []
        y_row: list[float] = []
        z_row: list[float] = []
        surface_row: list[float] = []
        for longitude in longitudes:
            x, y, z = _cartesian(longitude, latitude)
            x_row.append(x)
            y_row.append(y)
            z_row.append(z)
            surface_row.append((latitude + 90.0) / 180.0)
        x_values.append(x_row)
        y_values.append(y_row)
        z_values.append(z_row)
        surface_values.append(surface_row)

    return go.Surface(
        x=x_values,
        y=y_values,
        z=z_values,
        surfacecolor=surface_values,
        colorscale=[
            [0.0, "#061a2b"],
            [0.45, "#0b3551"],
            [0.55, "#1f5a75"],
            [1.0, "#061a2b"],
        ],
        cmin=0.0,
        cmax=1.0,
        showscale=False,
        opacity=1.0,
        hoverinfo="skip",
        name="Ziemia",
        showlegend=False,
        lighting={
            "ambient": 0.82,
            "diffuse": 0.55,
            "roughness": 0.9,
            "specular": 0.08,
        },
    )


def _graticule_3d_trace() -> go.Scatter3d:
    x_values: list[float | None] = []
    y_values: list[float | None] = []
    z_values: list[float | None] = []
    altitude_km = 8.0

    for latitude in range(-60, 61, 30):
        for longitude in range(-180, 181, 3):
            x, y, z = _cartesian(longitude, latitude, altitude_km)
            x_values.append(x)
            y_values.append(y)
            z_values.append(z)
        x_values.append(None)
        y_values.append(None)
        z_values.append(None)

    for longitude in range(-150, 181, 30):
        for latitude in range(-90, 91, 3):
            x, y, z = _cartesian(longitude, latitude, altitude_km)
            x_values.append(x)
            y_values.append(y)
            z_values.append(z)
        x_values.append(None)
        y_values.append(None)
        z_values.append(None)

    return go.Scatter3d(
        x=x_values,
        y=y_values,
        z=z_values,
        mode="lines",
        line={"color": GRID_COLOR, "width": 2},
        hoverinfo="skip",
        showlegend=False,
        name="Siatka geograficzna",
    )


def _add_operational_tracks(
    figure: go.Figure,
    tracks: Sequence[SatelliteGroundTrack],
    focus_utc: datetime,
    *,
    show_ground_tracks: bool,
) -> None:
    for track in tracks:
        color = _family_color(track.satellite.family)
        family_name = _family_name(track.satellite.family)
        if show_ground_tracks:
            longitude_values = [state.longitude_deg for state in track.states]
            latitude_values = [state.latitude_deg for state in track.states]
            longitude_values, latitude_values = _split_antimeridian(
                longitude_values,
                latitude_values,
            )
            figure.add_trace(
                go.Scattergeo(
                    lon=longitude_values,
                    lat=latitude_values,
                    mode="lines",
                    line={"color": color, "width": 1.8},
                    opacity=0.68,
                    name=f"{track.satellite.slot_id} · ground track",
                    legendgroup=track.satellite.slot_id,
                    hoverinfo="skip",
                )
            )

        state = _nearest_state(track, focus_utc)
        figure.add_trace(
            go.Scattergeo(
                lon=[state.longitude_deg],
                lat=[state.latitude_deg],
                mode="markers+text",
                marker={
                    "size": 13,
                    "color": color,
                    "line": {"color": "white", "width": 1.5},
                    "symbol": "circle",
                },
                text=[track.satellite.slot_id],
                textposition="top center",
                textfont={"color": "white", "size": 13},
                customdata=[
                    [
                        family_name,
                        track.satellite.record.object_name,
                        track.satellite.record.norad_cat_id,
                        state.timestamp_utc.isoformat(),
                        state.altitude_km,
                    ]
                ],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "%{customdata[0]}<br>"
                    "Obiekt: %{customdata[1]}<br>"
                    "NORAD: %{customdata[2]}<br>"
                    "Czas: %{customdata[3]}<br>"
                    "Lat/Lon: %{lat:.3f}°, %{lon:.3f}°<br>"
                    "Wysokość: %{customdata[4]:.1f} km"
                    "<extra></extra>"
                ),
                name=f"{track.satellite.slot_id} · pozycja",
                legendgroup=track.satellite.slot_id,
                showlegend=False,
            )
        )


def _add_spatial_tracks(
    figure: go.Figure,
    tracks: Sequence[SatelliteGroundTrack],
    focus_utc: datetime,
    *,
    show_orbits_3d: bool,
) -> None:
    for track in tracks:
        color = _family_color(track.satellite.family)
        family_name = _family_name(track.satellite.family)
        if show_orbits_3d:
            coordinates = [
                _cartesian(
                    state.longitude_deg,
                    state.latitude_deg,
                    state.altitude_km,
                )
                for state in track.states
            ]
            figure.add_trace(
                go.Scatter3d(
                    x=[point[0] for point in coordinates],
                    y=[point[1] for point in coordinates],
                    z=[point[2] for point in coordinates],
                    mode="lines",
                    line={"color": color, "width": 5},
                    opacity=0.9,
                    name=f"{track.satellite.slot_id} · orbita",
                    legendgroup=track.satellite.slot_id,
                    hoverinfo="skip",
                )
            )

        state = _nearest_state(track, focus_utc)
        x, y, z = _cartesian(
            state.longitude_deg,
            state.latitude_deg,
            state.altitude_km,
        )
        figure.add_trace(
            go.Scatter3d(
                x=[x],
                y=[y],
                z=[z],
                mode="markers+text",
                marker={
                    "size": 7,
                    "color": color,
                    "line": {"color": "white", "width": 1},
                },
                text=[track.satellite.slot_id],
                textposition="top center",
                textfont={"color": "white", "size": 12},
                customdata=[
                    [
                        family_name,
                        state.timestamp_utc.isoformat(),
                        state.latitude_deg,
                        state.longitude_deg,
                        state.altitude_km,
                    ]
                ],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "%{customdata[0]}<br>"
                    "Czas: %{customdata[1]}<br>"
                    "Lat/Lon: %{customdata[2]:.3f}°, "
                    "%{customdata[3]:.3f}°<br>"
                    "Wysokość: %{customdata[4]:.1f} km"
                    "<extra></extra>"
                ),
                name=f"{track.satellite.slot_id} · pozycja 3D",
                legendgroup=track.satellite.slot_id,
                showlegend=False,
            )
        )


def _add_requests_geo(
    figure: go.Figure,
    requests: Iterable[ObservationRequest],
) -> int:
    count = 0
    for request in requests:
        count += 1
        if isinstance(request.geometry, PointGeometry):
            longitude, latitude = request.geometry.coordinates
            figure.add_trace(
                go.Scattergeo(
                    lon=[longitude],
                    lat=[latitude],
                    mode="markers+text",
                    marker={
                        "size": 14,
                        "color": AOI_COLOR,
                        "symbol": "diamond",
                        "line": {"color": "#111827", "width": 2},
                    },
                    text=[request.request_id],
                    textposition="bottom center",
                    textfont={"color": "white", "size": 12},
                    customdata=[[request.name, request.priority]],
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "%{customdata[0]}<br>"
                        "Priorytet: %{customdata[1]}<br>"
                        "Lat/Lon: %{lat:.4f}°, %{lon:.4f}°"
                        "<extra></extra>"
                    ),
                    name=f"AOI · {request.request_id}",
                    legendgroup="AOI",
                    showlegend=count == 1,
                )
            )
            continue

        ring = request.geometry.coordinates[0]
        figure.add_trace(
            go.Scattergeo(
                lon=[position[0] for position in ring],
                lat=[position[1] for position in ring],
                mode="lines",
                line={"color": AOI_COLOR, "width": 3},
                fill="toself",
                fillcolor="rgba(250, 204, 21, 0.20)",
                text=[request.request_id] * len(ring),
                customdata=[[request.name, request.priority]] * len(ring),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "%{customdata[0]}<br>"
                    "Priorytet: %{customdata[1]}"
                    "<extra></extra>"
                ),
                name=f"AOI · {request.request_id}",
                legendgroup="AOI",
                showlegend=count == 1,
            )
        )
    return count


def _add_requests_3d(
    figure: go.Figure,
    requests: Iterable[ObservationRequest],
) -> None:
    for request in requests:
        if isinstance(request.geometry, PointGeometry):
            longitude, latitude = request.geometry.coordinates
            x, y, z = _cartesian(longitude, latitude, 20.0)
            figure.add_trace(
                go.Scatter3d(
                    x=[x],
                    y=[y],
                    z=[z],
                    mode="markers",
                    marker={"size": 6, "color": AOI_COLOR, "symbol": "diamond"},
                    text=[request.request_id],
                    hovertemplate="<b>%{text}</b><extra></extra>",
                    name=f"AOI · {request.request_id}",
                    legendgroup="AOI-3D",
                    showlegend=False,
                )
            )
            continue

        ring = request.geometry.coordinates[0]
        coordinates = [
            _cartesian(longitude, latitude, 20.0)
            for longitude, latitude in ring
        ]
        figure.add_trace(
            go.Scatter3d(
                x=[point[0] for point in coordinates],
                y=[point[1] for point in coordinates],
                z=[point[2] for point in coordinates],
                mode="lines",
                line={"color": AOI_COLOR, "width": 6},
                hoverinfo="skip",
                name=f"AOI · {request.request_id}",
                legendgroup="AOI-3D",
                showlegend=False,
            )
        )


def _add_access_geo(
    figure: go.Figure,
    access_result: AccessCalculationResult | None,
) -> int:
    if access_result is None:
        return 0

    for index, window in enumerate(access_result.windows):
        longitudes = [point.satellite_longitude_deg for point in window.path]
        latitudes = [point.satellite_latitude_deg for point in window.path]
        longitudes, latitudes = _split_antimeridian(longitudes, latitudes)
        figure.add_trace(
            go.Scattergeo(
                lon=longitudes,
                lat=latitudes,
                mode="lines",
                line={"color": ACCESS_COLOR, "width": 5},
                opacity=0.95,
                customdata=[
                    [
                        window.window_id,
                        window.mode_name,
                        window.start_utc.isoformat(),
                        window.end_utc.isoformat(),
                    ]
                    for _ in longitudes
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Tryb: %{customdata[1]}<br>"
                    "Od: %{customdata[2]}<br>"
                    "Do: %{customdata[3]}"
                    "<extra></extra>"
                ),
                name="Okna dostępu",
                legendgroup="ACCESS",
                showlegend=index == 0,
            )
        )
    return len(access_result.windows)


def _add_access_3d(
    figure: go.Figure,
    access_result: AccessCalculationResult | None,
) -> None:
    if access_result is None:
        return

    for window in access_result.windows:
        coordinates = [
            _cartesian(
                point.satellite_longitude_deg,
                point.satellite_latitude_deg,
                point.satellite_altitude_km,
            )
            for point in window.path
        ]
        if not coordinates:
            continue
        figure.add_trace(
            go.Scatter3d(
                x=[point[0] for point in coordinates],
                y=[point[1] for point in coordinates],
                z=[point[2] for point in coordinates],
                mode="lines",
                line={"color": ACCESS_COLOR, "width": 8},
                hoverinfo="skip",
                name="Okna dostępu 3D",
                legendgroup="ACCESS-3D",
                showlegend=False,
            )
        )


def _add_schedule_layers(
    operational: go.Figure,
    spatial: go.Figure,
    tracks: Sequence[SatelliteGroundTrack],
    planning_result: PlanningResult | None,
) -> int:
    if planning_result is None:
        return 0

    track_by_id = {track.satellite.slot_id: track for track in tracks}
    opportunity_by_id = {
        opportunity.opportunity_id: opportunity
        for opportunity in planning_result.scenario.opportunity_set.opportunities
    }
    request_by_id = {
        request.request_id: request
        for request in planning_result.scenario.request_set.requests
    }

    active_entries = [
        entry for entry in planning_result.schedule.entries if entry.is_active
    ]
    for index, entry in enumerate(active_entries):
        request = request_by_id.get(entry.request_id)
        opportunity = opportunity_by_id.get(entry.opportunity_id)
        track = track_by_id.get(entry.satellite_id)
        if request is None or opportunity is None or track is None:
            continue

        midpoint = entry.start_utc + (entry.end_utc - entry.start_utc) / 2
        state = _nearest_state(track, midpoint)
        target_longitude, target_latitude = geometry_centroid(request.geometry)

        operational.add_trace(
            go.Scattergeo(
                lon=[state.longitude_deg, target_longitude],
                lat=[state.latitude_deg, target_latitude],
                mode="lines+markers",
                line={"color": SCHEDULE_COLOR, "width": 3, "dash": "dot"},
                marker={
                    "size": [7, 12],
                    "color": SCHEDULE_COLOR,
                    "symbol": ["circle", "star"],
                    "line": {"color": "white", "width": 1},
                },
                customdata=[
                    [entry.entry_id, entry.start_utc.isoformat(), entry.mode_id],
                    [entry.entry_id, entry.start_utc.isoformat(), entry.mode_id],
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Start: %{customdata[1]}<br>"
                    "Tryb: %{customdata[2]}"
                    "<extra></extra>"
                ),
                name="Akwizycje w planie",
                legendgroup="SCHEDULE",
                showlegend=index == 0,
            )
        )

        satellite_xyz = _cartesian(
            state.longitude_deg,
            state.latitude_deg,
            state.altitude_km,
        )
        target_xyz = _cartesian(target_longitude, target_latitude, 25.0)
        spatial.add_trace(
            go.Scatter3d(
                x=[satellite_xyz[0], target_xyz[0]],
                y=[satellite_xyz[1], target_xyz[1]],
                z=[satellite_xyz[2], target_xyz[2]],
                mode="lines+markers",
                line={"color": SCHEDULE_COLOR, "width": 7},
                marker={"size": [5, 7], "color": SCHEDULE_COLOR},
                hoverinfo="skip",
                name="Akwizycje w planie 3D",
                legendgroup="SCHEDULE-3D",
                showlegend=False,
            )
        )
    return len(active_entries)


def _configure_operational_figure(figure: go.Figure, height_px: int) -> None:
    figure.update_geos(
        projection={
            "type": "orthographic",
            "rotation": {"lon": 20, "lat": 45},
            "scale": 1.10,
        },
        showframe=True,
        framecolor="#64748b",
        framewidth=1.4,
        showland=True,
        landcolor=LAND_COLOR,
        showocean=True,
        oceancolor=OCEAN_COLOR,
        showlakes=True,
        lakecolor=OCEAN_COLOR,
        showcoastlines=True,
        coastlinecolor="#94a3b8",
        coastlinewidth=0.8,
        showcountries=True,
        countrycolor="#64748b",
        countrywidth=0.45,
        bgcolor="#050911",
        resolution=110,
        domain={"x": [0.0, 1.0], "y": [0.0, 1.0]},
    )
    figure.update_layout(
        height=height_px,
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        paper_bgcolor="#050911",
        plot_bgcolor="#050911",
        font={"color": "#e5edf6", "size": 13},
        showlegend=False,
        hoverlabel={
            "bgcolor": "#111827",
            "bordercolor": "#64748b",
            "font": {"color": "white", "size": 13},
        },
        uirevision="satplan-operational-globe-v2",
    )


def _configure_spatial_figure(figure: go.Figure, height_px: int) -> None:
    axis = {
        "visible": False,
        "showgrid": False,
        "zeroline": False,
        "showticklabels": False,
    }
    figure.update_layout(
        height=height_px,
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        paper_bgcolor="#050911",
        plot_bgcolor="#050911",
        font={"color": "#e5edf6", "size": 13},
        showlegend=False,
        scene={
            "xaxis": axis,
            "yaxis": axis,
            "zaxis": axis,
            "aspectmode": "data",
            "bgcolor": "#050911",
            "camera": {"eye": {"x": 1.55, "y": 1.55, "z": 1.05}},
            "uirevision": "satplan-spatial-camera-v2",
        },
        hoverlabel={
            "bgcolor": "#111827",
            "bordercolor": "#64748b",
            "font": {"color": "white", "size": 13},
        },
        uirevision="satplan-spatial-orbits-v2",
    )


def build_plotly_globe_scene(
    *,
    tracks: Sequence[SatelliteGroundTrack],
    requests: Iterable[ObservationRequest] = (),
    access_result: AccessCalculationResult | None = None,
    planning_result: PlanningResult | None = None,
    focus_utc: datetime | None = None,
    show_ground_tracks: bool = True,
    show_orbits_3d: bool = True,
    show_aoi: bool = True,
    show_access_windows: bool = True,
    show_schedule: bool = True,
    show_graticule: bool = True,
    height_px: int = 760,
) -> PlotlyGlobeScene:
    """Buduje stabilny globus 2D/3D bez Cesium, tokenów i usług kafelkowych."""

    normalized_tracks = tuple(tracks)
    if not normalized_tracks:
        raise ValueError("Wizualizacja wymaga co najmniej jednego śladu satelity")
    if any(not track.states for track in normalized_tracks):
        raise ValueError("Każdy ślad satelity musi zawierać stany")

    start_utc = min(_utc(track.states[0].timestamp_utc) for track in normalized_tracks)
    end_utc = max(_utc(track.states[-1].timestamp_utc) for track in normalized_tracks)
    if focus_utc is None:
        focus_utc = start_utc
    focus_utc = min(max(_utc(focus_utc), start_utc), end_utc)
    normalized_requests = tuple(requests)

    operational = go.Figure()
    spatial = go.Figure()
    if show_graticule:
        operational.add_trace(_graticule_geo_trace())
    spatial.add_trace(_sphere_surface())
    if show_graticule:
        spatial.add_trace(_graticule_3d_trace())

    _add_operational_tracks(
        operational,
        normalized_tracks,
        focus_utc,
        show_ground_tracks=show_ground_tracks,
    )
    _add_spatial_tracks(
        spatial,
        normalized_tracks,
        focus_utc,
        show_orbits_3d=show_orbits_3d,
    )

    request_count = 0
    if show_aoi:
        request_count = _add_requests_geo(operational, normalized_requests)
        _add_requests_3d(spatial, normalized_requests)

    access_count = 0
    if show_access_windows:
        access_count = _add_access_geo(operational, access_result)
        _add_access_3d(spatial, access_result)

    schedule_count = 0
    if show_schedule:
        schedule_count = _add_schedule_layers(
            operational,
            spatial,
            normalized_tracks,
            planning_result,
        )

    _configure_operational_figure(operational, height_px)
    _configure_spatial_figure(spatial, height_px)

    return PlotlyGlobeScene(
        operational_figure=operational,
        spatial_figure=spatial,
        start_utc=start_utc,
        end_utc=end_utc,
        focus_utc=focus_utc,
        satellite_count=len(normalized_tracks),
        request_count=request_count,
        access_window_count=access_count,
        scheduled_acquisition_count=schedule_count,
    )
