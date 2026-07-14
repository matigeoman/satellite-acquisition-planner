import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.analysis.schedule_report import (
    RequestFulfillmentStatus,
    UnassignedReasonCode,
    analyze_schedule,
    export_schedule_analysis,
)
from app.catalog_loader import load_system_catalog
from app.models.schedule import Schedule
from app.opportunity_loader import load_opportunity_set
from app.planning.greedy import (
    GreedyPlannerConfig,
    build_greedy_schedule,
)
from app.request_loader import load_request_set


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]

CATALOG_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "example_system.json"
)

REQUEST_SET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "example_requests.json"
)

OPPORTUNITY_SET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "example_opportunities.json"
)

FIXED_CREATED_AT = datetime(
    2026,
    7,
    14,
    22,
    0,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(scope="module")
def reference_data():
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

    return catalog, request_set, opportunity_set


@pytest.fixture(scope="module")
def schedule_analysis(reference_data):
    catalog, request_set, opportunity_set = reference_data

    schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        created_at_utc=FIXED_CREATED_AT,
    )

    analysis = analyze_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        schedule=schedule,
    )

    return schedule, analysis


def test_analysis_contains_all_active_requests(
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    assert analysis.total_active_requests == 20
    assert len(analysis.request_diagnostics) == 20


def test_request_totals_are_consistent(
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    assert (
        analysis.fully_satisfied_requests
        + analysis.partially_satisfied_requests
        + analysis.unassigned_requests
        == analysis.total_active_requests
    )


def test_acquisition_totals_match_schedule(
    schedule_analysis,
) -> None:
    schedule, analysis = schedule_analysis

    assert (
        analysis.total_acquisitions
        == schedule.total_acquisitions
    )

    assert (
        analysis.sar_acquisitions
        + analysis.optical_acquisitions
        == schedule.total_acquisitions
    )


def test_duration_matches_schedule(
    schedule_analysis,
) -> None:
    schedule, analysis = schedule_analysis

    assert analysis.total_duration_s == pytest.approx(
        schedule.total_duration_s
    )


def test_data_volume_matches_schedule(
    schedule_analysis,
) -> None:
    schedule, analysis = schedule_analysis

    assert analysis.total_data_volume_mb == pytest.approx(
        schedule.total_data_volume_mb
    )


def test_objective_matches_schedule(
    schedule_analysis,
) -> None:
    schedule, analysis = schedule_analysis

    assert analysis.objective_value == pytest.approx(
        schedule.objective_value
    )


def test_satisfaction_ratios_are_valid(
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    assert 0.0 <= analysis.satisfaction_ratio <= 1.0
    assert (
        0.0
        <= analysis.mandatory_satisfaction_ratio
        <= 1.0
    )


def test_quality_and_coverage_are_valid(
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    assert (
        0.0
        <= analysis.average_selected_quality
        <= 1.0
    )

    assert (
        0.0
        <= analysis.average_selected_coverage
        <= 1.0
    )


def test_analysis_contains_all_satellites(
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    assert len(analysis.satellite_kpis) == 6

    assert {
        item.satellite_id
        for item in analysis.satellite_kpis
    } == {
        "SAR-01",
        "SAR-02",
        "SAR-03",
        "SAR-04",
        "EO-01",
        "EO-02",
    }


def test_satellite_acquisitions_sum_to_total(
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    assert sum(
        item.scheduled_acquisitions
        for item in analysis.satellite_kpis
    ) == analysis.total_acquisitions


def test_satellite_resource_ratios_are_valid(
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    for item in analysis.satellite_kpis:
        assert (
            0.0
            <= item.acquisition_utilization_ratio
            <= 1.0
        )

        assert (
            0.0
            <= item.imaging_utilization_ratio
            <= 1.0
        )

        assert (
            0.0
            <= item.memory_utilization_ratio
            <= 1.0
        )


def test_fully_satisfied_requests_have_no_reasons(
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    for diagnostic in analysis.request_diagnostics:
        if (
            diagnostic.fulfillment_status
            == RequestFulfillmentStatus.FULLY_SATISFIED.value
        ):
            assert diagnostic.reason_codes == ()


def test_entry_report_count_matches_schedule(
    schedule_analysis,
) -> None:
    schedule, analysis = schedule_analysis

    assert (
        len(analysis.entry_kpis)
        == schedule.total_acquisitions
    )


def test_full_memory_reserve_produces_diagnostics(
    reference_data,
) -> None:
    catalog, request_set, opportunity_set = reference_data

    schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=GreedyPlannerConfig(
            memory_reserve_ratio=1.0
        ),
        schedule_id="SCHEDULE-GREEDY-REPORT-NOMEM",
        created_at_utc=FIXED_CREATED_AT,
    )

    analysis = analyze_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        schedule=schedule,
    )

    assert analysis.unassigned_requests == 20

    for diagnostic in analysis.request_diagnostics:
        assert diagnostic.reason_codes


def test_full_memory_reserve_reports_memory_limit(
    reference_data,
) -> None:
    catalog, request_set, opportunity_set = reference_data

    schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=GreedyPlannerConfig(
            memory_reserve_ratio=1.0
        ),
        schedule_id="SCHEDULE-GREEDY-REPORT-MEMORY",
        created_at_utc=FIXED_CREATED_AT,
    )

    analysis = analyze_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        schedule=schedule,
    )

    assert (
        analysis.unassigned_reason_counts.get(
            UnassignedReasonCode.MEMORY_LIMIT.value,
            0,
        )
        > 0
    )


def test_export_creates_four_csv_files(
    tmp_path: Path,
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    paths = export_schedule_analysis(
        analysis,
        tmp_path,
    )

    assert set(paths) == {
        "kpi",
        "satellites",
        "requests",
        "entries",
    }

    assert all(
        path.exists()
        for path in paths.values()
    )


def test_exported_kpi_has_expected_header(
    tmp_path: Path,
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    paths = export_schedule_analysis(
        analysis,
        tmp_path,
    )

    with paths["kpi"].open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        assert reader.fieldnames == [
            "metric",
            "value",
        ]


def test_exported_request_rows_cover_all_requests(
    tmp_path: Path,
    schedule_analysis,
) -> None:
    _, analysis = schedule_analysis

    paths = export_schedule_analysis(
        analysis,
        tmp_path,
    )

    with paths["requests"].open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    assert len(rows) == 20


def test_unknown_opportunity_reference_is_rejected(
    reference_data,
    schedule_analysis,
) -> None:
    catalog, request_set, opportunity_set = reference_data
    schedule, _ = schedule_analysis

    data = schedule.model_dump(
        mode="json"
    )

    data["entries"][0]["opportunity_id"] = (
        "OPP-SAR-9999"
    )

    invalid_schedule = Schedule.model_validate(
        data
    )

    with pytest.raises(ValueError):
        analyze_schedule(
            catalog=catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
            schedule=invalid_schedule,
        )