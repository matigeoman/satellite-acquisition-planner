from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_files_and_documentation_index_exist() -> None:
    required = (
        "VERSION",
        "CHANGELOG.md",
        "docs/index.md",
        "docs/installation.md",
        "docs/user_guide.md",
        "docs/architecture.md",
        "docs/data_model.md",
        "docs/planning_model.md",
        "docs/public_data_sources.md",
        "docs/benchmarking.md",
        "docs/scientific_methodology.md",
        "docs/limitations.md",
        "docs/troubleshooting.md",
        "docs/developer_guide.md",
        "docs/quality_and_release.md",
        "docs/docker.md",
        "docs/demo_and_release_check.md",
        "scripts/cleanup_repository.py",
        "app/demo/service.py",
        "app/quality/release_check.py",
        "scripts/generate_poland_demo.py",
        "scripts/verify_poland_demo.ps1",
        "data/scenarios/poland_demo/system.json",
        "data/scenarios/poland_demo/requests.json",
        "data/scenarios/poland_demo/opportunities.json",
        "examples/poland_demo/README.md",
        "examples/poland_demo/orbits_omm.json",
        "examples/poland_demo/access_windows.json",
        "examples/poland_demo/schedule_greedy.json",
        "examples/poland_demo/schedule_cp_sat.json",
        "examples/poland_demo/benchmark_result.json",
        "examples/poland_demo/stk_validation.json",
        "examples/poland_demo/demo_report.html",
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
        ".github/workflows/docker.yml",
    )

    assert all((PROJECT_ROOT / relative).is_file() for relative in required)


def test_quality_workflow_runs_all_project_checks() -> None:
    workflow = (PROJECT_ROOT / ".github/workflows/quality.yml").read_text(
        encoding="utf-8"
    )

    assert 'python-version: "3.11"' in workflow
    assert "pytest -q" in workflow
    assert "ruff check app tests streamlit_app.py scripts" in workflow
    assert "python -m app.cli check" in workflow
    assert "python -m app.cli audit --strict" in workflow
    assert "python -m app.cli release-check --algorithm GREEDY" in workflow


def test_documentation_contains_mermaid_architecture_diagrams() -> None:
    architecture = (PROJECT_ROOT / "docs/architecture.md").read_text(
        encoding="utf-8"
    )
    data_model = (PROJECT_ROOT / "docs/data_model.md").read_text(
        encoding="utf-8"
    )
    planning = (PROJECT_ROOT / "docs/planning_model.md").read_text(
        encoding="utf-8"
    )

    assert "```mermaid" in architecture
    assert "```mermaid" in data_model
    assert "```mermaid" in planning
