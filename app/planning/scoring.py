from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Protocol

from app.models.enums import RequestMode, SensorType
from app.models.opportunity import AcquisitionOpportunity
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet


class ObjectiveScoringConfig(Protocol):
    """Minimalny zestaw wag wymagany przez wspólną funkcję celu."""

    priority_weight: float
    quality_weight: float
    coverage_weight: float
    mandatory_bonus: float
    dual_optional_second_bonus: float


def request_reward(
    request: ObservationRequest,
    config: ObjectiveScoringConfig,
) -> float:
    """Zwraca nagrodę naliczaną raz za zrealizowanie zlecenia."""

    reward = request.priority * config.priority_weight

    if request.is_mandatory:
        reward += config.mandatory_bonus

    return round(reward, 6)


def acquisition_score(
    opportunity: AcquisitionOpportunity,
    config: ObjectiveScoringConfig,
) -> float:
    """Wyznacza część funkcji celu zależną od jakości akwizycji."""

    score = (
        opportunity.quality_score * config.quality_weight
        + opportunity.coverage_ratio * config.coverage_weight
    )

    return round(score, 6)


def calculate_objective_contributions(
    *,
    request_set: ObservationRequestSet,
    selected_opportunities: Iterable[AcquisitionOpportunity],
    config: ObjectiveScoringConfig,
) -> dict[str, float]:
    """Rozdziela wspólną funkcję celu na wpisy harmonogramu.

    Nagroda priorytetowa i premia obowiązkowości są naliczane raz na
    zrealizowane zlecenie. Dla ``DUAL_REQUIRED`` nagroda jest dzielona
    pomiędzy SAR i EO wyłącznie wtedy, gdy komplet obu akwizycji istnieje.
    """

    selected_by_request: dict[
        str,
        list[AcquisitionOpportunity],
    ] = defaultdict(list)

    for opportunity in selected_opportunities:
        selected_by_request[
            opportunity.request_id
        ].append(opportunity)

    contributions: dict[str, float] = {}

    for request_id, opportunities in selected_by_request.items():
        request = request_set.get_request(request_id)
        reward = request_reward(request, config)

        if request.request_mode == RequestMode.SINGLE:
            opportunity = opportunities[0]
            contributions[opportunity.opportunity_id] = round(
                reward + acquisition_score(opportunity, config),
                6,
            )
            continue

        if request.request_mode == RequestMode.DUAL_REQUIRED:
            sensor_types = {
                opportunity.sensor_type
                for opportunity in opportunities
            }
            is_complete = (
                len(opportunities) == 2
                and sensor_types
                == {SensorType.SAR, SensorType.OPTICAL}
            )
            reward_share = (
                reward / len(opportunities)
                if is_complete
                else 0.0
            )

            for opportunity in opportunities:
                contributions[opportunity.opportunity_id] = round(
                    reward_share
                    + acquisition_score(opportunity, config),
                    6,
                )
            continue

        ordered_opportunities = sorted(
            opportunities,
            key=lambda opportunity: (
                -acquisition_score(opportunity, config),
                opportunity.opportunity_id,
            ),
        )
        primary_opportunity = ordered_opportunities[0]
        contributions[primary_opportunity.opportunity_id] = round(
            reward
            + acquisition_score(primary_opportunity, config),
            6,
        )

        for secondary_opportunity in ordered_opportunities[1:]:
            contributions[
                secondary_opportunity.opportunity_id
            ] = round(
                acquisition_score(secondary_opportunity, config)
                + config.dual_optional_second_bonus,
                6,
            )

    return contributions
