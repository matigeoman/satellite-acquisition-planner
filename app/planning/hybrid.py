from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from time import perf_counter
from typing import Iterable

from app.models.catalog import SystemCatalog
from app.models.enums import PlanningAlgorithm, ScheduleStatus
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request_set import ObservationRequestSet
from app.models.schedule import Schedule
from app.planning.config import HybridPlannerConfig
from app.planning.conflict_graph import (
    OpportunityConflictGraph,
    build_opportunity_conflict_graph,
)
from app.planning.cp_sat import CpSatScheduler
from app.planning.fixed import FixedOpportunityAssignment
from app.planning.greedy import GreedyScheduler


class HybridScheduler:
    """Hybryda: Greedy 2.0 jako incumbent i lokalna poprawa CP-SAT.

    Procedura zachowuje plan początkowy i akceptuje wyłącznie rozwiązania,
    które poprawiają funkcję celu bez pogorszenia wykonalności. CP-SAT
    optymalizuje kolejne sąsiedztwa zleceń wyznaczone z grafu konfliktów;
    decyzje poza aktualnym sąsiedztwem pozostają zablokowane.
    """

    def __init__(
        self,
        catalog: SystemCatalog,
        request_set: ObservationRequestSet,
        opportunity_set: AcquisitionOpportunitySet,
        config: HybridPlannerConfig | None = None,
        fixed_assignments: Iterable[FixedOpportunityAssignment] | None = None,
        frozen_until_utc: datetime | None = None,
    ) -> None:
        self.catalog = catalog
        self.request_set = request_set
        self.opportunity_set = opportunity_set
        self.config = config or HybridPlannerConfig()
        self.fixed_assignments = tuple(fixed_assignments or ())
        self.frozen_until_utc = frozen_until_utc
        self.last_solver_status: str | None = None
        self.initial_objective_value: float | None = None
        self.accepted_improvement_count = 0
        self.attempted_neighborhood_count = 0
        self.conflict_graph: OpportunityConflictGraph | None = None

        self._opportunities = [
            opportunity
            for opportunity in opportunity_set.feasible_opportunities
            if opportunity.request_id
            in {request.request_id for request in request_set.active_requests}
        ]
        self._opportunities_by_id = {
            opportunity.opportunity_id: opportunity
            for opportunity in self._opportunities
        }
        self._requests_by_id = {
            request.request_id: request for request in request_set.active_requests
        }

    def build_schedule(
        self,
        *,
        schedule_id: str = "SCHEDULE-HYBRID-001",
        name: str = "Dobowy harmonogram Hybrid",
        created_at_utc: datetime | None = None,
    ) -> Schedule:
        started = perf_counter()

        greedy = GreedyScheduler(
            catalog=self.catalog,
            request_set=self.request_set,
            opportunity_set=self.opportunity_set,
            config=self.config.greedy_config(),
            fixed_assignments=self.fixed_assignments,
            frozen_until_utc=self.frozen_until_utc,
        ).build_schedule(
            schedule_id=schedule_id,
            name=name,
            created_at_utc=created_at_utc,
        )
        self.initial_objective_value = float(greedy.objective_value or 0.0)
        incumbent = greedy

        self.conflict_graph = build_opportunity_conflict_graph(
            catalog=self.catalog,
            request_set=self.request_set,
            opportunity_set=self.opportunity_set,
            config=self.config,
        )
        neighborhoods = self._build_neighborhoods(incumbent)
        solver_statuses: list[str] = []

        for index, neighborhood_request_ids in enumerate(neighborhoods):
            elapsed = perf_counter() - started
            remaining_s = self.config.max_time_s - elapsed
            if remaining_s <= 0.05:
                break

            neighborhoods_left = max(1, len(neighborhoods) - index)
            local_budget_s = max(0.05, remaining_s / neighborhoods_left)
            selected_ids = {
                entry.opportunity_id for entry in incumbent.entries if entry.is_active
            }
            fixed_selection = {
                opportunity.opportunity_id: (
                    opportunity.opportunity_id in selected_ids
                )
                for opportunity in self._opportunities
                if opportunity.request_id not in neighborhood_request_ids
            }

            scheduler = CpSatScheduler(
                catalog=self.catalog,
                request_set=self.request_set,
                opportunity_set=self.opportunity_set,
                config=self.config.cp_sat_config(
                    max_time_s=local_budget_s,
                    random_seed=self.config.random_seed + index,
                ),
                fixed_assignments=self.fixed_assignments,
                frozen_until_utc=self.frozen_until_utc,
                fixed_selection=fixed_selection,
                solution_hint_ids=selected_ids,
            )
            self.attempted_neighborhood_count += 1
            try:
                candidate = scheduler.build_schedule(
                    schedule_id=schedule_id,
                    name=name,
                    created_at_utc=created_at_utc,
                )
            except (RuntimeError, ValueError) as error:
                solver_statuses.append(f"ERROR:{type(error).__name__}")
                continue

            solver_statuses.append(scheduler.last_solver_status or "UNKNOWN")
            if self._accept(candidate, incumbent):
                incumbent = candidate
                self.accepted_improvement_count += 1

        total_runtime_s = round(perf_counter() - started, 6)
        improvement = float(incumbent.objective_value or 0.0) - float(
            self.initial_objective_value or 0.0
        )
        graph = self.conflict_graph
        status_tail = ",".join(solver_statuses) if solver_statuses else "NO_CP_SAT"
        self.last_solver_status = (
            "HYBRID_IMPROVED"
            if improvement > self.config.minimum_improvement
            else "HYBRID_GREEDY_INCUMBENT"
        ) + f"; neighborhoods={self.attempted_neighborhood_count}; {status_tail}"

        notes = (
            "Harmonogram HYBRID: Greedy z heurystyką kosztu utraconych "
            "okazji tworzy rozwiązanie początkowe, a CP-SAT poprawia lokalne "
            "sąsiedztwa grafu konfliktów. Gorsze rozwiązania nie są "
            "przyjmowane przy równym statusie wykonalności. "
            f"Cel początkowy: {self.initial_objective_value:.6f}; "
            f"poprawa: {improvement:.6f}; "
            f"zaakceptowane sąsiedztwa: {self.accepted_improvement_count}/"
            f"{self.attempted_neighborhood_count}. "
            f"Graf: {graph.node_count if graph else 0} węzłów, "
            f"{graph.edge_count if graph else 0} krawędzi. "
            f"Status: {self.last_solver_status}."
        )

        return incumbent.model_copy(
            update={
                "schedule_id": schedule_id,
                "name": name,
                "algorithm": PlanningAlgorithm.HYBRID,
                "solver_runtime_s": total_runtime_s,
                "notes": notes,
            }
        )

    def _accept(self, candidate: Schedule, incumbent: Schedule) -> bool:
        status_rank = {
            ScheduleStatus.INFEASIBLE: 0,
            ScheduleStatus.DRAFT: 1,
            ScheduleStatus.FEASIBLE: 2,
            ScheduleStatus.FINAL: 3,
        }
        candidate_rank = status_rank[candidate.status]
        incumbent_rank = status_rank[incumbent.status]
        if candidate_rank < incumbent_rank:
            return False
        if candidate_rank > incumbent_rank:
            return True
        candidate_objective = float(candidate.objective_value or 0.0)
        incumbent_objective = float(incumbent.objective_value or 0.0)
        return (
            candidate_objective
            >= incumbent_objective + self.config.minimum_improvement
        )

    def _build_neighborhoods(self, incumbent: Schedule) -> tuple[frozenset[str], ...]:
        graph = self.conflict_graph
        if graph is None:
            return ()

        opportunity_to_request = {
            opportunity.opportunity_id: opportunity.request_id
            for opportunity in self._opportunities
        }
        request_neighbors: dict[str, set[str]] = defaultdict(set)
        request_conflict_degree: dict[str, int] = defaultdict(int)
        for conflict in graph.conflicts:
            first_request = opportunity_to_request[conflict.first_opportunity_id]
            second_request = opportunity_to_request[conflict.second_opportunity_id]
            if first_request == second_request:
                continue
            request_neighbors[first_request].add(second_request)
            request_neighbors[second_request].add(first_request)
            request_conflict_degree[first_request] += 1
            request_conflict_degree[second_request] += 1

        unassigned = set(incumbent.unassigned_request_ids)
        mandatory_unassigned = {
            request_id
            for request_id in unassigned
            if self._requests_by_id[request_id].is_mandatory
        }
        seeds = sorted(
            self._requests_by_id,
            key=lambda request_id: (
                -int(request_id in mandatory_unassigned),
                -int(request_id in unassigned),
                -self._requests_by_id[request_id].priority,
                -request_conflict_degree.get(request_id, 0),
                self._requests_by_id[request_id].latest_end_utc,
                request_id,
            ),
        )

        neighborhoods: list[frozenset[str]] = []
        seen: set[frozenset[str]] = set()
        for seed in seeds:
            mandatory_seed_ids = sorted(
                mandatory_unassigned,
                key=lambda request_id: (
                    -self._requests_by_id[request_id].priority,
                    self._requests_by_id[request_id].latest_end_utc,
                    request_id,
                ),
            )[: self.config.neighborhood_request_limit]
            selected = set(mandatory_seed_ids)
            queue = deque([seed, *mandatory_seed_ids])
            visited: set[str] = set()
            while queue and len(selected) < self.config.neighborhood_request_limit:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                selected.add(current)
                ordered_neighbors = sorted(
                    request_neighbors.get(current, set()),
                    key=lambda request_id: (
                        -int(request_id in unassigned),
                        -self._requests_by_id[request_id].priority,
                        -request_conflict_degree.get(request_id, 0),
                        request_id,
                    ),
                )
                queue.extend(ordered_neighbors)

            neighborhood = frozenset(selected)
            if not neighborhood or neighborhood in seen:
                continue
            seen.add(neighborhood)
            neighborhoods.append(neighborhood)
            if len(neighborhoods) >= self.config.max_neighborhoods:
                break

        return tuple(neighborhoods)


def build_hybrid_schedule(
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    *,
    config: HybridPlannerConfig | None = None,
    schedule_id: str = "SCHEDULE-HYBRID-001",
    name: str = "Dobowy harmonogram Hybrid",
    created_at_utc: datetime | None = None,
    fixed_assignments: Iterable[FixedOpportunityAssignment] | None = None,
    frozen_until_utc: datetime | None = None,
) -> Schedule:
    scheduler = HybridScheduler(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=config,
        fixed_assignments=fixed_assignments,
        frozen_until_utc=frozen_until_utc,
    )
    return scheduler.build_schedule(
        schedule_id=schedule_id,
        name=name,
        created_at_utc=created_at_utc,
    )


__all__ = ["HybridScheduler", "build_hybrid_schedule"]
