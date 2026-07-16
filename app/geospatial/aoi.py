from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.models.geometry import PointGeometry, PolygonGeometry, TargetGeometry


def _position(value: Sequence[Any]) -> tuple[float, float]:
    if len(value) < 2:
        raise ValueError("Pozycja GeoJSON musi zawierać longitude i latitude")
    return float(value[0]), float(value[1])


def _geometry_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    geojson_type = str(payload.get("type", ""))

    if geojson_type == "Feature":
        geometry = payload.get("geometry")
        if not isinstance(geometry, Mapping):
            raise ValueError("Feature nie zawiera poprawnej geometrii")
        return geometry

    if geojson_type == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list) or not features:
            raise ValueError("FeatureCollection nie zawiera obiektów")
        for feature in reversed(features):
            if not isinstance(feature, Mapping):
                continue
            geometry = feature.get("geometry")
            if isinstance(geometry, Mapping) and geometry.get("type") in {
                "Point",
                "Polygon",
            }:
                return geometry
        raise ValueError("FeatureCollection nie zawiera Point ani Polygon")

    return payload


def target_geometry_from_geojson(payload: Mapping[str, Any]) -> TargetGeometry:
    """Konwertuje Point/Polygon, Feature lub FeatureCollection na model AOI."""

    geometry = _geometry_payload(payload)
    geometry_type = str(geometry.get("type", ""))
    coordinates = geometry.get("coordinates")

    if geometry_type == "Point":
        if not isinstance(coordinates, Sequence):
            raise ValueError("Point nie zawiera poprawnych coordinates")
        return PointGeometry(coordinates=_position(coordinates))

    if geometry_type == "Polygon":
        if not isinstance(coordinates, Sequence) or not coordinates:
            raise ValueError("Polygon nie zawiera pierścieni")

        rings: list[list[tuple[float, float]]] = []
        for raw_ring in coordinates:
            if not isinstance(raw_ring, Sequence):
                raise ValueError("Niepoprawny pierścień Polygon")
            ring = [_position(position) for position in raw_ring]
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
            rings.append(ring)

        return PolygonGeometry(coordinates=rings)

    raise ValueError("Obsługiwane typy geometrii to Point i Polygon")


def target_geometry_to_feature(geometry: TargetGeometry) -> dict[str, Any]:
    """Zwraca zgodny z GeoJSON Feature bez właściwości domenowych."""

    return {
        "type": "Feature",
        "properties": {},
        "geometry": geometry.model_dump(mode="json"),
    }


def geometry_centroid(geometry: TargetGeometry) -> tuple[float, float]:
    """Wyznacza środek mapy; dla poligonu używa średniej wierzchołków."""

    if isinstance(geometry, PointGeometry):
        return geometry.coordinates

    ring = geometry.coordinates[0][:-1]
    longitude = sum(position[0] for position in ring) / len(ring)
    latitude = sum(position[1] for position in ring) / len(ring)
    return longitude, latitude


def geometry_bounds(
    geometry: TargetGeometry,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Zwraca granice jako ((south, west), (north, east))."""

    if isinstance(geometry, PointGeometry):
        longitude, latitude = geometry.coordinates
        return (latitude, longitude), (latitude, longitude)

    positions = [position for ring in geometry.coordinates for position in ring]
    longitudes = [position[0] for position in positions]
    latitudes = [position[1] for position in positions]
    return (
        (min(latitudes), min(longitudes)),
        (max(latitudes), max(longitudes)),
    )
