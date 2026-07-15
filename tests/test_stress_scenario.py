from datetime import timedelta
from pathlib import Path

import pytest

from app.catalog_loader import load_system_catalog
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request_set import ObservationRequestSet
from app.planning.cp_sat import (
    CpSatPlannerConfig,
    build_cp_sat_schedule,
)
from app.planning.greedy import (
    GreedyPlannerConfig,
    build_greedy_schedule,
)
from app.scenarios.stress import (
    build_stress_scenario,
    save_stress_scenario,
)


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]

BASE_CATALOG_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "example_system.json"
)


@pytest.fixture(scope="module")
def stress_scenario():
    base_catalog = load_system_catalog(
        BASE_CATALOG_PATH
    )

    return build_stress_scenario(
        base_catalog
    )


def test_stress_catalog_has_reduced_limits(
    stress_scenario,
) -> None:
    catalog, _, _ = stress_scenario

    for satellite in catalog.satellites:
        if satellite.satellite_id.startswith("SAR-"):
            assert satellite.memory_capacity_mb == 20_000.0
            assert satellite.max_acquisitions_per_day == 8
            assert (
                satellite.max_imaging_time_per_day_s
                == 600.0
            )
        else:
            assert satellite.memory_capacity_mb == 30_000.0
            assert satellite.max_acquisitions_per_day == 12
            assert (
                satellite.max_imaging_time_per_day_s
                == 360.0
            )


def test_stress_request_set_contains_eighty_requests(
    stress_scenario,
) -> None:
    _, request_set, _ = stress_scenario

    assert len(request_set.requests) == 80
    assert len(request_set.active_requests) == 80


def test_stress_request_mode_distribution(
    stress_scenario,
) -> None:
    _, request_set, _ = stress_scenario

    assert request_set.request_mode_counts == {
        "SINGLE": 64,
        "DUAL_OPTIONAL": 8,
        "DUAL_REQUIRED": 8,
    }


def test_stress_request_set_contains_four_mandatory_requests(
    stress_scenario,
) -> None:
    _, request_set, _ = stress_scenario

    assert len(request_set.mandatory_requests) == 4


def test_stress_opportunity_set_contains_eight_hundred(
    stress_scenario,
) -> None:
    _, _, opportunity_set = stress_scenario

    assert len(opportunity_set.opportunities) == 800


def test_stress_opportunities_are_sensor_balanced(
    stress_scenario,
) -> None:
    _, _, opportunity_set = stress_scenario

    assert opportunity_set.sensor_type_counts == {
        "SAR": 400,
        "OPTICAL": 400,
    }


def test_each_request_has_ten_opportunities(
    stress_scenario,
) -> None:
    _, _, opportunity_set = stress_scenario

    assert len(opportunity_set.request_counts) == 80

    assert set(
        opportunity_set.request_counts.values()
    ) == {10}


def test_all_stress_opportunities_are_feasible(
    stress_scenario,
) -> None:
    _, _, opportunity_set = stress_scenario

    assert len(
        opportunity_set.feasible_opportunities
    ) == 800

    assert not (
        opportunity_set.infeasible_opportunities
    )


def test_stress_opportunities_validate_against_inputs(
    stress_scenario,
) -> None:
    catalog, request_set, opportunity_set = (
        stress_scenario
    )

    opportunity_set.validate_against(
        catalog,
        request_set,
    )


def test_stress_scenario_is_deterministic() -> None:
    base_catalog = load_system_catalog(
        BASE_CATALOG_PATH
    )

    first = build_stress_scenario(
        base_catalog
    )

    second = build_stress_scenario(
        base_catalog
    )

    assert (
        first[0].model_dump(mode="json")
        == second[0].model_dump(mode="json")
    )

    assert (
        first[1].model_dump(mode="json")
        == second[1].model_dump(mode="json")
    )

    assert (
        first[2].model_dump(mode="json")
        == second[2].model_dump(mode="json")
    )


def test_trap_anchor_has_conflicting_and_safe_options(
    stress_scenario,
) -> None:
    catalog, _, opportunity_set = stress_scenario

    anchor_candidates = [
        opportunity
        for opportunity in opportunity_set.opportunities
        if opportunity.request_id
        == "REQ-STRESS-SAR-T01-A"
    ]

    dependent_b = [
        opportunity
        for opportunity in opportunity_set.opportunities
        if opportunity.request_id
        == "REQ-STRESS-SAR-T01-B"
    ]

    dependent_c = [
        opportunity
        for opportunity in opportunity_set.opportunities
        if opportunity.request_id
        == "REQ-STRESS-SAR-T01-C"
    ]

    best_anchor = max(
        anchor_candidates,
        key=lambda opportunity: opportunity.quality_score,
    )

    best_b = max(
        dependent_b,
        key=lambda opportunity: opportunity.quality_score,
    )

    best_c = max(
        dependent_c,
        key=lambda opportunity: opportunity.quality_score,
    )

    assert (
        best_anchor.satellite_id
        == best_b.satellite_id
        == best_c.satellite_id
    )

    assert any(
        candidate.satellite_id
        != best_anchor.satellite_id
        for candidate in anchor_candidates
    )

    satellite = catalog.get_satellite(
        best_anchor.satellite_id
    )

    sensor = catalog.get_sensor(
        satellite.sensor_id
    )

    transition = timedelta(
        seconds=max(
            satellite.minimum_transition_time_s,
            sensor.warmup_time_s
            + sensor.cooldown_time_s,
        )
    )

    assert not (
        best_b.end_utc + transition
        <= best_anchor.start_utc
        or best_anchor.end_utc + transition
        <= best_b.start_utc
    )

    assert not (
        best_anchor.end_utc + transition
        <= best_c.start_utc
        or best_c.end_utc + transition
        <= best_anchor.start_utc
    )

    assert (
        best_b.end_utc + transition
        <= best_c.start_utc
    )


def test_cp_sat_beats_greedy_on_trap_subset(
    stress_scenario,
) -> None:
    catalog, request_set, opportunity_set = (
        stress_scenario
    )

    trap_request_ids = {
        "REQ-STRESS-SAR-T01-A",
        "REQ-STRESS-SAR-T01-B",
        "REQ-STRESS-SAR-T01-C",
    }

    request_data = request_set.model_dump(
        mode="json"
    )

    request_data["request_set_id"] = (
        "REQSET-PL-STRESS-TRAP"
    )

    request_data["requests"] = [
        request
        for request in request_data["requests"]
        if request["request_id"]
        in trap_request_ids
    ]

    trap_request_set = (
        ObservationRequestSet.model_validate(
            request_data
        )
    )

    opportunity_data = opportunity_set.model_dump(
        mode="json"
    )

    opportunity_data["opportunity_set_id"] = (
        "OPPSET-PL-STRESS-TRAP"
    )

    opportunity_data["request_set_id"] = (
        trap_request_set.request_set_id
    )

    opportunity_data["opportunities"] = [
        opportunity
        for opportunity
        in opportunity_data["opportunities"]
        if opportunity["request_id"]
        in trap_request_ids
    ]

    trap_opportunity_set = (
        AcquisitionOpportunitySet.model_validate(
            opportunity_data
        )
    )

    trap_opportunity_set.validate_against(
        catalog,
        trap_request_set,
    )

    greedy_schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=trap_request_set,
        opportunity_set=trap_opportunity_set,
        config=GreedyPlannerConfig(
            memory_reserve_ratio=0.0
        ),
        schedule_id="SCHEDULE-TRAP-GREEDY",
    )

    cp_sat_schedule = build_cp_sat_schedule(
        catalog=catalog,
        request_set=trap_request_set,
        opportunity_set=trap_opportunity_set,
        config=CpSatPlannerConfig(
            memory_reserve_ratio=0.0,
            force_mandatory_requests=True,
            max_time_s=10.0,
            num_search_workers=1,
        ),
        schedule_id="SCHEDULE-TRAP-CP-SAT",
    )

    assert len(
        greedy_schedule.scheduled_request_ids
    ) == 1

    assert len(
        cp_sat_schedule.scheduled_request_ids
    ) == 3

    assert (
        cp_sat_schedule.objective_value
        > greedy_schedule.objective_value
    )


def test_save_stress_scenario_creates_three_files(
    tmp_path: Path,
    stress_scenario,
) -> None:
    catalog, request_set, opportunity_set = (
        stress_scenario
    )

    paths = save_stress_scenario(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        output_directory=tmp_path,
    )

    assert set(paths) == {
        "catalog",
        "requests",
        "opportunities",
    }

    assert all(
        path.exists()
        for path in paths.values()
    )