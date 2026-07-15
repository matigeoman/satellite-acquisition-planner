from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.catalog_loader import load_system_catalog
from app.models.catalog import SystemCatalog
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request_set import ObservationRequestSet
from app.opportunity_loader import load_opportunity_set
from app.request_loader import load_request_set


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ScenarioDefinition:
    """Opis zestawu plików tworzących scenariusz planistyczny."""

    scenario_id: str
    name: str
    description: str

    catalog_path: Path
    request_set_path: Path
    opportunity_set_path: Path

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

    @property
    def required_paths(self) -> tuple[Path, Path, Path]:
        return (
            self.catalog_path,
            self.request_set_path,
            self.opportunity_set_path,
        )

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

        return LoadedScenario(
            definition=definition,
            catalog=catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
        )


def build_default_scenario_definitions(
    project_root: str | Path,
) -> tuple[ScenarioDefinition, ...]:
    """Buduje standardowy rejestr scenariuszy projektu."""

    root = Path(
        project_root
    ).resolve()

    data_directory = (
        root
        / "data"
    )

    return (
        ScenarioDefinition(
            scenario_id="EXAMPLE",
            name="Scenariusz przykładowy",
            description=(
                "Podstawowy scenariusz obejmujący "
                "20 zleceń i 200 okazji akwizycyjnych."
            ),
            catalog_path=(
                data_directory
                / "example_system.json"
            ),
            request_set_path=(
                data_directory
                / "example_requests.json"
            ),
            opportunity_set_path=(
                data_directory
                / "example_opportunities.json"
            ),
        ),
        ScenarioDefinition(
            scenario_id="STRESS",
            name="Scenariusz stresowy",
            description=(
                "Przeciążony scenariusz obejmujący "
                "80 zleceń i 800 okazji akwizycyjnych."
            ),
            catalog_path=(
                data_directory
                / "stress_system.json"
            ),
            request_set_path=(
                data_directory
                / "stress_requests.json"
            ),
            opportunity_set_path=(
                data_directory
                / "stress_opportunities.json"
            ),
        ),
    )