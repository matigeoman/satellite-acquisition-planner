from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.config.paths import DEFAULT_PROJECT_ROOT, ProjectPaths
from app.io import (
    load_downlink_opportunity_set,
    load_opportunity_set,
    load_request_set,
    load_system_catalog,
)
from app.models.catalog import SystemCatalog
from app.models.downlink_set import DownlinkOpportunitySet
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request_set import ObservationRequestSet


@dataclass(frozen=True)
class ScenarioDefinition:
    """Opis zestawu plików tworzących scenariusz planistyczny."""

    scenario_id: str
    name: str
    description: str

    catalog_path: Path
    request_set_path: Path
    opportunity_set_path: Path
    downlink_set_path: Path | None = None

    def __post_init__(self) -> None:
        normalized_id = self.scenario_id.strip().upper()
        normalized_name = self.name.strip()
        normalized_description = self.description.strip()

        if not normalized_id:
            raise ValueError(
                "scenario_id nie może być pusty"
            )

        if not normalized_name:
            raise ValueError(
                "name nie może być puste"
            )

        if not normalized_description:
            raise ValueError(
                "description nie może być pusty"
            )

        object.__setattr__(
            self,
            "scenario_id",
            normalized_id,
        )

        object.__setattr__(
            self,
            "name",
            normalized_name,
        )

        object.__setattr__(
            self,
            "description",
            normalized_description,
        )

        object.__setattr__(
            self,
            "catalog_path",
            Path(self.catalog_path),
        )

        object.__setattr__(
            self,
            "request_set_path",
            Path(self.request_set_path),
        )

        object.__setattr__(
            self,
            "opportunity_set_path",
            Path(self.opportunity_set_path),
        )
        if self.downlink_set_path is not None:
            object.__setattr__(
                self,
                "downlink_set_path",
                Path(self.downlink_set_path),
            )

    @property
    def required_paths(self) -> tuple[Path, ...]:
        paths = [
            self.catalog_path,
            self.request_set_path,
            self.opportunity_set_path,
        ]
        if self.downlink_set_path is not None:
            paths.append(self.downlink_set_path)
        return tuple(paths)

    def validate_files(self) -> None:
        """Sprawdza obecność wszystkich plików scenariusza."""

        missing_paths = [
            path
            for path in self.required_paths
            if not path.is_file()
        ]

        if missing_paths:
            missing_text = ", ".join(
                str(path)
                for path in missing_paths
            )

            raise FileNotFoundError(
                "Brak plików scenariusza: "
                f"{missing_text}"
            )


@dataclass(frozen=True)
class LoadedScenario:
    """Załadowane i zwalidowane dane wejściowe planowania."""

    definition: ScenarioDefinition
    catalog: SystemCatalog
    request_set: ObservationRequestSet
    opportunity_set: AcquisitionOpportunitySet
    downlink_set: DownlinkOpportunitySet | None = None

    @property
    def scenario_id(self) -> str:
        return self.definition.scenario_id

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def active_request_count(self) -> int:
        return len(
            self.request_set.active_requests
        )

    @property
    def mandatory_request_count(self) -> int:
        return len(
            self.request_set.mandatory_requests
        )

    @property
    def opportunity_count(self) -> int:
        return len(
            self.opportunity_set.opportunities
        )

    @property
    def feasible_opportunity_count(self) -> int:
        return len(
            self.opportunity_set.feasible_opportunities
        )

    @property
    def satellite_count(self) -> int:
        return len(
            self.catalog.satellites
        )

    @property
    def ground_station_count(self) -> int:
        return len(self.catalog.ground_stations)

    @property
    def downlink_opportunity_count(self) -> int:
        if self.downlink_set is None:
            return 0
        return len(self.downlink_set.feasible_opportunities)


class ScenarioService:
    """Rejestruje i ładuje scenariusze dostępne w aplikacji."""

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        definitions: Iterable[
            ScenarioDefinition
        ] | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
            if project_root is not None
            else DEFAULT_PROJECT_ROOT
        ).resolve()

        if definitions is None:
            definitions = build_default_scenario_definitions(
                self.project_root
            )

        definition_list = list(
            definitions
        )

        if not definition_list:
            raise ValueError(
                "ScenarioService wymaga co najmniej "
                "jednej definicji scenariusza"
            )

        self._definitions: dict[
            str,
            ScenarioDefinition,
        ] = {}

        for definition in definition_list:
            scenario_id = (
                definition.scenario_id
            )

            if scenario_id in self._definitions:
                raise ValueError(
                    "Powtórzony scenario_id: "
                    f"{scenario_id}"
                )

            self._definitions[
                scenario_id
            ] = definition

    @property
    def definitions(
        self,
    ) -> tuple[ScenarioDefinition, ...]:
        return tuple(
            self._definitions[
                scenario_id
            ]
            for scenario_id in sorted(
                self._definitions
            )
        )

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        return tuple(
            definition.scenario_id
            for definition in self.definitions
        )

    def get_definition(
        self,
        scenario_id: str,
    ) -> ScenarioDefinition:
        normalized_id = (
            scenario_id.strip().upper()
        )

        try:
            return self._definitions[
                normalized_id
            ]
        except KeyError as error:
            available = ", ".join(
                self.scenario_ids
            )

            raise KeyError(
                "Nieznany scenariusz: "
                f"{normalized_id}. "
                f"Dostępne: {available}"
            ) from error

    def load(
        self,
        scenario_id: str,
    ) -> LoadedScenario:
        definition = self.get_definition(
            scenario_id
        )

        definition.validate_files()

        catalog = load_system_catalog(
            definition.catalog_path
        )

        request_set = load_request_set(
            definition.request_set_path
        )

        opportunity_set = load_opportunity_set(
            definition.opportunity_set_path,
            catalog=catalog,
            request_set=request_set,
        )

        downlink_set = None
        if definition.downlink_set_path is not None:
            downlink_set = load_downlink_opportunity_set(
                definition.downlink_set_path,
                catalog=catalog,
            )
            if (
                downlink_set.horizon_start_utc
                != request_set.horizon_start_utc
                or downlink_set.horizon_end_utc
                != request_set.horizon_end_utc
            ):
                raise ValueError(
                    "Horyzont downlinków jest niezgodny ze scenariuszem"
                )

        return LoadedScenario(
            definition=definition,
            catalog=catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
            downlink_set=downlink_set,
        )


def build_default_scenario_definitions(
    project_root: str | Path,
) -> tuple[ScenarioDefinition, ...]:
    """Buduje standardowy rejestr scenariuszy projektu."""

    paths = ProjectPaths(Path(project_root))
    example = paths.scenario("EXAMPLE")
    stress = paths.scenario("STRESS")
    poland_demo = paths.scenario("POLAND_DEMO")

    return (
        ScenarioDefinition(
            scenario_id="EXAMPLE",
            name="Scenariusz przykładowy",
            description=(
                "Podstawowy scenariusz obejmujący "
                "20 zleceń i 200 okazji akwizycyjnych."
            ),
            catalog_path=example.catalog,
            request_set_path=example.requests,
            opportunity_set_path=example.opportunities,
            downlink_set_path=example.downlinks,
        ),
        ScenarioDefinition(
            scenario_id="STRESS",
            name="Scenariusz stresowy",
            description=(
                "Przeciążony scenariusz obejmujący "
                "80 zleceń i 800 okazji akwizycyjnych."
            ),
            catalog_path=stress.catalog,
            request_set_path=stress.requests,
            opportunity_set_path=stress.opportunities,
            downlink_set_path=stress.downlinks,
        ),
        ScenarioDefinition(
            scenario_id="POLAND_DEMO",
            name="Polska — rozbudowany scenariusz demonstracyjny",
            description=(
                "48-godzinny scenariusz obejmujący 50 zleceń SAR, EO "
                "i SAR+EO oraz 500 zróżnicowanych okazji."
            ),
            catalog_path=poland_demo.catalog,
            request_set_path=poland_demo.requests,
            opportunity_set_path=poland_demo.opportunities,
            downlink_set_path=poland_demo.downlinks,
        ),
    )
