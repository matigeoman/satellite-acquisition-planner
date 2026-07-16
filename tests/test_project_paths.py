from pathlib import Path

import pytest

from app.config.paths import ProjectPaths


def test_project_paths_normalizes_root(tmp_path: Path) -> None:
    paths = ProjectPaths(tmp_path / "folder" / "..")

    assert paths.root == tmp_path.resolve()


def test_project_paths_exposes_output_directories(tmp_path: Path) -> None:
    paths = ProjectPaths(tmp_path)

    assert paths.reports == tmp_path / "data" / "reports"
    assert paths.benchmarks == tmp_path / "data" / "benchmarks"
    assert paths.stk_imports == tmp_path / "data" / "imports" / "stk"
    assert paths.generated_schedules == (
        tmp_path / "data" / "generated" / "schedules"
    )


def test_example_scenario_paths_are_stable(tmp_path: Path) -> None:
    paths = ProjectPaths(tmp_path)
    scenario = paths.scenario("example")

    assert scenario.catalog == tmp_path / "data" / "example_system.json"
    assert scenario.requests == tmp_path / "data" / "example_requests.json"
    assert scenario.opportunities == (
        tmp_path / "data" / "example_opportunities.json"
    )


def test_stress_scenario_paths_are_stable(tmp_path: Path) -> None:
    scenario = ProjectPaths(tmp_path).scenario("STRESS")

    assert [path.name for path in scenario.all] == [
        "stress_system.json",
        "stress_requests.json",
        "stress_opportunities.json",
    ]


def test_unknown_scenario_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Nieobsługiwany scenariusz"):
        ProjectPaths(tmp_path).scenario("UNKNOWN")


def test_reference_schedule_path_is_case_insensitive(tmp_path: Path) -> None:
    path = ProjectPaths(tmp_path).reference_schedule(
        scenario_id="example",
        algorithm_value="cp_sat",
    )

    assert path == tmp_path / "data" / "example_schedule_cp_sat.json"


def test_unknown_reference_algorithm_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Nieobsługiwany algorytm"):
        ProjectPaths(tmp_path).reference_schedule(
            scenario_id="EXAMPLE",
            algorithm_value="RANDOM",
        )


def test_ensure_output_directories_creates_structure(tmp_path: Path) -> None:
    paths = ProjectPaths(tmp_path)
    paths.ensure_output_directories()

    for directory in (
        paths.reports,
        paths.benchmarks,
        paths.stk_imports,
        paths.generated_schedules,
        paths.generated_reports,
        paths.generated_benchmarks,
    ):
        assert directory.is_dir()
