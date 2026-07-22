from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Iterable

from app.models.catalog import SystemCatalog
from app.models.enums import RequestMode, SensorType
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request_set import ObservationRequestSet
from app.planning.operational import (
    OperationalPlannerConfig,
    dual_pair_is_compatible,
    required_transition_time_s,
)


class ConflictReason(str, Enum):
    """Typ parowego konfliktu pomiędzy okazjami akwizycyjnymi."""

    SAME_REQUEST_ALTERNATIVE = "SAME_REQUEST_ALTERNATIVE"
    DUAL_PAIR_INCOMPATIBLE = "DUAL_PAIR_INCOMPATIBLE"
    SATELLITE_TRANSITION = "SATELLITE_TRANSITION"


@dataclass(frozen=True)
class OpportunityConflict:
    """Jedna krawędź grafu niewykonalności."""

    first_opportunity_id: str
    second_opportunity_id: str
    reasons: tuple[ConflictReason, ...]


@dataclass(frozen=True)
class OpportunityConflictGraph:
    """Nieskierowany graf parowych konfliktów okazji.

    Węzły odpowiadają wykonalnym okazjom, a krawędź oznacza, że para
    nie może jednocześnie należeć do harmonogramu. Ograniczenia globalne,
    takie jak całkowita pamięć lub limit liczby akwizycji, pozostają w
    modelach planerów i celowo nie są sprowadzane do konfliktów parowych.
    """

    opportunity_ids: tuple[str, ...]
    adjacency: dict[str, frozenset[str]]
    conflicts: tuple[OpportunityConflict, ...]

    @property
    def node_count(self) -> int:
        return len(self.opportunity_ids)

    @property
    def edge_count(self) -> int:
        return len(self.conflicts)

    @property
    def density(self) -> float:
        possible = self.node_count * (self.node_count - 1) / 2
        if possible <= 0:
            return 0.0
        return self.edge_count / possible

    def neighbors(self, opportunity_id: str) -> frozenset[str]:
        try:
            return self.adjacency[opportunity_id]
        except KeyError as error:
            raise KeyError(f"Nieznana okazja grafu: {opportunity_id}") from error

    def degree(self, opportunity_id: str) -> int:
        return len(self.neighbors(opportunity_id))

    def connected_components(self) -> tuple[frozenset[str], ...]:
        remaining = set(self.opportunity_ids)
        components: list[frozenset[str]] = []

        while remaining:
            start = min(remaining)
            queue = deque([start])
            component: set[str] = set()
            remaining.remove(start)

            while queue:
                current = queue.popleft()
                component.add(current)
                for neighbor in sorted(self.adjacency[current]):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        queue.append(neighbor)

            components.append(frozenset(component))

        return tuple(
            sorted(
                components,
                key=lambda component: (-len(component), min(component)),
            )
        )

    def reason_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for conflict in self.conflicts:
            for reason in conflict.reasons:
                counts[reason.value] += 1
        return dict(sorted(counts.items()))


class _ConflictAccumulator:
    def __init__(self, opportunity_ids: Iterable[str]) -> None:
        self._adjacency: dict[str, set[str]] = {
            opportunity_id: set() for opportunity_id in opportunity_ids
        }
        self._reasons: dict[tuple[str, str], set[ConflictReason]] = defaultdict(set)

    def add(
        self,
        first_id: str,
        second_id: str,
        reason: ConflictReason,
    ) -> None:
        if first_id == second_id:
            return
        left, right = sorted((first_id, second_id))
        self._adjacency[left].add(right)
        self._adjacency[right].add(left)
        self._reasons[(left, right)].add(reason)

    def build(self) -> OpportunityConflictGraph:
        conflicts = tuple(
            OpportunityConflict(
                first_opportunity_id=first_id,
                second_opportunity_id=second_id,
                reasons=tuple(sorted(reasons, key=lambda reason: reason.value)),
            )
            for (first_id, second_id), reasons in sorted(self._reasons.items())
        )
        return OpportunityConflictGraph(
            opportunity_ids=tuple(sorted(self._adjacency)),
            adjacency={
                opportunity_id: frozenset(sorted(neighbors))
                for opportunity_id, neighbors in sorted(self._adjacency.items())
            },
            conflicts=conflicts,
        )


def build_opportunity_conflict_graph(
    *,
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    config: OperationalPlannerConfig,
) -> OpportunityConflictGraph:
    """Buduje graf niewykonalności zgodny z ograniczeniami planerów."""

    opportunity_set.validate_against(catalog, request_set)
    active_request_ids = {
        request.request_id for request in request_set.active_requests
    }
    opportunities = [
        opportunity
        for opportunity in opportunity_set.feasible_opportunities
        if opportunity.request_id in active_request_ids
    ]
    accumulator = _ConflictAccumulator(
        opportunity.opportunity_id for opportunity in opportunities
    )

    by_request: dict[str, list[AcquisitionOpportunity]] = defaultdict(list)
    by_satellite: dict[str, list[AcquisitionOpportunity]] = defaultdict(list)
    for opportunity in opportunities:
        by_request[opportunity.request_id].append(opportunity)
        by_satellite[opportunity.satellite_id].append(opportunity)

    for request in request_set.active_requests:
        candidates = sorted(
            by_request.get(request.request_id, []),
            key=lambda opportunity: opportunity.opportunity_id,
        )
        for first_index, first in enumerate(candidates):
            for second in candidates[first_index + 1 :]:
                if request.request_mode == RequestMode.SINGLE:
                    accumulator.add(
                        first.opportunity_id,
                        second.opportunity_id,
                        ConflictReason.SAME_REQUEST_ALTERNATIVE,
                    )
                    continue

                if first.sensor_type == second.sensor_type:
                    accumulator.add(
                        first.opportunity_id,
                        second.opportunity_id,
                        ConflictReason.SAME_REQUEST_ALTERNATIVE,
                    )
                    continue

                if not dual_pair_is_compatible(request, first, second):
                    accumulator.add(
                        first.opportunity_id,
                        second.opportunity_id,
                        ConflictReason.DUAL_PAIR_INCOMPATIBLE,
                    )

    satellites = {satellite.satellite_id: satellite for satellite in catalog.satellites}
    sensors = {sensor.sensor_id: sensor for sensor in catalog.sensors}
    modes_by_id = {
        mode.mode_id: mode
        for sensor in catalog.sensors
        for mode in sensor.imaging_modes
    }

    for satellite_id, candidates in by_satellite.items():
        satellite = satellites[satellite_id]
        sensor = sensors[satellite.sensor_id]
        ordered = sorted(
            candidates,
            key=lambda opportunity: (
                opportunity.start_utc,
                opportunity.end_utc,
                opportunity.opportunity_id,
            ),
        )
        transition_upper_bound_s = _transition_upper_bound_s(
            candidates=ordered,
            satellite=satellite,
            sensor_service_time_s=sensor.warmup_time_s + sensor.cooldown_time_s,
            config=config,
        )

        for first_index, first in enumerate(ordered):
            latest_relevant_start = first.end_utc + timedelta(
                seconds=transition_upper_bound_s
            )
            for second in ordered[first_index + 1 :]:
                if second.start_utc > latest_relevant_start:
                    break
                transition_s = required_transition_time_s(
                    first=first,
                    second=second,
                    satellite=satellite,
                    sensor=sensor,
                    modes_by_id=modes_by_id,
                    config=config,
                )
                if first.end_utc + timedelta(seconds=transition_s) <= second.start_utc:
                    continue
                accumulator.add(
                    first.opportunity_id,
                    second.opportunity_id,
                    ConflictReason.SATELLITE_TRANSITION,
                )

    return accumulator.build()


def _transition_upper_bound_s(
    *,
    candidates: list[AcquisitionOpportunity],
    satellite,
    sensor_service_time_s: float,
    config: OperationalPlannerConfig,
) -> float:
    if not config.use_dynamic_transition_model:
        return max(satellite.minimum_transition_time_s, sensor_service_time_s)
    if not candidates:
        return 0.0
    sensor_type = candidates[0].sensor_type
    if sensor_type == SensorType.OPTICAL:
        # Publiczny model Pléiades Neo jest liniowo ekstrapolowany powyżej 60°.
        return max(sensor_service_time_s, 52.0 + config.eo_stabilization_time_s)
    return max(
        sensor_service_time_s,
        180.0 / config.sar_slew_rate_deg_s
        + config.sar_stabilization_time_s
        + config.sar_side_switch_penalty_s
        + config.sar_mode_switch_penalty_s,
    )


__all__ = [
    "ConflictReason",
    "OpportunityConflict",
    "OpportunityConflictGraph",
    "build_opportunity_conflict_graph",
]
