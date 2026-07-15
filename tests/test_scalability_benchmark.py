import csv
from collections import Counter
from pathlib import Path

import pytest

from app.analysis.scalability_benchmark import (
    SCALABILITY_FIELDNAMES,
    ScalabilityRunResult,
    build_scalability_report,
    export_scalability_report,
)
from app.catalog_loader import load_system_catalog
from app.models.enums import SensorType
from app.opportunity_loader import load_opportunity_set
from app.request_loader import load_request_set
from app.scenarios.scalability import (
    build_scalability_source,
    build_scalability_subset,
)


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]

CATALOG_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "stress_system.json"
)

REQUEST_SET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "stress_requests.json"
)

OPPORTUNITY_SET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "stress_opportunities.json"
)


@pytest.fixture(scope="module")
def scalability_source():
    catalog = load_system_catalog(
        CATALOG_PATH
    )

    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH,
        catalog=catalog,
        request_set=request_set,
    )

    (
        expanded_requests,
        expanded_opportunities,
    ) = build_scalability_source(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
    )

    return (
        catalog,
        expanded_requests,
        expanded_opportunities,
    )


def make_result(
    *,
    request_count: int,
    algorithm: str,
    objective: float,
    fulfilled: int,
    runtime: float,
) -> ScalabilityRunResult:
    return ScalabilityRunResult(
        request_count=request_count,
        opportunity_count=request_count * 10,
        selection_variable_count=request_count * 10,
        request_variable_count=request_count,
        auxiliary_variable_count=2,
        algorithm=algorithm,
        time_limit_s=(
            None
            if algorithm == "GREEDY"
            else 10.0
        ),
        solver_status=(
            "NOT_APPLICABLE"
            if algorithm == "GREEDY"
            else "FEASIBLE"
        ),
        schedule_status="FEASIBLE",
        objective_value=objective,
        fully_satisfied_requests=fulfilled,
        unassigned_requests=(
            request_count - fulfilled
        ),
        satisfaction_ratio=(
            fulfilled / request_count
        ),
        total_acquisitions=fulfilled,
        runtime_s=runtime,
        schedule_path=(
            f"{request_count}_{algorithm}.json"
        ),
    )


@pytest.fixture
def sample_report():
    results = []

    for request_count in (
        20,
        40,
        60,
    ):
        results.extend(
            [
                make_result(
                    request_count=request_count,
                    algorithm="GREEDY",
                    objective=request_count * 40.0,
                    fulfilled=int(
                        request_count * 0.65
                    ),
                    runtime=0.002,
                ),
                make_result(
                    request_count=request_count,
                    algorithm="CP_SAT",
                    objective=request_count * 50.0,
                    fulfilled=int(
                        request_count * 0.75
                    ),
                    runtime=10.0,
                ),
            ]
        )

    return build_scalability_report(
        scenario_id="TEST-SCALABILITY",
        results=results,
    )


def test_source_contains_one_hundred_requests(
    scalability_source,
) -> None:
    _, request_set, _ = scalability_source

    assert len(
        request_set.active_requests
    ) == 100


def test_source_contains_one_thousand_opportunities(
    scalability_source,
) -> None:
    _, _, opportunity_set = scalability_source

    assert len(
        opportunity_set.opportunities
    ) == 1000


def test_each_source_request_has_ten_opportunities(
    scalability_source,
) -> None:
    _, request_set, opportunity_set = (
        scalability_source
    )

    counts = Counter(
        opportunity.request_id
        for opportunity in opportunity_set.opportunities
    )

    assert len(counts) == len(
        request_set.active_requests
    )

    assert set(
        counts.values()
    ) == {10}


@pytest.mark.parametrize(
    "request_count",
    [
        20,
        40,
        60,
        80,
        100,
    ],
)
def test_subset_has_expected_size(
    scalability_source,
    request_count: int,
) -> None:
    (
        catalog,
        request_set,
        opportunity_set,
    ) = scalability_source

    subset_requests, subset_opportunities = (
        build_scalability_subset(
            catalog=catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
            request_count=request_count,
        )
    )

    assert len(
        subset_requests.active_requests
    ) == request_count

    assert len(
        subset_opportunities.opportunities
    ) == request_count * 10


def test_subsets_are_deterministic(
    scalability_source,
) -> None:
    (
        catalog,
        request_set,
        opportunity_set,
    ) = scalability_source

    first = build_scalability_subset(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        request_count=40,
    )

    second = build_scalability_subset(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        request_count=40,
    )

    assert (
        first[0].model_dump(mode="json")
        == second[0].model_dump(mode="json")
    )

    assert (
        first[1].model_dump(mode="json")
        == second[1].model_dump(mode="json")
    )


def test_small_subset_contains_both_sensor_types(
    scalability_source,
) -> None:
    (
        catalog,
        request_set,
        opportunity_set,
    ) = scalability_source

    subset_requests, _ = (
        build_scalability_subset(
            catalog=catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
            request_count=20,
        )
    )

    demanded_sensor_types = {
        sensor_type
        for request in subset_requests.active_requests
        for sensor_type
        in request.requested_sensor_types
    }

    assert demanded_sensor_types == {
        SensorType.SAR,
        SensorType.OPTICAL,
    }


def test_report_contains_two_algorithms_per_size(
    sample_report,
) -> None:
    assert sample_report.request_counts == [
        20,
        40,
        60,
    ]

    for algorithms in (
        sample_report.grouped_results.values()
    ):
        assert set(algorithms) == {
            "GREEDY",
            "CP_SAT",
        }


def test_cp_sat_improvement_is_calculated(
    sample_report,
) -> None:
    cp_sat_rows = [
        row
        for row in sample_report.csv_rows()
        if row["algorithm"] == "CP_SAT"
    ]

    assert all(
        row[
            "objective_improvement_pct_vs_greedy"
        ]
        == pytest.approx(25.0)
        for row in cp_sat_rows
    )


def test_csv_contains_two_rows_per_problem_size(
    sample_report,
) -> None:
    rows = sample_report.csv_rows()

    assert len(rows) == 6

    assert [
        row["algorithm"]
        for row in rows
    ] == [
        "GREEDY",
        "CP_SAT",
        "GREEDY",
        "CP_SAT",
        "GREEDY",
        "CP_SAT",
    ]


def test_estimated_boolean_variable_count() -> None:
    result = make_result(
        request_count=20,
        algorithm="CP_SAT",
        objective=1000.0,
        fulfilled=15,
        runtime=10.0,
    )

    assert (
        result.estimated_boolean_variable_count
        == 222
    )


def test_export_creates_csv_and_four_charts(
    tmp_path: Path,
    sample_report,
) -> None:
    paths = export_scalability_report(
        sample_report,
        tmp_path,
    )

    assert set(paths) == {
        "csv",
        "objective_chart",
        "fulfilled_chart",
        "runtime_chart",
        "improvement_chart",
    }

    assert all(
        path.exists()
        for path in paths.values()
    )

    assert all(
        path.stat().st_size > 0
        for path in paths.values()
    )


def test_exported_csv_has_expected_header(
    tmp_path: Path,
    sample_report,
) -> None:
    paths = export_scalability_report(
        sample_report,
        tmp_path,
    )

    with paths["csv"].open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(
            file
        )

        assert reader.fieldnames == (
            SCALABILITY_FIELDNAMES
        )

        rows = list(
            reader
        )

    assert len(rows) == 6