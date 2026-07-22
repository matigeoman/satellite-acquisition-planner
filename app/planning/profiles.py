from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DecisionProfile(str, Enum):
    """Jawny profil preferencji decydenta dla funkcji celu."""

    CUSTOM = "CUSTOM"
    BALANCED = "BALANCED"
    EMERGENCY = "EMERGENCY"
    QUALITY_FIRST = "QUALITY_FIRST"
    THROUGHPUT = "THROUGHPUT"
    SAR_EO_FUSION = "SAR_EO_FUSION"


@dataclass(frozen=True)
class DecisionProfileWeights:
    priority_weight: float
    quality_weight: float
    coverage_weight: float
    mandatory_bonus: float
    dual_optional_second_bonus: float
    scarcity_bonus_weight: float
    conflict_cost_weight: float
    duration_cost_weight: float
    memory_cost_weight: float


_PROFILE_WEIGHTS: dict[DecisionProfile, DecisionProfileWeights] = {
    DecisionProfile.BALANCED: DecisionProfileWeights(
        priority_weight=10.0,
        quality_weight=3.0,
        coverage_weight=2.0,
        mandatory_bonus=100.0,
        dual_optional_second_bonus=5.0,
        scarcity_bonus_weight=2.0,
        conflict_cost_weight=0.20,
        duration_cost_weight=0.010,
        memory_cost_weight=0.00010,
    ),
    DecisionProfile.EMERGENCY: DecisionProfileWeights(
        priority_weight=16.0,
        quality_weight=1.5,
        coverage_weight=1.5,
        mandatory_bonus=180.0,
        dual_optional_second_bonus=3.0,
        scarcity_bonus_weight=4.0,
        conflict_cost_weight=0.10,
        duration_cost_weight=0.005,
        memory_cost_weight=0.00005,
    ),
    DecisionProfile.QUALITY_FIRST: DecisionProfileWeights(
        priority_weight=7.0,
        quality_weight=7.0,
        coverage_weight=5.0,
        mandatory_bonus=100.0,
        dual_optional_second_bonus=6.0,
        scarcity_bonus_weight=1.0,
        conflict_cost_weight=0.15,
        duration_cost_weight=0.005,
        memory_cost_weight=0.00005,
    ),
    DecisionProfile.THROUGHPUT: DecisionProfileWeights(
        priority_weight=8.0,
        quality_weight=1.5,
        coverage_weight=1.0,
        mandatory_bonus=100.0,
        dual_optional_second_bonus=2.0,
        scarcity_bonus_weight=2.5,
        conflict_cost_weight=0.35,
        duration_cost_weight=0.025,
        memory_cost_weight=0.00020,
    ),
    DecisionProfile.SAR_EO_FUSION: DecisionProfileWeights(
        priority_weight=10.0,
        quality_weight=3.0,
        coverage_weight=2.5,
        mandatory_bonus=120.0,
        dual_optional_second_bonus=14.0,
        scarcity_bonus_weight=3.0,
        conflict_cost_weight=0.20,
        duration_cost_weight=0.010,
        memory_cost_weight=0.00010,
    ),
}


def decision_profile_weights(profile: DecisionProfile) -> DecisionProfileWeights:
    if profile == DecisionProfile.CUSTOM:
        raise ValueError("Profil CUSTOM nie posiada narzuconego zestawu wag")
    return _PROFILE_WEIGHTS[profile]


__all__ = [
    "DecisionProfile",
    "DecisionProfileWeights",
    "decision_profile_weights",
]
