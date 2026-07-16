from __future__ import annotations

from dataclasses import dataclass


def _validate_memory_reserve_ratio(value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(
            "memory_reserve_ratio musi należeć do zakresu [0, 1]"
        )


def _validate_objective_weights(
    *,
    priority_weight: float,
    quality_weight: float,
    coverage_weight: float,
    mandatory_bonus: float,
    dual_optional_second_bonus: float,
) -> None:
    values = {
        "priority_weight": priority_weight,
        "quality_weight": quality_weight,
        "coverage_weight": coverage_weight,
        "mandatory_bonus": mandatory_bonus,
        "dual_optional_second_bonus": dual_optional_second_bonus,
    }

    for name, value in values.items():
        if value < 0.0:
            raise ValueError(
                f"{name} nie może być wartością ujemną"
            )


@dataclass(frozen=True)
class GreedyPlannerConfig:
    """Parametry ograniczeń i funkcji celu algorytmu Greedy."""

    memory_reserve_ratio: float = 0.0

    priority_weight: float = 10.0
    quality_weight: float = 3.0
    coverage_weight: float = 2.0
    mandatory_bonus: float = 100.0
    dual_optional_second_bonus: float = 5.0

    def __post_init__(self) -> None:
        _validate_memory_reserve_ratio(
            self.memory_reserve_ratio
        )
        _validate_objective_weights(
            priority_weight=self.priority_weight,
            quality_weight=self.quality_weight,
            coverage_weight=self.coverage_weight,
            mandatory_bonus=self.mandatory_bonus,
            dual_optional_second_bonus=(
                self.dual_optional_second_bonus
            ),
        )


@dataclass(frozen=True)
class CpSatPlannerConfig:
    """Parametry ograniczeń, funkcji celu i solvera CP-SAT."""

    memory_reserve_ratio: float = 0.0

    priority_weight: float = 10.0
    quality_weight: float = 3.0
    coverage_weight: float = 2.0
    mandatory_bonus: float = 100.0
    dual_optional_second_bonus: float = 5.0

    force_mandatory_requests: bool = True

    max_time_s: float = 30.0
    num_search_workers: int = 1
    random_seed: int = 20260715
    log_search_progress: bool = False

    objective_scale: int = 1_000_000
    resource_scale: int = 1_000

    def __post_init__(self) -> None:
        _validate_memory_reserve_ratio(
            self.memory_reserve_ratio
        )
        _validate_objective_weights(
            priority_weight=self.priority_weight,
            quality_weight=self.quality_weight,
            coverage_weight=self.coverage_weight,
            mandatory_bonus=self.mandatory_bonus,
            dual_optional_second_bonus=(
                self.dual_optional_second_bonus
            ),
        )

        if self.max_time_s <= 0.0:
            raise ValueError(
                "max_time_s musi być większe od zera"
            )

        if self.num_search_workers <= 0:
            raise ValueError(
                "num_search_workers musi być większe od zera"
            )

        if self.random_seed < 0:
            raise ValueError(
                "random_seed nie może być ujemny"
            )

        if self.objective_scale <= 0:
            raise ValueError(
                "objective_scale musi być większe od zera"
            )

        if self.resource_scale <= 0:
            raise ValueError(
                "resource_scale musi być większe od zera"
            )
