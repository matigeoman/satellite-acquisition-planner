from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_repository_defines_cross_platform_text_policy() -> None:
    editorconfig = (PROJECT_ROOT / ".editorconfig").read_text(encoding="utf-8")
    attributes = (PROJECT_ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "charset = utf-8" in editorconfig
    assert "[*.{ps1,bat}]" in editorconfig
    assert "*.py      text eol=lf" in attributes
    assert "*.ps1     text eol=crlf" in attributes
    assert "*.docx binary" in attributes


def test_root_contains_only_active_entrypoint() -> None:
    assert (PROJECT_ROOT / "streamlit_app.py").is_file()
    assert not (PROJECT_ROOT / "main.py").exists()


def test_documentation_has_no_orphaned_duplicate_chapters() -> None:
    assert not (PROJECT_ROOT / "docs" / "algorithm_benchmarks.md").exists()
    assert not (PROJECT_ROOT / "docs" / "planning_architecture.md").exists()

    index = (PROJECT_ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    assert "benchmarking.md" in index
    assert "planning_model.md" in index
