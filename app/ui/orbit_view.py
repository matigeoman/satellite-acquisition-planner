from __future__ import annotations

from collections.abc import Iterable

import plotly.graph_objects as go

from app.integrations.orbits import SatelliteGroundTrack


def _split_dateline(
    longitudes: Iterable[float],
    latitudes: Iterable[float],
) -> tuple[list[float | None], list[float | None]]:
    """Wstawia przerwy, aby linia nie przecinała mapy przy ±180°."""

    output_lon: list[float | None] = []
    output_lat: list[float | None] = []
    previous: float | None = None
    for longitude, latitude in zip(longitudes, latitudes):
        if previous is not None and abs(longitude - previous) > 180.0:
            output_lon.append(None)
            output_lat.append(None)
        output_lon.append(longitude)
        output_lat.append(latitude)
        previous = longitude
    return output_lon, output_lat


def build_ground_track_figure(
    tracks: Iterable[SatelliteGroundTrack],
) -> go.Figure:
    """Buduje czytelną mapę 2D śladów naziemnych sześciu satelitów."""

    figure = go.Figure()
    for track in tracks:
        if not track.states:
            continue
        longitudes, latitudes = _split_dateline(
            (state.longitude_deg for state in track.states),
            (state.latitude_deg for state in track.states),
        )
        label = (
            f"{track.satellite.slot_id} — "
            f"{track.satellite.record.object_name}"
        )
        figure.add_trace(
            go.Scattergeo(
                lon=longitudes,
                lat=latitudes,
                mode="lines",
                name=label,
                line={"width": 2.5},
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "Szerokość: %{lat:.3f}°<br>"
                    "Długość: %{lon:.3f}°<extra></extra>"
                ),
            )
        )
        first = track.states[0]
        figure.add_trace(
            go.Scattergeo(
                lon=[first.longitude_deg],
                lat=[first.latitude_deg],
                mode="markers+text",
                name=f"Pozycja {track.satellite.slot_id}",
                text=[track.satellite.slot_id],
                textposition="top center",
                marker={"size": 13, "symbol": "circle"},
                showlegend=False,
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    f"Czas: {first.timestamp_utc.isoformat()}<br>"
                    f"Wysokość: {first.altitude_km:.1f} km<extra></extra>"
                ),
            )
        )

    figure.update_geos(
        projection_type="natural earth",
        showland=True,
        showocean=True,
        showcountries=True,
        showcoastlines=True,
        lataxis={"showgrid": True, "dtick": 30},
        lonaxis={"showgrid": True, "dtick": 30},
    )
    figure.update_layout(
        height=760,
        margin={"l": 0, "r": 0, "t": 25, "b": 0},
        legend={"orientation": "h", "y": -0.08},
        hoverlabel={"font_size": 17},
    )
    return figure
