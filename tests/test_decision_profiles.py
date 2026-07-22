from __future__ import annotations

import pytest

from app.planning.profiles import DecisionProfile, decision_profile_weights
from app.services.contracts.planning import PlanningOptions


def test_profile_overrides_weights_and_enables_research_heuristic() -> None:
    options = PlanningOptions(
        decision_profile=DecisionProfile.EMERGENCY,
        priority_weight=1.0,
        mandatory_bonus=1.0,
    )
    expected = decision_profile_weights(DecisionProfile.EMERGENCY)

    assert options.priority_weight == expected.priority_weight
    assert options.mandatory_bonus == expected.mandatory_bonus
    assert options.use_opportunity_cost_heuristic is True


def test_custom_profile_preserves_explicit_weights() -> None:
    options = PlanningOptions(
        decision_profile=DecisionProfile.CUSTOM,
        priority_weight=12.5,
        conflict_cost_weight=0.7,
    )

    assert options.priority_weight == 12.5
    assert options.conflict_cost_weight == 0.7
    assert options.use_opportunity_cost_heuristic is False


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="profil decyzyjny"):
        PlanningOptions(decision_profile="UNKNOWN")
