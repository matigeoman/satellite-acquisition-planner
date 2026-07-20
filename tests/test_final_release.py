from __future__ import annotations

from pathlib import Path

from app.version import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_final_release_version_and_assets_are_consistent() -> None:
    assert __version__ == "1.0.0"
    assert (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.0.0"

    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    workflow = (PROJECT_ROOT / ".github/workflows/docker.yml").read_text(
        encoding="utf-8"
    )

    assert "ARG APP_VERSION=1.0.0" in dockerfile
    assert "image: satplan:1.0.0" in compose
    assert "APP_VERSION=1.0.0" in workflow


def test_final_release_contains_no_root_hotfix_or_generated_report() -> None:
    forbidden = (
        "HOTFIX_README.txt",
        "RECOVERY_README.txt",
        "README_STAGE17_WINDOWS.txt",
        "run_stage17_checks.ps1",
        "report.docx",
    )

    assert all(not (PROJECT_ROOT / relative).exists() for relative in forbidden)


def test_release_notes_define_validation_and_tagging() -> None:
    notes = (PROJECT_ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "scripts/verify_release.ps1").read_text(
        encoding="utf-8"
    )

    assert "verify_release.ps1 -Docker -NoCache" in notes
    assert "git tag -a v1.0.0" in notes
    assert "release-check --algorithm BOTH" in script
    assert "FINAL RELEASE 1.0.0: READY" in script
