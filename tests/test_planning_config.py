import pytest

from app.planning.config import (
    CpSatPlannerConfig,
    GreedyPlannerConfig,
)


def test_default_objective_weights_are_identical() -> None:
    greedy = GreedyPlannerConfig()
    cp_sat = CpSatPlannerConfig()

    assert greedy.priority_weight == cp_sat.priority_weight
    assert greedy.quality_weight == cp_sat.quality_weight
    assert greedy.coverage_weight == cp_sat.coverage_weight
    assert greedy.mandatory_bonus == cp_sat.mandatory_bonus
    assert (
        greedy.dual_optional_second_bonus
        == cp_sat.dual_optional_second_bonus
    )


@pytest.mark.parametrize(
    "config_type",
    [GreedyPlannerConfig, CpSatPlannerConfig],
)
def test_shared_memory_validation(config_type) -> None:
    with pytest.raises(ValueError):
        config_type(memory_reserve_ratio=-0.01)

    with pytest.raises(ValueError):
        config_type(memory_reserve_ratio=1.01)


@pytest.mark.parametrize(
    "field_name",
    [
        "priority_weight",
        "quality_weight",
        "coverage_weight",
        "mandatory_bonus",
        "dual_optional_second_bonus",
    ],
)
def test_shared_weights_reject_negative_values(field_name: str) -> None:
    with pytest.raises(ValueError):
        GreedyPlannerConfig(**{field_name: -0.01})

    with pytest.raises(ValueError):
        CpSatPlannerConfig(**{field_name: -0.01})


def test_cp_sat_specific_parameters_are_validated() -> None:
    with pytest.raises(ValueError):
        CpSatPlannerConfig(random_seed=-1)

    with pytest.raises(ValueError):
        CpSatPlannerConfig(resource_scale=0)
