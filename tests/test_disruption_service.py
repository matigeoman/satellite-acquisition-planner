from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.analysis.disruption_report import (
    build_disruption_summary_rows,
    build_schedule_change_rows,
    export_disruption_report,
)
from app.models.enums import (
    PlanningAlgorithm,
    ScheduleEntryStatus,
    ScheduleStatus,
)
from app.models.opportunity import AcquisitionOpportunity
from app.schedule_loader import load_schedule
from app.scenarios.disruption import build_example_disruption_plan
from app.services.disruption_service import (
    CloudCoverUpdate,
    DisruptionPlan,
    DisruptionReplanningService,
    DisruptionService,
    SatelliteOutage,
    UrgentRequestPackage,
)
from app.services.planning_service import PlanningOptions
from app.services.scenario_service import ScenarioService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPLAN_AT = datetime(2026, 7, 15, 6, 0, tzinfo=timezone.utc)
FROZEN_UNTIL = datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def example_scenario():
    return ScenarioService(project_root=PROJECT_ROOT).load("EXAMPLE")


@pytest.fixture(scope="module")
def previous_schedule():
    return load_schedule(
        PROJECT_ROOT / "data" / "example_schedule_cp_sat.json"
    )


@pytest.fixture(scope="module")
def disruption_plan(example_scenario, previous_schedule):
    return build_example_disruption_plan(
        scenario=example_scenario,
        previous_schedule=previous_schedule,
        replan_at_utc=REPLAN_AT,
        freeze_duration=timedelta(hours=2),
    )


@pytest.fixture(scope="module")
def application_result(example_scenario, disruption_plan):
    return DisruptionService().apply(
        scenario=example_scenario,
        plan=disruption_plan,
    )


@pytest.fixture(scope="module")
def replanning_result(
    example_scenario,
    previous_schedule,
    disruption_plan,
):
    return DisruptionReplanningService().run(
        scenario=example_scenario,
        previous_schedule=previous_schedule,
        plan=disruption_plan,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.CP_SAT,
            memory_reserve_ratio=0.0,
            cp_sat_time_limit_s=30.0,
            cp_sat_num_search_workers=1,
            cp_sat_force_mandatory_requests=True,
        ),
        replan_at_utc=REPLAN_AT,
        freeze_duration=timedelta(hours=2),
    )


def test_satellite_outage_normalizes_values() -> None:
    outage = SatelliteOutage(
        satellite_id=" eo-01 ",
        effective_from_utc=datetime(
            2026,
            7,
            15,
            10,
            0,
            tzinfo=timezone(timedelta(hours=2)),
        ),
        reason=" awaria ",
    )

    assert outage.satellite_id == "EO-01"
    assert outage.effective_from_utc.hour == 8
    assert outage.reason == "awaria"


def test_satellite_outage_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        SatelliteOutage(
            satellite_id="EO-01",
            effective_from_utc=datetime(2026, 7, 15, 8, 0),
        )


def test_cloud_cover_update_rejects_value_outside_range() -> None:
    with pytest.raises(ValueError):
        CloudCoverUpdate(
            opportunity_id="OPP-EO-0001",
            cloud_cover=1.1,
        )


def test_urgent_package_rejects_foreign_opportunity(
    example_scenario,
) -> None:
    request = example_scenario.request_set.requests[0]
    opportunity = example_scenario.opportunity_set.opportunities[0]

    foreign = AcquisitionOpportunity.model_validate(
        {
            **opportunity.model_dump(),
            "request_id": "REQ-FOREIGN-001",
        }
    )

    with pytest.raises(ValueError):
        UrgentRequestPackage(
            request=request,
            opportunities=(foreign,),
        )


def test_disruption_plan_rejects_duplicate_outages() -> None:
    outage = SatelliteOutage(
        satellite_id="EO-01",
        effective_from_utc=FROZEN_UNTIL,
    )

    with pytest.raises(ValueError):
        DisruptionPlan(
            plan_id="DISRUPTION-DUPLICATE",
            occurred_at_utc=REPLAN_AT,
            satellite_outages=(outage, outage),
        )


def test_example_plan_selects_expected_events(disruption_plan) -> None:
    assert disruption_plan.satellite_outages[0].satellite_id == "EO-01"
    assert (
        disruption_plan.cloud_cover_updates[0].opportunity_id
        == "OPP-EO-0106"
    )
    assert (
        disruption_plan.urgent_requests[0].request.request_id
        == "REQ-URGENT-001"
    )


def test_application_adds_urgent_request_and_opportunity(
    example_scenario,
    application_result,
) -> None:
    disrupted = application_result.disrupted_scenario

    assert len(disrupted.request_set.requests) == (
        len(example_scenario.request_set.requests) + 1
    )
    assert len(disrupted.opportunity_set.opportunities) == (
        len(example_scenario.opportunity_set.opportunities) + 1
    )
    assert application_result.added_request_ids == ("REQ-URGENT-001",)
    assert application_result.added_opportunity_ids == ("OPP-URGENT-001",)


def test_outage_invalidates_only_future_opportunities(
    application_result,
) -> None:
    disrupted = application_result.disrupted_scenario

    affected = [
        disrupted.opportunity_set.get_opportunity(opportunity_id)
        for opportunity_id
        in application_result.outage_invalidated_opportunity_ids
    ]

    assert affected
    assert all(item.satellite_id == "EO-01" for item in affected)
    assert all(item.start_utc >= FROZEN_UNTIL for item in affected)
    assert all(not item.is_feasible for item in affected)


def test_outage_preserves_earlier_opportunities(application_result) -> None:
    disrupted = application_result.disrupted_scenario
    earlier = [
        opportunity
        for opportunity in disrupted.opportunity_set.opportunities
        if opportunity.satellite_id == "EO-01"
        and opportunity.start_utc < FROZEN_UNTIL
    ]

    original_by_id = {
        opportunity.opportunity_id: opportunity
        for opportunity
        in application_result.previous_scenario.opportunity_set.opportunities
    }

    assert all(
        opportunity.is_feasible
        == original_by_id[opportunity.opportunity_id].is_feasible
        for opportunity in earlier
    )


def test_weather_update_invalidates_selected_opportunity(
    application_result,
) -> None:
    opportunity = (
        application_result.disrupted_scenario.opportunity_set.get_opportunity(
            "OPP-EO-0106"
        )
    )

    assert opportunity.cloud_cover == pytest.approx(1.0)
    assert opportunity.is_feasible is False
    assert (
        application_result.weather_invalidated_opportunity_ids
        == ("OPP-EO-0106",)
    )


def test_disrupted_input_sets_remain_cross_validated(
    application_result,
) -> None:
    disrupted = application_result.disrupted_scenario

    disrupted.opportunity_set.validate_against(
        disrupted.catalog,
        disrupted.request_set,
    )


def test_disrupted_scenario_has_separate_identity(application_result) -> None:
    assert (
        application_result.disrupted_scenario.scenario_id
        == "EXAMPLE-DISRUPTED"
    )


def test_replanning_finds_feasible_optimal_schedule(replanning_result) -> None:
    assert replanning_result.solver_status == "OPTIMAL"
    assert replanning_result.schedule.status == ScheduleStatus.FEASIBLE


def test_replanning_preserves_executed_and_frozen_entries(
    replanning_result,
) -> None:
    fixed_ids = {
        assignment.opportunity_id
        for assignment
        in replanning_result.replanning_result.fixed_assignments
    }
    result_ids = {
        entry.opportunity_id
        for entry in replanning_result.schedule.active_entries
    }

    assert fixed_ids <= result_ids
    assert sum(
        entry.status == ScheduleEntryStatus.EXECUTED
        for entry in replanning_result.schedule.active_entries
    ) == 6
    assert sum(
        entry.status == ScheduleEntryStatus.FROZEN
        for entry in replanning_result.schedule.active_entries
    ) == 5


def test_failed_satellite_has_no_acquisition_after_outage(
    replanning_result,
) -> None:
    assert not any(
        entry.satellite_id == "EO-01"
        and entry.start_utc >= FROZEN_UNTIL
        for entry in replanning_result.schedule.active_entries
    )


def test_weather_invalidated_opportunity_is_not_selected(
    replanning_result,
) -> None:
    assert "OPP-EO-0106" not in {
        entry.opportunity_id
        for entry in replanning_result.schedule.active_entries
    }


def test_urgent_request_is_selected(replanning_result) -> None:
    assert "REQ-URGENT-001" in (
        replanning_result.schedule.scheduled_request_ids
    )
    assert "OPP-URGENT-001" in {
        entry.opportunity_id
        for entry in replanning_result.schedule.active_entries
    }


def test_disruption_causes_real_schedule_changes(replanning_result) -> None:
    assert replanning_result.added_opportunity_ids
    assert replanning_result.removed_opportunity_ids
    assert replanning_result.invalidated_previous_selection_ids


def test_all_mandatory_requests_remain_satisfied(replanning_result) -> None:
    assert (
        replanning_result.analysis.mandatory_satisfied_requests
        == replanning_result.analysis.mandatory_requests
        == 5
    )


def test_disruption_report_builders_return_changes(replanning_result) -> None:
    summary = build_disruption_summary_rows(replanning_result)
    changes = build_schedule_change_rows(replanning_result)

    metrics = {row["metric"] for row in summary}
    change_types = {row["change_type"] for row in changes}

    assert "objective_delta" in metrics
    assert change_types == {"ADDED", "REMOVED"}


def test_disruption_report_is_exported(
    replanning_result,
    tmp_path,
) -> None:
    paths = export_disruption_report(
        replanning_result,
        tmp_path,
        prefix="test_disruption",
    )

    assert paths["summary"].is_file()
    assert paths["changes"].is_file()
    assert "objective_delta" in paths["summary"].read_text(
        encoding="utf-8-sig"
    )
