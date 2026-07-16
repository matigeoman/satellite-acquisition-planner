from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScenarioPaths:
    """Ścieżki plików wejściowych jednego scenariusza."""

    catalog: Path
    requests: Path
    opportunities: Path

    @property
    def all(self) -> tuple[Path, Path, Path]:
        return (
            self.catalog,
            self.requests,
            self.opportunities,
        )


@dataclass(frozen=True)
class ProjectPaths:
    """Centralny rejestr ścieżek projektu.

    Dane źródłowe, harmonogramy referencyjne, importy zewnętrzne i wyniki
    generowane są rozdzielone. Moduły aplikacji nie powinny samodzielnie
    składać ścieżek względem katalogu ``data``.
    """

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).resolve())

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def scenarios(self) -> Path:
        return self.data / "scenarios"

    @property
    def reference_schedules(self) -> Path:
        return self.data / "reference_schedules"

    @property
    def imports(self) -> Path:
        return self.data / "imports"

    @property
    def stk_imports(self) -> Path:
        return self.imports / "stk"

    @property
    def generated(self) -> Path:
        return self.data / "generated"

    @property
    def generated_schedules(self) -> Path:
        return self.generated / "schedules"

    @property
    def generated_reports(self) -> Path:
        return self.generated / "reports"

    @property
    def generated_benchmarks(self) -> Path:
        return self.generated / "benchmarks"

    @property
    def generated_orbits(self) -> Path:
        """Cache publicznych elementów orbitalnych GP/OMM."""

        return self.generated / "orbits"

    # Krótkie aliasy zachowują czytelność starszych modułów.
    @property
    def reports(self) -> Path:
        return self.generated_reports

    @property
    def benchmarks(self) -> Path:
        return self.generated_benchmarks

    @property
    def experimental_validation_reports(self) -> Path:
        return self.generated_reports / "experimental_validation"

    @staticmethod
    def _scenario_slug(scenario_id: str) -> str:
        normalized = scenario_id.strip().upper()
        slugs = {
            "EXAMPLE": "example",
            "STRESS": "stress",
        }

        try:
            return slugs[normalized]
        except KeyError as error:
            raise ValueError(
                f"Nieobsługiwany scenariusz: {scenario_id}"
            ) from error

    def scenario_directory(self, scenario_id: str) -> Path:
        return self.scenarios / self._scenario_slug(scenario_id)

    def scenario(self, scenario_id: str) -> ScenarioPaths:
        """Zwraca pliki wejściowe zarejestrowanego scenariusza."""

        directory = self.scenario_directory(scenario_id)
        return ScenarioPaths(
            catalog=directory / "system.json",
            requests=directory / "requests.json",
            opportunities=directory / "opportunities.json",
        )

    def reference_schedule(
        self,
        *,
        scenario_id: str,
        algorithm_value: str,
    ) -> Path:
        """Zwraca referencyjny harmonogram Greedy lub CP-SAT."""

        normalized_algorithm = algorithm_value.strip().upper()
        filenames = {
            "GREEDY": "greedy.json",
            "CP_SAT": "cp_sat.json",
        }

        try:
            filename = filenames[normalized_algorithm]
        except KeyError as error:
            raise ValueError(
                f"Nieobsługiwany algorytm: {algorithm_value}"
            ) from error

        return (
            self.reference_schedules
            / self._scenario_slug(scenario_id)
            / filename
        )

    def generated_schedule(
        self,
        *,
        scenario_id: str,
        name: str,
    ) -> Path:
        """Buduje ścieżkę roboczego harmonogramu generowanego przez aplikację."""

        normalized_name = name.strip().lower().replace(" ", "_")
        if not normalized_name:
            raise ValueError("name nie może być puste")

        return (
            self.generated_schedules
            / self._scenario_slug(scenario_id)
            / f"{normalized_name}.json"
        )

    def ensure_output_directories(self) -> None:
        """Tworzy katalogi przeznaczone na importy i wyniki programu."""

        directories = (
            self.stk_imports,
            self.generated_schedules,
            self.generated_reports,
            self.generated_benchmarks,
            self.generated_orbits,
        )

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        for scenario_id in ("EXAMPLE", "STRESS"):
            self.generated_schedule(
                scenario_id=scenario_id,
                name="placeholder",
            ).parent.mkdir(parents=True, exist_ok=True)


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATHS = ProjectPaths(DEFAULT_PROJECT_ROOT)
PROJECT_ROOT = DEFAULT_PATHS.root
