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
