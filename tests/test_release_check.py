from __future__ import annotations

from pathlib import Path

from app.cli import build_parser
from app.config.paths import ProjectPaths
from app.models.enums import PlanningAlgorithm
from app.quality import run_release_check


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_check_parser_is_registered() -> None:
    args = build_parser().parse_args(["release-check", "--algorithm", "GREEDY"])

    assert args.command == "release-check"
    assert args.algorithm == "GREEDY"
    assert args.cp_sat_time_limit == 2.0


def test_release_check_validates_full_artifact_pipeline(tmp_path: Path) -> None:
    report = run_release_check(
        ProjectPaths(PROJECT_ROOT),
        algorithms=(PlanningAlgorithm.GREEDY,),
        output_directory=tmp_path,
    )
    steps = {step.name: step for step in report.steps}

    assert report.passed
    assert steps["repository-audit"].passed
    assert steps["scenario-load"].passed
    assert steps["planning-greedy"].passed
    assert steps["project-archive-roundtrip"].passed
    assert steps["scientific-report"].passed
    assert {path.name for path in report.artifact_paths} == {
        "release-check.satplan.zip",
        "release-check-report.zip",
    }
    assert all(path.is_file() and path.stat().st_size > 0 for path in report.artifact_paths)
