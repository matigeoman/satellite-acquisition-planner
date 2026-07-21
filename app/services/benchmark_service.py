from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter

from app.analysis.algorithm_benchmark import (
    AlgorithmBenchmarkConfig,
    AlgorithmBenchmarkResult,
    BenchmarkRunRecord,
    build_benchmark_pairs,
    build_benchmark_summary,
)
from app.models.enums import PlanningAlgorithm, RequestMode
from app.scenarios.scalability import (
    SOURCE_REQUEST_COUNT,
    build_scalability_source,
    build_scalability_subset,
)
from app.services.contracts.planning import PlanningOptions, PlanningResult
from app.services.planning_service import PlanningService
from app.services.scenario_service import LoadedScenario


class AlgorithmBenchmarkService:
    """Uruchamia kontrolowany benchmark skalowalności planerów."""

    def __init__(
        self,
        *,
        planning_service: PlanningService | None = None,
    ) -> None:
        self.planning_service = planning_service or PlanningService()

    def run(
        self,
        *,
        base_scenario: LoadedScenario,
        config: AlgorithmBenchmarkConfig,
    ) -> AlgorithmBenchmarkResult:
        started_at = datetime.now(timezone.utc)
        timer_start = perf_counter()

        source_scenario = self._build_source_scenario(
            base_scenario=base_scenario,
            maximum_request_count=max(config.request_counts),
        )
        scenarios = {
            request_count: self._build_subset_scenario(
                source_scenario=source_scenario,
                request_count=request_count,
            )
            for request_count in config.request_counts
        }

        records: list[BenchmarkRunRecord] = []
        for request_count in config.request_counts:
            scenario = scenarios[request_count]
            for repetition in range(1, config.repetitions + 1):
                seed_base = (
                    config.base_seed
                    + request_count * 10_000
                    + repetition * 100
                )
                records.append(
                    self._run_single(
                        scenario=scenario,
                        config=config,
                        request_count=request_count,
                        repetition=repetition,
                        algorithm=PlanningAlgorithm.GREEDY,
                        time_limit_s=None,
                        random_seed=seed_base,
                        created_at_utc=started_at,
                    )
                )
                for time_limit_s in config.cp_sat_time_limits_s:
                    records.append(
                        self._run_single(
                            scenario=scenario,
                            config=config,
                            request_count=request_count,
                            repetition=repetition,
                            algorithm=PlanningAlgorithm.CP_SAT,
                            time_limit_s=time_limit_s,
                            random_seed=seed_base,
                            created_at_utc=started_at,
                        )
                    )

        completed_at = datetime.now(timezone.utc)
        wall_clock_runtime_s = round(perf_counter() - timer_start, 6)
        run_records = tuple(records)

        return AlgorithmBenchmarkResult(
            base_scenario_id=base_scenario.scenario_id,
            config=config,
            run_records=run_records,
            pair_records=build_benchmark_pairs(run_records),
            summary_records=build_benchmark_summary(run_records),
            started_at_utc=started_at,
            completed_at_utc=completed_at,
            wall_clock_runtime_s=wall_clock_runtime_s,
        )

    def _build_source_scenario(
        self,
        *,
        base_scenario: LoadedScenario,
        maximum_request_count: int,
    ) -> LoadedScenario:
        if maximum_request_count <= SOURCE_REQUEST_COUNT:
            return base_scenario

        request_set, opportunity_set = build_scalability_source(
            catalog=base_scenario.catalog,
            request_set=base_scenario.request_set,
            opportunity_set=base_scenario.opportunity_set,
            target_request_count=maximum_request_count,
        )
        return LoadedScenario(
            definition=replace(
                base_scenario.definition,
                scenario_id=(
                    f"BENCHMARK-SOURCE-{maximum_request_count:03d}"
                ),
                name=(
                    "Źródło benchmarku — "
                    f"{maximum_request_count} zleceń"
                ),
                description=(
                    "Deterministycznie rozszerzony scenariusz stresowy."
                ),
            ),
            catalog=base_scenario.catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
        )

    def _build_subset_scenario(
        self,
        *,
        source_scenario: LoadedScenario,
        request_count: int,
    ) -> LoadedScenario:
        request_set, opportunity_set = build_scalability_subset(
            catalog=source_scenario.catalog,
            request_set=source_scenario.request_set,
            opportunity_set=source_scenario.opportunity_set,
            request_count=request_count,
        )
        return LoadedScenario(
            definition=replace(
                source_scenario.definition,
                scenario_id=f"BENCHMARK-{request_count:03d}",
                name=f"Benchmark — {request_count} zleceń",
                description=(
                    "Zbalansowany podzbiór do porównania Greedy i CP-SAT."
                ),
            ),
            catalog=source_scenario.catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
        )

    def _run_single(
        self,
        *,
        scenario: LoadedScenario,
        config: AlgorithmBenchmarkConfig,
        request_count: int,
        repetition: int,
        algorithm: PlanningAlgorithm,
        time_limit_s: float | None,
        random_seed: int,
        created_at_utc: datetime,
    ) -> BenchmarkRunRecord:
        options = PlanningOptions(
            algorithm=algorithm,
            memory_reserve_ratio=config.memory_reserve_ratio,
            use_dynamic_transition_model=(
                config.use_dynamic_transition_model
            ),
            cp_sat_time_limit_s=time_limit_s or 1.0,
            cp_sat_num_search_workers=config.cp_sat_num_search_workers,
            cp_sat_random_seed=random_seed,
            cp_sat_force_mandatory_requests=False,
        )
        variant = (
            "GREEDY"
            if algorithm == PlanningAlgorithm.GREEDY
            else f"CP-SAT-{time_limit_s:g}S".replace(".", "P")
        )
        schedule_id = (
            f"SCHEDULE-BENCH-{request_count:03d}-"
            f"R{repetition:02d}-{variant}"
        )
        timer_start = perf_counter()
        try:
            result = self.planning_service.run(
                scenario=scenario,
                options=options,
                schedule_id=schedule_id,
                schedule_name=(
                    f"Benchmark {request_count} — R{repetition:02d} "
                    f"— {variant}"
                ),
                created_at_utc=created_at_utc,
            )
        except Exception as error:
            runtime_s = round(perf_counter() - timer_start, 6)
            return self._build_error_record(
                scenario=scenario,
                request_count=request_count,
                repetition=repetition,
                algorithm=algorithm,
                time_limit_s=time_limit_s,
                random_seed=random_seed,
                runtime_s=runtime_s,
                error=error,
            )

        return self._build_success_record(
            result=result,
            request_count=request_count,
            repetition=repetition,
            time_limit_s=time_limit_s,
            random_seed=random_seed,
        )

    def _build_success_record(
        self,
        *,
        result: PlanningResult,
        request_count: int,
        repetition: int,
        time_limit_s: float | None,
        random_seed: int,
    ) -> BenchmarkRunRecord:
        analysis = result.analysis
        reasons = analysis.unassigned_reason_counts
        return BenchmarkRunRecord(
            request_count=request_count,
            repetition=repetition,
            algorithm=result.algorithm.value,
            time_limit_s=time_limit_s,
            random_seed=random_seed,
            opportunity_count=result.scenario.opportunity_count,
            feasible_opportunity_count=(
                result.scenario.feasible_opportunity_count
            ),
            estimated_boolean_variable_count=(
                _estimate_boolean_variable_count(result.scenario)
            ),
            solver_status=result.solver_status,
            schedule_status=result.schedule.status.value,
            objective_value=result.objective_value,
            fully_satisfied_requests=analysis.fully_satisfied_requests,
            partially_satisfied_requests=(
                analysis.partially_satisfied_requests
            ),
            unassigned_requests=analysis.unassigned_requests,
            mandatory_satisfied_requests=(
                analysis.mandatory_satisfied_requests
            ),
            satisfaction_ratio=analysis.satisfaction_ratio,
            total_acquisitions=analysis.total_acquisitions,
            sar_acquisitions=analysis.sar_acquisitions,
            optical_acquisitions=analysis.optical_acquisitions,
            total_duration_s=analysis.total_duration_s,
            total_data_volume_mb=analysis.total_data_volume_mb,
            average_selected_quality=analysis.average_selected_quality,
            runtime_s=result.wall_clock_runtime_s,
            transition_rejections=reasons.get("TRANSITION_CONFLICT", 0),
            memory_rejections=reasons.get("MEMORY_LIMIT", 0),
            acquisition_limit_rejections=reasons.get(
                "ACQUISITION_LIMIT", 0
            ),
            imaging_time_rejections=reasons.get("IMAGING_TIME_LIMIT", 0),
            dual_separation_rejections=reasons.get(
                "DUAL_SEPARATION_LIMIT", 0
            ),
        )

    def _build_error_record(
        self,
        *,
        scenario: LoadedScenario,
        request_count: int,
        repetition: int,
        algorithm: PlanningAlgorithm,
        time_limit_s: float | None,
        random_seed: int,
        runtime_s: float,
        error: Exception,
    ) -> BenchmarkRunRecord:
        return BenchmarkRunRecord(
            request_count=request_count,
            repetition=repetition,
            algorithm=algorithm.value,
            time_limit_s=time_limit_s,
            random_seed=random_seed,
            opportunity_count=scenario.opportunity_count,
            feasible_opportunity_count=scenario.feasible_opportunity_count,
            estimated_boolean_variable_count=(
                _estimate_boolean_variable_count(scenario)
            ),
            solver_status=type(error).__name__.upper(),
            schedule_status="ERROR",
            objective_value=0.0,
            fully_satisfied_requests=0,
            partially_satisfied_requests=0,
            unassigned_requests=request_count,
            mandatory_satisfied_requests=0,
            satisfaction_ratio=0.0,
            total_acquisitions=0,
            sar_acquisitions=0,
            optical_acquisitions=0,
            total_duration_s=0.0,
            total_data_volume_mb=0.0,
            average_selected_quality=0.0,
            runtime_s=runtime_s,
            transition_rejections=0,
            memory_rejections=0,
            acquisition_limit_rejections=0,
            imaging_time_rejections=0,
            dual_separation_rejections=0,
            error_message=str(error),
        )


def _estimate_boolean_variable_count(scenario: LoadedScenario) -> int:
    dual_optional_count = sum(
        request.request_mode == RequestMode.DUAL_OPTIONAL
        for request in scenario.request_set.active_requests
    )
    return (
        scenario.feasible_opportunity_count
        + scenario.active_request_count
        + dual_optional_count
    )


__all__ = ["AlgorithmBenchmarkService"]
