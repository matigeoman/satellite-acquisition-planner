from pathlib import Path

from app.cli import build_parser, main
from app.config.paths import DEFAULT_PATHS, ProjectPaths


def test_source_scenarios_use_nested_directories() -> None:
    for scenario_id in ("EXAMPLE", "STRESS"):
        scenario = DEFAULT_PATHS.scenario(scenario_id)
        assert all(path.is_file() for path in scenario.all)
        assert scenario.catalog.parent.parent == DEFAULT_PATHS.scenarios


def test_reference_schedules_are_separated_from_generated_outputs() -> None:
    for scenario_id in ("EXAMPLE", "STRESS"):
        for algorithm in ("GREEDY", "CP_SAT"):
            path = DEFAULT_PATHS.reference_schedule(
                scenario_id=scenario_id,
                algorithm_value=algorithm,
            )
            assert path.is_file()
            assert DEFAULT_PATHS.reference_schedules in path.parents
            assert DEFAULT_PATHS.generated not in path.parents


def test_legacy_flat_data_files_are_removed() -> None:
    legacy_names = (
        "example_system.json",
        "example_requests.json",
        "example_opportunities.json",
        "stress_system.json",
        "stress_requests.json",
        "stress_opportunities.json",
    )

    assert all(
        not (DEFAULT_PATHS.data / name).exists()
        for name in legacy_names
    )


def test_cli_parser_exposes_main_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["check"]).command == "check"
    assert parser.parse_args(["paths"]).command == "paths"
    assert parser.parse_args(["plan"]).command == "plan"


def test_cli_paths_command_uses_supplied_project_root(
    tmp_path: Path,
    capsys,
) -> None:
    exit_code = main(["paths"], paths=ProjectPaths(tmp_path))
    output = capsys.readouterr().out

    assert exit_code == 0
    assert str(tmp_path.resolve()) in output
    assert "generated_reports" in output
    assert "stk_imports" in output


def test_cli_check_loads_registered_scenarios(capsys) -> None:
    exit_code = main(["check"], paths=DEFAULT_PATHS)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "EXAMPLE" in output
    assert "STRESS" in output
    assert "Struktura i dane wejściowe są poprawne" in output


def test_migration_script_is_available() -> None:
    script = DEFAULT_PATHS.root / "scripts" / "migrate_data_layout.py"
    assert script.is_file()
    assert "--remove-legacy" in script.read_text(encoding="utf-8")
