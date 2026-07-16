from __future__ import annotations

from app.geospatial.aoi import geometry_bounds, geometry_centroid
from app.integrations.weather.models import WeatherLocation
from app.models.geometry import PointGeometry, PolygonGeometry, TargetGeometry


def _point_in_ring(
    longitude: float,
    latitude: float,
    ring: list[tuple[float, float]],
) -> bool:
    """Test ray-casting dla prostego pierścienia GeoJSON."""

    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous
        x2, y2 = current
        intersects = (y1 > latitude) != (y2 > latitude)
        if intersects:
            denominator = y2 - y1
            if abs(denominator) < 1e-15:
                previous = current
                continue
            crossing_longitude = (x2 - x1) * (latitude - y1) / denominator + x1
            if longitude < crossing_longitude:
                inside = not inside
        previous = current
    return inside


def _point_in_polygon(
    longitude: float,
    latitude: float,
    geometry: PolygonGeometry,
) -> bool:
    outer = geometry.coordinates[0]
    if not _point_in_ring(longitude, latitude, outer):
        return False
    return not any(
        _point_in_ring(longitude, latitude, inner)
        for inner in geometry.coordinates[1:]
    )


def _deduplicate(
    values: list[WeatherLocation],
    *,
    maximum: int,
) -> tuple[WeatherLocation, ...]:
    output: list[WeatherLocation] = []
    seen: set[tuple[float, float]] = set()
    for value in values:
        key = (round(value.longitude_deg, 6), round(value.latitude_deg, 6))
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
        if len(output) >= maximum:
            break
    return tuple(output)


def build_weather_sampling_locations(
    geometry: TargetGeometry,
    *,
    maximum_points: int = 9,
) -> tuple[WeatherLocation, ...]:
    """Buduje reprezentatywny zestaw punktów dla prognozy nad AOI."""

    if maximum_points < 1:
        raise ValueError("maximum_points musi być dodatnie")

    if isinstance(geometry, PointGeometry):
        longitude, latitude = geometry.coordinates
        return (
            WeatherLocation(
                location_id="AOI-POINT",
                longitude_deg=longitude,
                latitude_deg=latitude,
            ),
        )

    candidates: list[WeatherLocation] = []
    center_longitude, center_latitude = geometry_centroid(geometry)
    if _point_in_polygon(center_longitude, center_latitude, geometry):
        candidates.append(
            WeatherLocation(
                location_id="AOI-CENTROID",
                longitude_deg=center_longitude,
                latitude_deg=center_latitude,
            )
        )

    outer_vertices = geometry.coordinates[0][:-1]
    if outer_vertices:
        vertex_budget = min(4, len(outer_vertices))
        for index in range(vertex_budget):
            source_index = round(index * (len(outer_vertices) - 1) / max(1, vertex_budget - 1))
            longitude, latitude = outer_vertices[source_index]
            candidates.append(
                WeatherLocation(
                    location_id=f"AOI-VERTEX-{source_index + 1}",
                    longitude_deg=longitude,
                    latitude_deg=latitude,
                )
            )

    (south, west), (north, east) = geometry_bounds(geometry)
    longitudes = [west, (west + east) / 2.0, east]
    latitudes = [south, (south + north) / 2.0, north]
    for row_index, latitude in enumerate(latitudes, start=1):
        for column_index, longitude in enumerate(longitudes, start=1):
            if _point_in_polygon(longitude, latitude, geometry):
                candidates.append(
                    WeatherLocation(
                        location_id=f"AOI-GRID-{row_index}-{column_index}",
                        longitude_deg=longitude,
                        latitude_deg=latitude,
                    )
                )

    if not candidates:
        longitude, latitude = outer_vertices[0]
        candidates.append(
            WeatherLocation(
                location_id="AOI-FALLBACK",
                longitude_deg=longitude,
                latitude_deg=latitude,
            )
        )

    return _deduplicate(candidates, maximum=maximum_points)
