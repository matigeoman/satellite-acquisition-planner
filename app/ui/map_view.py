from __future__ import annotations

from collections.abc import Iterable, Sequence
from html import escape
from math import log2
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from app.services.planning_service import PlanningResult
from app.ui.dataframes import build_request_status_dataframe


MAP_COLUMNS = [
    "request_id",
    "name",
    "geometry_type",
    "priority",
    "is_mandatory",
    "request_mode",
    "requested_sensor_types",
    "fulfillment_status",
    "scheduled_entry_count",
    "feasible_opportunity_count",
    "centroid_lon",
    "centroid_lat",
    "coordinates",
]

STATUS_STYLES = {
    "FULLY_SATISFIED": {
        "label": "W pełni zrealizowane",
        "color": "#16A34A",
    },
    "PARTIALLY_SATISFIED": {
        "label": "Częściowo zrealizowane",
        "color": "#F59E0B",
    },
    "UNASSIGNED": {
        "label": "Niezrealizowane",
        "color": "#DC2626",
    },
}


def build_request_map_dataframe(
    result: PlanningResult,
) -> pd.DataFrame:
    """Buduje dane geograficzne wszystkich aktywnych zleceń."""

    status_dataframe = build_request_status_dataframe(
        result
    )

    status_by_request = {
        row["request_id"]: row
        for row in status_dataframe.to_dict(
            orient="records"
        )
    }

    rows: list[dict[str, Any]] = []

    for request in sorted(
        result.scenario.request_set.active_requests,
        key=lambda item: item.request_id,
    ):
        try:
            status_row = status_by_request[
                request.request_id
            ]
        except KeyError as error:
            raise KeyError(
                "Brak statusu realizacji zlecenia: "
                f"{request.request_id}"
            ) from error

        geometry_payload = _geometry_payload(
            request.geometry
        )

        (
            geometry_type,
            coordinates,
            centroid_lon,
            centroid_lat,
        ) = _normalize_geometry(
            geometry_payload
        )

        requested_sensor_types = sorted(
            _enum_value(sensor_type)
            for sensor_type
            in request.requested_sensor_types
        )

        rows.append(
            {
                "request_id": request.request_id,
                "name": request.name,
                "geometry_type": geometry_type,
                "priority": request.priority,
                "is_mandatory": request.is_mandatory,
                "request_mode": _enum_value(
                    request.request_mode
                ),
                "requested_sensor_types": "|".join(
                    requested_sensor_types
                ),
                "fulfillment_status": status_row[
                    "fulfillment_status"
                ],
                "scheduled_entry_count": int(
                    status_row[
                        "scheduled_entry_count"
                    ]
                ),
                "feasible_opportunity_count": int(
                    status_row[
                        "feasible_opportunity_count"
                    ]
                ),
                "centroid_lon": centroid_lon,
                "centroid_lat": centroid_lat,
                "coordinates": coordinates,
            }
        )

    return pd.DataFrame(
        rows,
        columns=MAP_COLUMNS,
    )


def build_request_map_figure(
    result: PlanningResult,
    *,
    fulfillment_statuses: Iterable[str] | None = None,
    geometry_types: Iterable[str] | None = None,
    mandatory_only: bool = False,
) -> go.Figure:
    """
    Buduje interaktywną mapę geometrii Point i Polygon.

    Mapa używa płaskiego układu Web Mercator. Dzięki temu poligony
    są wypełniane lokalnie, zamiast obejmować dopełnienie obszaru
    na projekcji globu.
    """

    dataframe = build_request_map_dataframe(
        result
    )

    if fulfillment_statuses is not None:
        selected_statuses = {
            str(status).strip().upper()
            for status in fulfillment_statuses
        }

        dataframe = dataframe.loc[
            dataframe["fulfillment_status"].isin(
                selected_statuses
            )
        ]

    if geometry_types is not None:
        selected_geometry_types = {
            str(geometry_type).strip().upper()
            for geometry_type in geometry_types
        }

        dataframe = dataframe.loc[
            dataframe["geometry_type"].isin(
                selected_geometry_types
            )
        ]

    if mandatory_only:
        dataframe = dataframe.loc[
            dataframe["is_mandatory"]
        ]

    dataframe = dataframe.reset_index(
        drop=True
    )

    if dataframe.empty:
        return _build_empty_map_figure()

    figure = go.Figure()
    statuses_in_legend: set[str] = set()

    for status, style in STATUS_STYLES.items():
        status_dataframe = dataframe.loc[
            dataframe["fulfillment_status"]
            == status
        ]

        if status_dataframe.empty:
            continue

        point_dataframe = status_dataframe.loc[
            status_dataframe["geometry_type"]
            == "POINT"
        ]

        for is_mandatory, marker_size in (
            (False, 12),
            (True, 18),
        ):
            selected_points = point_dataframe.loc[
                point_dataframe["is_mandatory"]
                == is_mandatory
            ]

            if selected_points.empty:
                continue

            show_legend = (
                status not in statuses_in_legend
            )

            figure.add_trace(
                go.Scattermap(
                    lon=selected_points[
                        "centroid_lon"
                    ],
                    lat=selected_points[
                        "centroid_lat"
                    ],
                    mode="markers",
                    name=style["label"],
                    legendgroup=status,
                    showlegend=show_legend,
                    marker={
                        "size": marker_size,
                        "symbol": "circle",
                        "color": style["color"],
                        "opacity": 0.92,
                        "allowoverlap": True,
                    },
                    hovertext=[
                        _build_hover_text(row)
                        for row
                        in selected_points.to_dict(
                            orient="records"
                        )
                    ],
                    hoverinfo="text",
                )
            )

            statuses_in_legend.add(
                status
            )

        polygon_dataframe = status_dataframe.loc[
            status_dataframe["geometry_type"]
            == "POLYGON"
        ]

        for row in polygon_dataframe.to_dict(
            orient="records"
        ):
            outer_ring = row[
                "coordinates"
            ]

            show_legend = (
                status not in statuses_in_legend
            )

            figure.add_trace(
                go.Scattermap(
                    lon=[
                        position[0]
                        for position in outer_ring
                    ],
                    lat=[
                        position[1]
                        for position in outer_ring
                    ],
                    mode="lines",
                    fill="toself",
                    fillcolor=_with_alpha(
                        style["color"],
                        0.18,
                    ),
                    line={
                        "color": style["color"],
                        "width": (
                            4
                            if row["is_mandatory"]
                            else 2
                        ),
                    },
                    name=style["label"],
                    legendgroup=status,
                    showlegend=show_legend,
                    hovertext=[
                        _build_hover_text(row)
                        for _ in outer_ring
                    ],
                    hoverinfo="text",
                )
            )

            statuses_in_legend.add(
                status
            )

    center, zoom = _calculate_map_view(
        dataframe
    )

    point_count = int(
        (
            dataframe["geometry_type"]
            == "POINT"
        ).sum()
    )

    polygon_count = int(
        (
            dataframe["geometry_type"]
            == "POLYGON"
        ).sum()
    )

    figure.update_layout(
        height=650,
        hovermode="closest",
        dragmode="pan",
        uirevision=(
            "request-map-"
            f"{result.schedule.schedule_id}"
        ),
        map={
            "style": "carto-positron",
            "center": center,
            "zoom": zoom,
            "bearing": 0,
            "pitch": 0,
        },
        legend={
            "title": {
                "text": "Status realizacji",
            },
            "orientation": "h",
            "yanchor": "top",
            "y": -0.04,
            "xanchor": "center",
            "x": 0.5,
        },
        margin={
            "l": 0,
            "r": 0,
            "t": 10,
            "b": 80,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        meta={
            "request_count": len(
                dataframe
            ),
            "point_count": point_count,
            "polygon_count": polygon_count,
        },
    )

    return figure


def _geometry_payload(
    geometry: Any,
) -> dict[str, Any]:
    if hasattr(
        geometry,
        "model_dump",
    ):
        payload = geometry.model_dump(
            mode="json"
        )
    elif isinstance(
        geometry,
        dict,
    ):
        payload = geometry
    else:
        raise TypeError(
            "Geometria musi być modelem Pydantic "
            "albo słownikiem GeoJSON"
        )

    if not isinstance(
        payload,
        dict,
    ):
        raise TypeError(
            "Zserializowana geometria musi być słownikiem"
        )

    return payload


def _normalize_geometry(
    payload: dict[str, Any],
) -> tuple[
    str,
    list[float] | list[list[float]],
    float,
    float,
]:
    geometry_type = str(
        payload.get(
            "type",
            "",
        )
    ).strip().upper()

    coordinates = payload.get(
        "coordinates"
    )

    if geometry_type == "POINT":
        point = _normalize_position(
            coordinates
        )

        return (
            geometry_type,
            point,
            point[0],
            point[1],
        )

    if geometry_type == "POLYGON":
        if (
            not isinstance(
                coordinates,
                Sequence,
            )
            or isinstance(
                coordinates,
                (str, bytes),
            )
            or not coordinates
        ):
            raise ValueError(
                "Polygon musi zawierać co najmniej jeden pierścień"
            )

        outer_ring_raw = coordinates[0]

        if (
            not isinstance(
                outer_ring_raw,
                Sequence,
            )
            or isinstance(
                outer_ring_raw,
                (str, bytes),
            )
        ):
            raise ValueError(
                "Zewnętrzny pierścień Polygon jest niepoprawny"
            )

        outer_ring = [
            _normalize_position(
                position
            )
            for position in outer_ring_raw
        ]

        if len(outer_ring) < 4:
            raise ValueError(
                "Pierścień Polygon wymaga co najmniej czterech pozycji"
            )

        outer_ring = _close_ring(
            outer_ring
        )

        outer_ring = _ensure_counterclockwise_ring(
            outer_ring
        )

        centroid_lon, centroid_lat = (
            _polygon_centroid(
                outer_ring
            )
        )

        return (
            geometry_type,
            outer_ring,
            centroid_lon,
            centroid_lat,
        )

    raise ValueError(
        "Obsługiwane geometrie to Point i Polygon, "
        f"otrzymano: {geometry_type or '<brak>'}"
    )


def _normalize_position(
    value: Any,
) -> list[float]:
    if (
        not isinstance(
            value,
            Sequence,
        )
        or isinstance(
            value,
            (str, bytes),
        )
        or len(value) < 2
    ):
        raise ValueError(
            "Pozycja geograficzna musi zawierać longitude i latitude"
        )

    longitude = float(
        value[0]
    )

    latitude = float(
        value[1]
    )

    if not -180.0 <= longitude <= 180.0:
        raise ValueError(
            "Longitude musi należeć do zakresu [-180, 180]"
        )

    if not -90.0 <= latitude <= 90.0:
        raise ValueError(
            "Latitude musi należeć do zakresu [-90, 90]"
        )

    return [
        longitude,
        latitude,
    ]


def _close_ring(
    ring: list[list[float]],
) -> list[list[float]]:
    closed_ring = [
        list(position)
        for position in ring
    ]

    if closed_ring[0] != closed_ring[-1]:
        closed_ring.append(
            list(
                closed_ring[0]
            )
        )

    return closed_ring


def _ensure_counterclockwise_ring(
    ring: list[list[float]],
) -> list[list[float]]:
    """
    Normalizuje kierunek zewnętrznego pierścienia.

    Dodatnie pole skierowane oznacza kolejność przeciwną
    do ruchu wskazówek zegara.
    """

    closed_ring = _close_ring(
        ring
    )

    if _ring_signed_area(
        closed_ring
    ) >= 0.0:
        return closed_ring

    reversed_vertices = list(
        reversed(
            closed_ring[:-1]
        )
    )

    return _close_ring(
        reversed_vertices
    )


def _ring_signed_area(
    ring: Sequence[Sequence[float]],
) -> float:
    closed_ring = (
        list(ring)
        if ring[0] == ring[-1]
        else [
            *ring,
            ring[0],
        ]
    )

    return 0.5 * sum(
        (
            current[0]
            * following[1]
            - following[0]
            * current[1]
        )
        for current, following in zip(
            closed_ring[:-1],
            closed_ring[1:],
            strict=True,
        )
    )


def _polygon_centroid(
    ring: Sequence[Sequence[float]],
) -> tuple[float, float]:
    vertices = list(
        ring[:-1]
        if ring[0] == ring[-1]
        else ring
    )

    if len(vertices) < 3:
        raise ValueError(
            "Centroid wymaga co najmniej trzech wierzchołków"
        )

    twice_area = 0.0
    longitude_sum = 0.0
    latitude_sum = 0.0

    for index, current in enumerate(
        vertices
    ):
        following = vertices[
            (index + 1)
            % len(vertices)
        ]

        cross_product = (
            current[0]
            * following[1]
            - following[0]
            * current[1]
        )

        twice_area += cross_product

        longitude_sum += (
            current[0]
            + following[0]
        ) * cross_product

        latitude_sum += (
            current[1]
            + following[1]
        ) * cross_product

    if abs(twice_area) < 1e-12:
        return (
            sum(
                vertex[0]
                for vertex in vertices
            )
            / len(vertices),
            sum(
                vertex[1]
                for vertex in vertices
            )
            / len(vertices),
        )

    return (
        longitude_sum
        / (3.0 * twice_area),
        latitude_sum
        / (3.0 * twice_area),
    )


def _calculate_map_view(
    dataframe: pd.DataFrame,
) -> tuple[dict[str, float], float]:
    longitudes: list[float] = []
    latitudes: list[float] = []

    for row in dataframe.to_dict(
        orient="records"
    ):
        if row["geometry_type"] == "POINT":
            longitudes.append(
                float(
                    row["coordinates"][0]
                )
            )
            latitudes.append(
                float(
                    row["coordinates"][1]
                )
            )
        else:
            longitudes.extend(
                float(position[0])
                for position
                in row["coordinates"]
            )
            latitudes.extend(
                float(position[1])
                for position
                in row["coordinates"]
            )

    minimum_longitude = min(
        longitudes
    )
    maximum_longitude = max(
        longitudes
    )
    minimum_latitude = min(
        latitudes
    )
    maximum_latitude = max(
        latitudes
    )

    center = {
        "lon": (
            minimum_longitude
            + maximum_longitude
        )
        / 2.0,
        "lat": (
            minimum_latitude
            + maximum_latitude
        )
        / 2.0,
    }

    longitude_span = max(
        (
            maximum_longitude
            - minimum_longitude
        )
        * 1.35,
        0.35,
    )

    latitude_span = max(
        (
            maximum_latitude
            - minimum_latitude
        )
        * 1.35,
        0.25,
    )

    longitude_zoom = (
        log2(
            360.0
            / longitude_span
        )
        - 1.0
    )

    latitude_zoom = (
        log2(
            170.0
            / latitude_span
        )
        - 1.0
    )

    zoom = min(
        longitude_zoom,
        latitude_zoom,
    )

    zoom = max(
        3.0,
        min(
            11.0,
            zoom,
        ),
    )

    return (
        center,
        round(
            zoom,
            3,
        ),
    )


def _build_hover_text(
    row: dict[str, Any],
) -> str:
    mandatory_label = (
        "tak"
        if row["is_mandatory"]
        else "nie"
    )

    status_label = STATUS_STYLES.get(
        row["fulfillment_status"],
        {
            "label": row[
                "fulfillment_status"
            ]
        },
    )["label"]

    return (
        f"<b>{escape(str(row['request_id']))}</b><br>"
        f"{escape(str(row['name']))}<br>"
        f"Status: {escape(str(status_label))}<br>"
        f"Geometria: {escape(str(row['geometry_type']))}<br>"
        f"Tryb: {escape(str(row['request_mode']))}<br>"
        f"Sensory: {escape(str(row['requested_sensor_types']))}<br>"
        f"Priorytet: {int(row['priority'])}<br>"
        f"Obowiązkowe: {mandatory_label}<br>"
        "Zaplanowane akwizycje: "
        f"{int(row['scheduled_entry_count'])}<br>"
        "Wykonalne okazje: "
        f"{int(row['feasible_opportunity_count'])}"
    )


def _with_alpha(
    hex_color: str,
    alpha: float,
) -> str:
    normalized = hex_color.lstrip(
        "#"
    )

    if len(normalized) != 6:
        raise ValueError(
            "Kolor musi mieć format #RRGGBB"
        )

    if not 0.0 <= alpha <= 1.0:
        raise ValueError(
            "alpha musi należeć do zakresu [0, 1]"
        )

    red = int(
        normalized[0:2],
        16,
    )
    green = int(
        normalized[2:4],
        16,
    )
    blue = int(
        normalized[4:6],
        16,
    )

    return (
        f"rgba({red}, {green}, {blue}, "
        f"{alpha})"
    )


def _build_empty_map_figure() -> go.Figure:
    figure = go.Figure()

    figure.add_annotation(
        text=(
            "Brak zleceń spełniających "
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

    figure.update_layout(
        height=520,
        map={
            "style": "carto-positron",
            "center": {
                "lon": 19.0,
                "lat": 52.0,
            },
            "zoom": 4.5,
        },
        margin={
            "l": 0,
            "r": 0,
            "t": 10,
            "b": 10,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        meta={
            "request_count": 0,
            "point_count": 0,
            "polygon_count": 0,
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
