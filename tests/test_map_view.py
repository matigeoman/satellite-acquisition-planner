from pathlib import Path

import pytest
from plotly.graph_objects import Figure

from app.models.enums import PlanningAlgorithm
from app.services.planning_service import (
    PlanningOptions,
    PlanningService,
)
from app.services.scenario_service import (
    ScenarioService,
)
from app.ui.map_view import (
    MAP_COLUMNS,
    build_request_map_dataframe,
    build_request_map_figure,
)


PROJECT_DIRECTORY = Path(
    __file__
).resolve().parents[1]


@pytest.fixture(scope="module")
def example_scenario():
    return ScenarioService(
        project_root=PROJECT_DIRECTORY
    ).load(
        "EXAMPLE"
    )


@pytest.fixture(scope="module")
def example_result(
    example_scenario,
):
    return PlanningService().run(
        scenario=example_scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=0.0,
        ),
        schedule_id="SCHEDULE-MAP-EXAMPLE",
    )


@pytest.fixture(scope="module")
def blocked_result(
    example_scenario,
):
    return PlanningService().run(
        scenario=example_scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=1.0,
        ),
        schedule_id="SCHEDULE-MAP-BLOCKED",
    )


def test_map_dataframe_contains_all_requests(
    example_result,
) -> None:
    dataframe = build_request_map_dataframe(
        example_result
    )

    assert list(
        dataframe.columns
    ) == MAP_COLUMNS

    assert len(dataframe) == 20


def test_map_dataframe_contains_supported_geometries(
    example_result,
) -> None:
    dataframe = build_request_map_dataframe(
        example_result
    )

    assert set(
        dataframe["geometry_type"]
    ) == {
        "POINT",
        "POLYGON",
    }


def test_map_centroids_are_valid_coordinates(
    example_result,
) -> None:
    dataframe = build_request_map_dataframe(
        example_result
    )

    assert dataframe[
        "centroid_lon"
    ].between(
        -180.0,
        180.0,
    ).all()

    assert dataframe[
        "centroid_lat"
    ].between(
        -90.0,
        90.0,
    ).all()


def test_polygon_rings_are_closed(
    example_result,
) -> None:
    dataframe = build_request_map_dataframe(
        example_result
    )

    polygons = dataframe.loc[
        dataframe["geometry_type"]
        == "POLYGON"
    ]

    assert not polygons.empty

    assert all(
        coordinates[0]
        == coordinates[-1]
        for coordinates
        in polygons["coordinates"]
    )


def test_polygon_rings_are_counterclockwise(
    example_result,
) -> None:
    dataframe = build_request_map_dataframe(
        example_result
    )

    polygons = dataframe.loc[
        dataframe["geometry_type"]
        == "POLYGON"
    ]

    for coordinates in polygons[
        "coordinates"
    ]:
        signed_area = 0.5 * sum(
            (
                current[0]
                * following[1]
                - following[0]
                * current[1]
            )
            for current, following
            in zip(
                coordinates[:-1],
                coordinates[1:],
                strict=True,
            )
        )

        assert signed_area >= 0.0


def test_map_figure_metadata_matches_requests(
    example_result,
) -> None:
    figure = build_request_map_figure(
        example_result
    )

    assert isinstance(
        figure,
        Figure,
    )

    assert (
        figure.layout.meta[
            "request_count"
        ]
        == 20
    )

    assert (
        figure.layout.meta[
            "point_count"
        ]
        + figure.layout.meta[
            "polygon_count"
        ]
        == 20
    )


def test_map_uses_planar_scattermap_traces(
    example_result,
) -> None:
    figure = build_request_map_figure(
        example_result
    )

    assert figure.data

    assert all(
        trace.type == "scattermap"
        for trace in figure.data
    )

    assert (
        figure.layout.map.style
        == "carto-positron"
    )


def test_map_figure_filters_geometry_type(
    example_result,
) -> None:
    dataframe = build_request_map_dataframe(
        example_result
    )

    expected_point_count = int(
        (
            dataframe["geometry_type"]
            == "POINT"
        ).sum()
    )

    figure = build_request_map_figure(
        example_result,
        geometry_types=[
            "POINT"
        ],
    )

    assert (
        figure.layout.meta[
            "request_count"
        ]
        == expected_point_count
    )

    assert (
        figure.layout.meta[
            "polygon_count"
        ]
        == 0
    )


def test_blocked_schedule_marks_requests_unassigned(
    blocked_result,
) -> None:
    dataframe = build_request_map_dataframe(
        blocked_result
    )

    assert set(
        dataframe["fulfillment_status"]
    ) == {
        "UNASSIGNED"
    }

    figure = build_request_map_figure(
        blocked_result,
        fulfillment_statuses=[
            "UNASSIGNED"
        ],
    )

    assert (
        figure.layout.meta[
            "request_count"
        ]
        == 20
    )


def test_empty_filter_builds_empty_map(
    example_result,
) -> None:
    figure = build_request_map_figure(
        example_result,
        fulfillment_statuses=[],
    )

    assert isinstance(
        figure,
        Figure,
    )

    assert len(
        figure.data
    ) == 0

    assert (
        figure.layout.meta[
            "request_count"
        ]
        == 0
    )

    assert len(
        figure.layout.annotations
    ) == 1
