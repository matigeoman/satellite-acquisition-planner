from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.analysis.experimental_validation import (
    ExperimentalValidationConfig,
    ExperimentalValidationService,
    export_experimental_validation,
)
from app.scenarios.experiment import (
    ExperimentProfile,
    build_experiment_variant,
)
from app.services.scenario_service import ScenarioService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def stress_scenario():
    return ScenarioService(
        project_root=PROJECT_ROOT
    ).load("STRESS")


@pytest.fixture
def quick_profile() -> ExperimentProfile:
    return ExperimentProfile(
        profile_id="TEST",
        name="Profil testowy",
        resource_ratio=0.9,
        opportunity_dropout_ratio=0.08,
    )


def test_profile_normalizes_identifier() -> None:
    profile = ExperimentProfile(
        profile_id=" test-profile ",
        name=" Test ",
        resource_ratio=1.0,
        opportunity_dropout_ratio=0.0,
    )

    assert profile.profile_id == "TEST-PROFILE"
    assert profile.name == "Test"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("resource_ratio", 0.0),
        ("resource_ratio", 1.1),
        ("opportunity_dropout_ratio", -0.1),
        ("opportunity_dropout_ratio", 1.0),
    ],
)
def test_profile_rejects_invalid_ratios(
    field: str,
    value: float,
) -> None:
    data = {
        "profile_id": "TEST",
        "name": "Test",
        "resource_ratio": 1.0,
        "opportunity_dropout_ratio": 0.1,
    }
    data[field] = value

    with pytest.raises(ValueError):
        ExperimentProfile(**data)


def test_variant_is_reproducible(
    stress_scenario,
    quick_profile: ExperimentProfile,
) -> None:
    first = build_experiment_variant(
        base_scenario=stress_scenario,
        profile=quick_profile,
        random_seed=1234,
    )
    second = build_experiment_variant(
        base_scenario=stress_scenario,
        profile=quick_profile,
        random_seed=1234,
    )

    assert (
        first.scenario.opportunity_set.model_dump(mode="json")
        == second.scenario.opportunity_set.model_dump(mode="json")
    )
    assert first.dropped_opportunity_count == (
        second.dropped_opportunity_count
    )


def test_different_seeds_change_variant(
    stress_scenario,
    quick_profile: ExperimentProfile,
) -> None:
    first = build_experiment_variant(
        base_scenario=stress_scenario,
        profile=quick_profile,
        random_seed=100,
    )
    second = build_experiment_variant(
        base_scenario=stress_scenario,
        profile=quick_profile,
        random_seed=101,
    )

    first_feasible = {
        opportunity.opportunity_id
        for opportunity in (
            first.scenario.opportunity_set.feasible_opportunities
        )
    }
    second_feasible = {
        opportunity.opportunity_id
        for opportunity in (
            second.scenario.opportunity_set.feasible_opportunities
        )
    }

    assert first_feasible != second_feasible


def test_variant_scales_satellite_resources(
    stress_scenario,
    quick_profile: ExperimentProfile,
) -> None:
    variant = build_experiment_variant(
        base_scenario=stress_scenario,
        profile=quick_profile,
        random_seed=777,
    )

    base_by_id = {
        satellite.satellite_id: satellite
        for satellite in stress_scenario.catalog.satellites
    }

    for satellite in variant.scenario.catalog.satellites:
        base = base_by_id[satellite.satellite_id]

        assert (
            satellite.max_acquisitions_per_day
            <= base.max_acquisitions_per_day
        )
        assert (
            satellite.max_imaging_time_per_day_s
            == pytest.approx(
                base.max_imaging_time_per_day_s
                * quick_profile.resource_ratio
            )
        )
        assert (
            satellite.memory_capacity_mb
            <= base.memory_capacity_mb
        )


def test_variant_identifiers_are_consistent(
    stress_scenario,
    quick_profile: ExperimentProfile,
) -> None:
    variant = build_experiment_variant(
        base_scenario=stress_scenario,
        profile=quick_profile,
        random_seed=42,
    )

    scenario = variant.scenario

    assert (
        scenario.opportunity_set.catalog_id
        == scenario.catalog.catalog_id
    )
    assert (
        scenario.opportunity_set.request_set_id
        == scenario.request_set.request_set_id
    )

    scenario.opportunity_set.validate_against(
        scenario.catalog,
        scenario.request_set,
    )


def test_mandatory_requests_keep_protected_opportunities(
    stress_scenario,
) -> None:
    profile = ExperimentProfile(
        profile_id="MAXDROP",
        name="Maksymalne testowe usuwanie",
        resource_ratio=1.0,
        opportunity_dropout_ratio=0.99,
    )

    variant = build_experiment_variant(
        base_scenario=stress_scenario,
        profile=profile,
        random_seed=99,
    )

    feasible_request_ids = {
        opportunity.request_id
        for opportunity in (
            variant.scenario.opportunity_set.feasible_opportunities
        )
    }

    for request in stress_scenario.request_set.mandatory_requests:
        assert request.request_id in feasible_request_ids


def test_config_rejects_duplicate_profiles(
    quick_profile: ExperimentProfile,
) -> None:
    with pytest.raises(ValueError):
        ExperimentalValidationConfig(
            profiles=(quick_profile, quick_profile),
            repetitions=1,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repetitions", 0),
        ("base_seed", -1),
        ("cp_sat_time_limit_s", 0.0),
        ("cp_sat_num_search_workers", 0),
    ],
)
def test_config_rejects_invalid_values(
    quick_profile: ExperimentProfile,
    field: str,
    value: int | float,
) -> None:
    data = {
        "profiles": (quick_profile,),
        "repetitions": 1,
        "base_seed": 1,
        "cp_sat_time_limit_s": 0.1,
        "cp_sat_num_search_workers": 1,
    }
    data[field] = value

    with pytest.raises(ValueError):
        ExperimentalValidationConfig(**data)


def test_service_builds_expected_records(
    stress_scenario,
    quick_profile: ExperimentProfile,
) -> None:
    result = ExperimentalValidationService().run(
        base_scenario=stress_scenario,
        config=ExperimentalValidationConfig(
            profiles=(quick_profile,),
            repetitions=1,
            base_seed=555,
            cp_sat_time_limit_s=0.1,
        ),
    )

    assert len(result.run_records) == 2
    assert len(result.pair_records) == 1
    assert len(result.summary_records) == 2
    assert {
        record.algorithm
        for record in result.run_records
    } == {"GREEDY", "CP_SAT"}

    pair = result.pair_records[0]
    assert pair.random_seed == 555
    assert pair.cp_sat_solver_status in {
        "OPTIMAL",
        "FEASIBLE",
        "UNKNOWN",
    }


def test_result_metrics_are_consistent(
    stress_scenario,
    quick_profile: ExperimentProfile,
) -> None:
    result = ExperimentalValidationService().run(
        base_scenario=stress_scenario,
        config=ExperimentalValidationConfig(
            profiles=(quick_profile,),
            repetitions=1,
            base_seed=556,
            cp_sat_time_limit_s=0.1,
        ),
    )

    pair = result.pair_records[0]

    assert pair.objective_difference == pytest.approx(
        pair.cp_sat_objective_value
        - pair.greedy_objective_value,
        abs=1e-6,
    )
    assert 0 <= result.cp_sat_better_objective_count <= 1
    assert 0 <= result.cp_sat_not_worse_objective_count <= 1


def test_export_writes_csv_json_and_charts(
    stress_scenario,
    quick_profile: ExperimentProfile,
    tmp_path: Path,
) -> None:
    result = ExperimentalValidationService().run(
        base_scenario=stress_scenario,
        config=ExperimentalValidationConfig(
            profiles=(quick_profile,),
            repetitions=1,
            base_seed=557,
            cp_sat_time_limit_s=0.1,
        ),
    )

    paths = export_experimental_validation(
        result,
        tmp_path,
        prefix="validation_test",
    )

    assert set(paths) == {
        "runs_csv",
        "pairs_csv",
        "summary_csv",
        "metadata_json",
        "objective_chart",
        "satisfaction_chart",
        "runtime_chart",
        "improvement_chart",
    }

    for path in paths.values():
        assert path.is_file()
        assert path.stat().st_size > 0

    with paths["runs_csv"].open(
        encoding="utf-8-sig"
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 2

    metadata = json.loads(
        paths["metadata_json"].read_text(
            encoding="utf-8"
        )
    )
    assert metadata["base_scenario_id"] == "STRESS"
    assert metadata["pair_count"] == 1


def test_export_rejects_path_in_prefix(
    stress_scenario,
    quick_profile: ExperimentProfile,
    tmp_path: Path,
) -> None:
    result = ExperimentalValidationService().run(
        base_scenario=stress_scenario,
        config=ExperimentalValidationConfig(
            profiles=(quick_profile,),
            repetitions=1,
            base_seed=558,
            cp_sat_time_limit_s=0.1,
        ),
    )

    with pytest.raises(ValueError):
        export_experimental_validation(
            result,
            tmp_path,
            prefix="folder/invalid",
        )
