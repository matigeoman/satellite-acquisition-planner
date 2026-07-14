import pytest
from pydantic import ValidationError

from app.models.geometry import (
    PointGeometry,
    PolygonGeometry,
)


def valid_polygon_coordinates() -> list:
    return [
        [
            [19.0, 52.0],
            [20.0, 52.0],
            [20.0, 53.0],
            [19.0, 52.0],
        ]
    ]


def test_valid_point_is_created() -> None:
    point = PointGeometry(
        type="Point",
        coordinates=[21.0, 52.0],
    )

    assert point.coordinates == (21.0, 52.0)


def test_point_rejects_invalid_longitude() -> None:
    with pytest.raises(ValidationError):
        PointGeometry(
            type="Point",
            coordinates=[181.0, 52.0],
        )


def test_point_rejects_invalid_latitude() -> None:
    with pytest.raises(ValidationError):
        PointGeometry(
            type="Point",
            coordinates=[21.0, 91.0],
        )


def test_valid_polygon_is_created() -> None:
    polygon = PolygonGeometry(
        type="Polygon",
        coordinates=valid_polygon_coordinates(),
    )

    assert len(polygon.coordinates) == 1
    assert len(polygon.coordinates[0]) == 4


def test_polygon_ring_must_be_closed() -> None:
    coordinates = [
        [
            [19.0, 52.0],
            [20.0, 52.0],
            [20.0, 53.0],
            [19.0, 53.0],
        ]
    ]

    with pytest.raises(ValidationError):
        PolygonGeometry(
            type="Polygon",
            coordinates=coordinates,
        )


def test_polygon_ring_requires_four_positions() -> None:
    coordinates = [
        [
            [19.0, 52.0],
            [20.0, 52.0],
            [19.0, 52.0],
        ]
    ]

    with pytest.raises(ValidationError):
        PolygonGeometry(
            type="Polygon",
            coordinates=coordinates,
        )


def test_polygon_requires_three_distinct_vertices() -> None:
    coordinates = [
        [
            [19.0, 52.0],
            [20.0, 52.0],
            [19.0, 52.0],
            [19.0, 52.0],
        ]
    ]

    with pytest.raises(ValidationError):
        PolygonGeometry(
            type="Polygon",
            coordinates=coordinates,
        )


def test_polygon_rejects_zero_area() -> None:
    coordinates = [
        [
            [19.0, 52.0],
            [20.0, 53.0],
            [21.0, 54.0],
            [19.0, 52.0],
        ]
    ]

    with pytest.raises(ValidationError):
        PolygonGeometry(
            type="Polygon",
            coordinates=coordinates,
        )


def test_polygon_rejects_invalid_coordinate_range() -> None:
    coordinates = [
        [
            [19.0, 52.0],
            [181.0, 52.0],
            [20.0, 53.0],
            [19.0, 52.0],
        ]
    ]

    with pytest.raises(ValidationError):
        PolygonGeometry(
            type="Polygon",
            coordinates=coordinates,
        )


def test_geometry_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        PointGeometry(
            type="Point",
            coordinates=[21.0, 52.0],
            unknown_field=123,
        )