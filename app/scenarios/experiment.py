from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

from app.models.catalog import SystemCatalog
from app.models.enums import RequestMode, SensorType
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request_set import ObservationRequestSet
from app.services.scenario_service import (
    LoadedScenario,
    ScenarioDefinition,
)


@dataclass(frozen=True)
class ExperimentProfile:
    """Poziom degradacji systemu w eksperymencie Monte Carlo."""

    profile_id: str
    name: str
    resource_ratio: float
    opportunity_dropout_ratio: float

    def __post_init__(self) -> None:
        normalized_id = self.profile_id.strip().upper()
        normalized_name = self.name.strip()

        if not normalized_id:
            raise ValueError("profile_id nie może być pusty")

        if not all(
            character.isalnum() or character == "-" for character in normalized_id
        ):
            raise ValueError(
                "profile_id może zawierać wyłącznie litery, cyfry i myślniki"
            )

        if not normalized_name:
            raise ValueError("name nie może być puste")

        if not 0.0 < self.resource_ratio <= 1.0:
            raise ValueError("resource_ratio musi należeć do zakresu (0, 1]")

        if not 0.0 <= self.opportunity_dropout_ratio < 1.0:
            raise ValueError("opportunity_dropout_ratio musi należeć do zakresu [0, 1)")

        object.__setattr__(
            self,
            "profile_id",
            normalized_id,
        )
        object.__setattr__(
            self,
            "name",
            normalized_name,
        )


DEFAULT_EXPERIMENT_PROFILES = (
    ExperimentProfile(
        profile_id="NOMINAL",
        name="Warunki nominalne z niewielką zmiennością",
        resource_ratio=1.0,
        opportunity_dropout_ratio=0.03,
    ),
    ExperimentProfile(
        profile_id="DEGRADED",
        name="Umiarkowana degradacja dostępności",
        resource_ratio=0.85,
        opportunity_dropout_ratio=0.10,
    ),
    ExperimentProfile(
        profile_id="SEVERE",
        name="Silna degradacja dostępności",
        resource_ratio=0.70,
        opportunity_dropout_ratio=0.20,
    ),
)


@dataclass(frozen=True)
class ExperimentScenarioVariant:
    """Jeden deterministyczny wariant scenariusza eksperymentalnego."""

    scenario: LoadedScenario
    profile: ExperimentProfile
    random_seed: int
    source_feasible_opportunity_count: int
    feasible_opportunity_count: int
    dropped_opportunity_count: int
    protected_opportunity_count: int

    def __post_init__(self) -> None:
        if self.random_seed < 0:
            raise ValueError("random_seed nie może być ujemny")

        count_values = {
            "source_feasible_opportunity_count": (
                self.source_feasible_opportunity_count
            ),
            "feasible_opportunity_count": (self.feasible_opportunity_count),
            "dropped_opportunity_count": (self.dropped_opportunity_count),
            "protected_opportunity_count": (self.protected_opportunity_count),
        }

        for name, value in count_values.items():
            if value < 0:
                raise ValueError(f"{name} nie może być ujemne")

        if (
            self.feasible_opportunity_count + self.dropped_opportunity_count
            != self.source_feasible_opportunity_count
        ):
            raise ValueError("Liczba okazji po degradacji jest niespójna")


def build_experiment_variant(
    *,
    base_scenario: LoadedScenario,
    profile: ExperimentProfile,
    random_seed: int,
) -> ExperimentScenarioVariant:
    """
    Buduje wariant scenariusza przez redukcję zasobów i losowe
    unieważnienie części okien akwizycyjnych.

    Losowanie jest deterministyczne dla podanego ziarna. Najlepsze
    okazje potrzebne do realizacji zleceń obowiązkowych są chronione
    przed losowym usunięciem, ale nadal podlegają ograniczeniom zasobów.
    """

    if random_seed < 0:
        raise ValueError("random_seed nie może być ujemny")

    catalog = _build_experiment_catalog(
        base_catalog=base_scenario.catalog,
        profile=profile,
        random_seed=random_seed,
    )

    request_set = _build_experiment_request_set(
        base_request_set=base_scenario.request_set,
        profile=profile,
        random_seed=random_seed,
    )

    protected_ids = _select_protected_opportunities(
        request_set=base_scenario.request_set,
        opportunity_set=base_scenario.opportunity_set,
    )

    opportunity_set = _build_experiment_opportunity_set(
        base_opportunity_set=base_scenario.opportunity_set,
        catalog=catalog,
        request_set=request_set,
        profile=profile,
        random_seed=random_seed,
        protected_opportunity_ids=protected_ids,
    )

    definition = ScenarioDefinition(
        scenario_id=(f"EXPERIMENT-{profile.profile_id}-{random_seed}"),
        name=(f"Eksperyment {profile.profile_id}, seed {random_seed}"),
        description=(
            f"Wariant scenariusza {base_scenario.scenario_id}; "
            f"zasoby={profile.resource_ratio:.2f}, "
            "odsetek unieważnianych okazji="
            f"{profile.opportunity_dropout_ratio:.2f}."
        ),
        catalog_path=Path("in_memory") / "catalog.json",
        request_set_path=Path("in_memory") / "requests.json",
        opportunity_set_path=(Path("in_memory") / "opportunities.json"),
    )

    scenario = LoadedScenario(
        definition=definition,
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
    )

    source_feasible_count = len(base_scenario.opportunity_set.feasible_opportunities)
    feasible_count = len(opportunity_set.feasible_opportunities)

    return ExperimentScenarioVariant(
        scenario=scenario,
        profile=profile,
        random_seed=random_seed,
        source_feasible_opportunity_count=(source_feasible_count),
        feasible_opportunity_count=feasible_count,
        dropped_opportunity_count=(source_feasible_count - feasible_count),
        protected_opportunity_count=len(protected_ids),
    )


def _build_experiment_catalog(
    *,
    base_catalog: SystemCatalog,
    profile: ExperimentProfile,
    random_seed: int,
) -> SystemCatalog:
    data = base_catalog.model_dump(mode="json")

    suffix = f"{profile.profile_id}-{random_seed}"
    data["catalog_id"] = f"CATALOG-EXP-{suffix}"
    data["name"] = f"{base_catalog.name} — eksperyment {profile.profile_id}"
    data["version"] = "1.0.0"
    data["notes"] = (
        "EXPERIMENT|"
        f"PROFILE={profile.profile_id}|"
        f"SEED={random_seed}|"
        f"RESOURCE_RATIO={profile.resource_ratio:.6f}"
    )

    for satellite in data["satellites"]:
        initial_usage = float(satellite["initial_memory_usage_mb"])
        capacity = float(satellite["memory_capacity_mb"])
        available_memory = capacity - initial_usage

        satellite["memory_capacity_mb"] = round(
            initial_usage + available_memory * profile.resource_ratio,
            6,
        )
        satellite["max_acquisitions_per_day"] = max(
            1,
            math.floor(
                int(satellite["max_acquisitions_per_day"]) * profile.resource_ratio
            ),
        )
        satellite["max_imaging_time_per_day_s"] = round(
            float(satellite["max_imaging_time_per_day_s"]) * profile.resource_ratio,
            6,
        )

    return SystemCatalog.model_validate(data)


def _build_experiment_request_set(
    *,
    base_request_set: ObservationRequestSet,
    profile: ExperimentProfile,
    random_seed: int,
) -> ObservationRequestSet:
    data = base_request_set.model_dump(mode="json")

    suffix = f"{profile.profile_id}-{random_seed}"
    data["request_set_id"] = f"REQSET-EXP-{suffix}"
    data["name"] = f"{base_request_set.name} — eksperyment {profile.profile_id}"
    data["version"] = "1.0.0"
    data["notes"] = f"EXPERIMENT|PROFILE={profile.profile_id}|SEED={random_seed}"

    return ObservationRequestSet.model_validate(data)


def _build_experiment_opportunity_set(
    *,
    base_opportunity_set: AcquisitionOpportunitySet,
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    profile: ExperimentProfile,
    random_seed: int,
    protected_opportunity_ids: set[str],
) -> AcquisitionOpportunitySet:
    rng = random.Random(random_seed)
    data = base_opportunity_set.model_dump(mode="json")

    suffix = f"{profile.profile_id}-{random_seed}"
    data["opportunity_set_id"] = f"OPPSET-EXP-{suffix}"
    data["catalog_id"] = catalog.catalog_id
    data["request_set_id"] = request_set.request_set_id
    data["name"] = f"{base_opportunity_set.name} — eksperyment {profile.profile_id}"
    data["version"] = "1.0.0"
    data["random_seed"] = random_seed
    data["notes"] = (
        "EXPERIMENT|"
        f"PROFILE={profile.profile_id}|"
        f"SEED={random_seed}|"
        "DROPOUT_RATIO="
        f"{profile.opportunity_dropout_ratio:.6f}"
    )

    for opportunity_data in data["opportunities"]:
        opportunity_id = opportunity_data["opportunity_id"]

        if not opportunity_data["is_feasible"]:
            continue

        if opportunity_id in protected_opportunity_ids:
            continue

        if rng.random() >= profile.opportunity_dropout_ratio:
            continue

        opportunity_data["is_feasible"] = False
        reasons = list(opportunity_data.get("infeasibility_reasons") or [])
        reasons.append("EXPERIMENTAL_UNAVAILABILITY")
        opportunity_data["infeasibility_reasons"] = reasons

    opportunity_set = AcquisitionOpportunitySet.model_validate(data)
    opportunity_set.validate_against(
        catalog,
        request_set,
    )

    return opportunity_set


def _select_protected_opportunities(
    *,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
) -> set[str]:
    opportunities_by_request: dict[
        str,
        list[AcquisitionOpportunity],
    ] = {}

    for opportunity in opportunity_set.feasible_opportunities:
        opportunities_by_request.setdefault(
            opportunity.request_id,
            [],
        ).append(opportunity)

    protected_ids: set[str] = set()

    for request in request_set.mandatory_requests:
        candidates = opportunities_by_request.get(
            request.request_id,
            [],
        )

        if request.request_mode == RequestMode.DUAL_REQUIRED:
            for sensor_type in (
                SensorType.SAR,
                SensorType.OPTICAL,
            ):
                selected = _best_opportunity(
                    candidates,
                    sensor_type=sensor_type,
                )
                if selected is not None:
                    protected_ids.add(selected.opportunity_id)
            continue

        selected = _best_opportunity(
            candidates,
            sensor_type=(
                request.requested_sensor_types[0]
                if request.request_mode == RequestMode.SINGLE
                else None
            ),
        )

        if selected is not None:
            protected_ids.add(selected.opportunity_id)

    return protected_ids


def _best_opportunity(
    opportunities: list[AcquisitionOpportunity],
    *,
    sensor_type: SensorType | None,
) -> AcquisitionOpportunity | None:
    candidates = [
        opportunity
        for opportunity in opportunities
        if (sensor_type is None or opportunity.sensor_type == sensor_type)
    ]

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda opportunity: (
            -opportunity.quality_score,
            -opportunity.coverage_ratio,
            opportunity.start_utc,
            opportunity.opportunity_id,
        ),
    )
