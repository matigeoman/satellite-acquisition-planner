from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from plotly.graph_objects import Figure

from app.analysis.experimental_validation import (
    ExperimentalValidationConfig,
    ExperimentalValidationService,
)
from app.models.enums import PlanningAlgorithm
from app.schedule_loader import load_schedule
from app.scenarios.disruption import build_configurable_disruption_plan
from app.scenarios.experiment import ExperimentProfile
from app.services.disruption_service import DisruptionReplanningService
from app.services.planning_service import PlanningOptions
from app.services.replanning_service import ReplanningService
from app.services.scenario_service import ScenarioService
from app.ui.operations import (
    DISRUPTION_EVENT_COLUMNS,
    EXPERIMENT_PAIR_COLUMNS,
    EXPERIMENT_SUMMARY_COLUMNS,
    REPLANNING_CHANGE_COLUMNS,
    build_disruption_changes_dataframe,
    build_disruption_events_dataframe,
    build_disruption_metrics,
    build_experiment_improvement_figure,
    build_experiment_metadata_json,
    build_experiment_objective_figure,
    build_experiment_pairs_dataframe,
    build_experiment_profile_dataframe,
    build_experiment_runtime_figure,
    build_experiment_satisfaction_figure,
    build_experiment_summary_dataframe,
    build_replanning_changes_dataframe,
    build_replanning_metrics,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPLAN_AT = datetime(2026, 7, 15, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def example_scenario():
    return ScenarioService(project_root=PROJECT_ROOT).load("EXAMPLE")


@pytest.fixture(scope="module")
def stress_scenario():
    return ScenarioService(project_root=PROJECT_ROOT).load("STRESS")


@pytest.fixture(scope="module")
def previous_schedule():
    return load_schedule(
        PROJECT_ROOT / "data" / "reference_schedules" / "example" / "cp_sat.json"
    )


@pytest.fixture(scope="module")
def replanning_result(example_scenario, previous_schedule):
    return ReplanningService().run(
        scenario=example_scenario,
        previous_schedule=previous_schedule,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.CP_SAT,
            memory_reserve_ratio=0.0,
            cp_sat_time_limit_s=2.0,
            cp_sat_num_search_workers=1,
        ),
        replan_at_utc=REPLAN_AT,
    )


@pytest.fixture(scope="module")
def disruption_result(example_scenario, previous_schedule):
    plan = build_configurable_disruption_plan(
        scenario=example_scenario,
        previous_schedule=previous_schedule,
        replan_at_utc=REPLAN_AT,
        freeze_duration=timedelta(hours=2),
        include_outage=True,
        outage_satellite_id="EO-01",
        include_weather=True,
        weather_opportunity_id="OPP-EO-0106",
        include_urgent_request=True,
        urgent_priority=9,
    )

    return DisruptionReplanningService().run(
        scenario=example_scenario,
        previous_schedule=previous_schedule,
        plan=plan,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.CP_SAT,
            memory_reserve_ratio=0.0,
            cp_sat_time_limit_s=2.0,
            cp_sat_num_search_workers=1,
        ),
        replan_at_utc=REPLAN_AT,
        freeze_duration=timedelta(hours=2),
    )


@pytest.fixture(scope="module")
def experiment_result(stress_scenario):
    profile = ExperimentProfile(
        profile_id="UI-TEST",
        name="Profil interfejsu",
        resource_ratio=0.9,
        opportunity_dropout_ratio=0.05,
    )

    return ExperimentalValidationService().run(
        base_scenario=stress_scenario,
        config=ExperimentalValidationConfig(
            profiles=(profile,),
            repetitions=1,
            base_seed=123,
            cp_sat_time_limit_s=0.1,
            cp_sat_num_search_workers=1,
        ),
    )


def test_configurable_plan_accepts_selected_events(
    example_scenario,
    previous_schedule,
) -> None:
    plan = build_configurable_disruption_plan(
        scenario=example_scenario,
        previous_schedule=previous_schedule,
        replan_at_utc=REPLAN_AT,
        outage_satellite_id="EO-01",
        weather_opportunity_id="OPP-EO-0106",
        urgent_priority=8,
    )

    assert plan.satellite_outages[0].satellite_id == "EO-01"
    assert plan.cloud_cover_updates[0].opportunity_id == "OPP-EO-0106"
    assert plan.urgent_requests[0].request.priority == 8


def test_configurable_plan_requires_at_least_one_event(
    example_scenario,
    previous_schedule,
) -> None:
    with pytest.raises(ValueError):
        build_configurable_disruption_plan(
            scenario=example_scenario,
            previous_schedule=previous_schedule,
            replan_at_utc=REPLAN_AT,
            include_outage=False,
            include_weather=False,
            include_urgent_request=False,
        )


def test_replanning_metrics_match_result(replanning_result) -> None:
    metrics = build_replanning_metrics(replanning_result)

    assert metrics.executed_count == replanning_result.executed_count
    assert metrics.frozen_count == replanning_result.frozen_count
    assert metrics.new_objective_value == pytest.approx(
        replanning_result.schedule.objective_value
    )


def test_replanning_changes_have_expected_columns(replanning_result) -> None:
    dataframe = build_replanning_changes_dataframe(replanning_result)

    assert list(dataframe.columns) == REPLANNING_CHANGE_COLUMNS
    assert set(dataframe["change_type"]) <= {
        "UNCHANGED",
        "ADDED",
        "REMOVED",
    }


def test_disruption_metrics_match_result(disruption_result) -> None:
    metrics = build_disruption_metrics(disruption_result)

    assert metrics.added_count == len(disruption_result.added_opportunity_ids)
    assert metrics.removed_count == len(
        disruption_result.removed_opportunity_ids
    )
    assert metrics.added_urgent_request_count == 1


def test_disruption_event_dataframe_contains_three_event_types(
    disruption_result,
) -> None:
    dataframe = build_disruption_events_dataframe(disruption_result)

    assert list(dataframe.columns) == DISRUPTION_EVENT_COLUMNS
    assert set(dataframe["event_type"]) == {
        "SATELLITE_OUTAGE",
        "CLOUD_COVER_UPDATE",
        "URGENT_REQUEST",
    }


def test_disruption_change_dataframe_contains_added_and_removed(
    disruption_result,
) -> None:
    dataframe = build_disruption_changes_dataframe(disruption_result)

    assert set(dataframe["change_type"]) == {"ADDED", "REMOVED"}


def test_experiment_dataframes_have_stable_columns(experiment_result) -> None:
    summary = build_experiment_summary_dataframe(experiment_result)
    pairs = build_experiment_pairs_dataframe(experiment_result)

    assert list(summary.columns) == EXPERIMENT_SUMMARY_COLUMNS
    assert list(pairs.columns) == EXPERIMENT_PAIR_COLUMNS
    assert len(summary) == 2
    assert len(pairs) == 1


def test_experiment_profile_dataframe_combines_algorithms(
    experiment_result,
) -> None:
    dataframe = build_experiment_profile_dataframe(experiment_result)

    assert len(dataframe) == 1
    assert "objective_mean_greedy" in dataframe.columns
    assert "objective_mean_cp_sat" in dataframe.columns
    assert "objective_improvement_pct" in dataframe.columns


@pytest.mark.parametrize(
    "builder",
    [
        build_experiment_objective_figure,
        build_experiment_satisfaction_figure,
        build_experiment_runtime_figure,
        build_experiment_improvement_figure,
    ],
)
def test_experiment_figures_are_created(
    experiment_result,
    builder,
) -> None:
    figure = builder(experiment_result)

    assert isinstance(figure, Figure)
    assert figure.data


def test_experiment_metadata_is_valid_json(experiment_result) -> None:
    payload = json.loads(build_experiment_metadata_json(experiment_result))

    assert payload["base_scenario_id"] == "STRESS"
    assert payload["repetitions"] == 1
    assert payload["cp_sat_better_objective_count"] in {0, 1}
