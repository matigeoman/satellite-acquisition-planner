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

    Wszystkie moduły aplikacji korzystają z tej klasy zamiast samodzielnie
    wyznaczać katalog główny i składać ścieżki do danych. Dzięki temu zmiana
    układu katalogów nie wymaga edytowania wielu niezależnych plików.
    """

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).resolve())

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def reports(self) -> Path:
        return self.data / "reports"

    @property
    def benchmarks(self) -> Path:
        return self.data / "benchmarks"

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
    def experimental_validation_reports(self) -> Path:
        return self.reports / "experimental_validation"

    def scenario(self, scenario_id: str) -> ScenarioPaths:
        """Zwraca pliki wejściowe zarejestrowanego scenariusza."""

        normalized = scenario_id.strip().upper()
        filenames = {
            "EXAMPLE": (
                "example_system.json",
                "example_requests.json",
                "example_opportunities.json",
            ),
            "STRESS": (
                "stress_system.json",
                "stress_requests.json",
                "stress_opportunities.json",
            ),
        }

        try:
            catalog_name, requests_name, opportunities_name = filenames[
                normalized
            ]
        except KeyError as error:
            raise ValueError(
                f"Nieobsługiwany scenariusz: {scenario_id}"
            ) from error

        return ScenarioPaths(
            catalog=self.data / catalog_name,
            requests=self.data / requests_name,
            opportunities=self.data / opportunities_name,
        )

    def reference_schedule(
        self,
        *,
        scenario_id: str,
        algorithm_value: str,
    ) -> Path:
        """Zwraca ścieżkę referencyjnego harmonogramu Greedy lub CP-SAT."""

        normalized_scenario = scenario_id.strip().upper()
        normalized_algorithm = algorithm_value.strip().upper()

        scenario_prefixes = {
            "EXAMPLE": "example_schedule",
            "STRESS": "stress_schedule",
        }

        try:
            prefix = scenario_prefixes[normalized_scenario]
        except KeyError as error:
            raise ValueError(
                f"Nieobsługiwany scenariusz: {scenario_id}"
            ) from error

        if normalized_algorithm not in {"GREEDY", "CP_SAT"}:
            raise ValueError(
                f"Nieobsługiwany algorytm: {algorithm_value}"
            )

        return self.data / (
            f"{prefix}_{normalized_algorithm.lower()}.json"
        )

    def ensure_output_directories(self) -> None:
        """Tworzy katalogi przeznaczone na importy i wyniki programu."""

        for directory in (
            self.reports,
            self.benchmarks,
            self.stk_imports,
            self.generated_schedules,
            self.generated_reports,
            self.generated_benchmarks,
        ):
            directory.mkdir(parents=True, exist_ok=True)


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATHS = ProjectPaths(DEFAULT_PROJECT_ROOT)
PROJECT_ROOT = DEFAULT_PATHS.root
