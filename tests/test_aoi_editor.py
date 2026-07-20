import pytest

from app.models.geometry import PointGeometry, PolygonGeometry
from app.geospatial.aoi import (
    geometry_bounds,
    geometry_centroid,
    target_geometry_from_geojson,
    target_geometry_to_feature,
)


def test_point_feature_is_converted_to_domain_geometry() -> None:
    geometry = target_geometry_from_geojson(
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Point",
                "coordinates": [21.0122, 52.2297],
            },
        }
    )

    assert geometry == PointGeometry(coordinates=(21.0122, 52.2297))


def test_polygon_ring_is_closed_automatically() -> None:
    geometry = target_geometry_from_geojson(
        {
            "type": "Polygon",
            "coordinates": [
                [[20.0, 52.0], [21.0, 52.0], [21.0, 53.0], [20.0, 53.0]]
            ],
        }
    )

    assert isinstance(geometry, PolygonGeometry)
    assert geometry.coordinates[0][0] == geometry.coordinates[0][-1]


def test_feature_collection_uses_last_supported_geometry() -> None:
    geometry = target_geometry_from_geojson(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Point", "coordinates": [10, 50]},
                },
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Point", "coordinates": [20, 51]},
                },
            ],
        }
    )

    assert geometry == PointGeometry(coordinates=(20.0, 51.0))


def test_geometry_round_trip_and_helpers() -> None:
    original = PolygonGeometry(
        coordinates=[
            [(20.0, 52.0), (22.0, 52.0), (22.0, 54.0), (20.0, 52.0)]
        ]
    )

    restored = target_geometry_from_geojson(target_geometry_to_feature(original))

    assert restored == original
    assert geometry_centroid(original) == pytest.approx((64 / 3, 158 / 3))
    assert geometry_bounds(original) == ((52.0, 20.0), (54.0, 22.0))


def test_unsupported_geometry_is_rejected() -> None:
    with pytest.raises(ValueError, match="Point i Polygon"):
        target_geometry_from_geojson(
            {"type": "LineString", "coordinates": [[20, 52], [21, 53]]}
        )
