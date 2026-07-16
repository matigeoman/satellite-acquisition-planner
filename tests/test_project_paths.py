from pathlib import Path

import pytest

from app.config.paths import ProjectPaths


def test_project_paths_normalizes_root(tmp_path: Path) -> None:
    paths = ProjectPaths(tmp_path / "folder" / "..")

    assert paths.root == tmp_path.resolve()


def test_project_paths_exposes_output_directories(tmp_path: Path) -> None:
    paths = ProjectPaths(tmp_path)

    assert paths.scenarios == tmp_path / "data" / "scenarios"
    assert paths.reference_schedules == (
        tmp_path / "data" / "reference_schedules"
    )
    assert paths.reports == tmp_path / "data" / "generated" / "reports"
    assert paths.benchmarks == (
        tmp_path / "data" / "generated" / "benchmarks"
    )
    assert paths.stk_imports == tmp_path / "data" / "imports" / "stk"
    assert paths.generated_schedules == (
        tmp_path / "data" / "generated" / "schedules"
    )


def test_example_scenario_paths_are_stable(tmp_path: Path) -> None:
    paths = ProjectPaths(tmp_path)
    scenario = paths.scenario("example")

    directory = tmp_path / "data" / "scenarios" / "example"
    assert scenario.catalog == directory / "system.json"
    assert scenario.requests == directory / "requests.json"
    assert scenario.opportunities == directory / "opportunities.json"


def test_stress_scenario_paths_are_stable(tmp_path: Path) -> None:
    scenario = ProjectPaths(tmp_path).scenario("STRESS")

    assert [path.name for path in scenario.all] == [
        "system.json",
        "requests.json",
        "opportunities.json",
    ]
    assert scenario.catalog.parent.name == "stress"


def test_unknown_scenario_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Nieobsługiwany scenariusz"):
        ProjectPaths(tmp_path).scenario("UNKNOWN")


def test_reference_schedule_path_is_case_insensitive(tmp_path: Path) -> None:
    path = ProjectPaths(tmp_path).reference_schedule(
        scenario_id="example",
        algorithm_value="cp_sat",
    )

    assert path == (
        tmp_path
        / "data"
        / "reference_schedules"
        / "example"
        / "cp_sat.json"
    )


def test_generated_schedule_path_is_normalized(tmp_path: Path) -> None:
    path = ProjectPaths(tmp_path).generated_schedule(
        scenario_id="STRESS",
        name="Replanned CP SAT",
    )

    assert path == (
        tmp_path
        / "data"
        / "generated"
        / "schedules"
        / "stress"
        / "replanned_cp_sat.json"
    )


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
        paths.generated_schedules / "example",
        paths.generated_schedules / "stress",
    ):
        assert directory.is_dir()
