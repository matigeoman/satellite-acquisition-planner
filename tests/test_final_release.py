from __future__ import annotations

from pathlib import Path

from app.version import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_final_release_version_and_assets_are_consistent() -> None:
    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert __version__ == version == "1.4.0"

    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    workflow = (PROJECT_ROOT / ".github/workflows/docker.yml").read_text(
        encoding="utf-8"
    )

    assert "ARG APP_VERSION=dev" in dockerfile
    assert "image: satplan:${APP_VERSION:-dev}" in compose
    assert "APP_VERSION=${{ env.APP_VERSION }}" in workflow
    assert "tr -d" in workflow and "VERSION" in workflow


def test_final_release_contains_no_root_update_artifacts() -> None:
    forbidden_patterns = (
        "satplan-*.zip",
        "*.patch",
        "*_NOTES.txt",
        "*_README.txt",
        "README_*.txt",
        "run_*_checks.ps1",
        "report.*",
    )
    matches = {
        path.name
        for pattern in forbidden_patterns
        for path in PROJECT_ROOT.glob(pattern)
        if path.is_file()
    }

    assert not matches
    assert not (PROJECT_ROOT / "main.py").exists()


def test_release_notes_define_validation_and_compatibility() -> None:
    notes = (PROJECT_ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "scripts/verify_release.ps1").read_text(encoding="utf-8")

    assert "verify_release.ps1 -Docker -NoCache" in notes
    assert "Nie jest wymagana migracja danych" in notes
    assert "release-check --algorithm ALL" in script
    assert 'FINAL RELEASE $Version: READY' in script
