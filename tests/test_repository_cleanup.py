from __future__ import annotations

from pathlib import Path

from scripts.cleanup_repository import (
    LEGACY_PATHS,
    discover_cleanup_targets,
    remove_targets,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_repository_no_longer_contains_legacy_files() -> None:
    assert all(not (PROJECT_ROOT / relative).exists() for relative in LEGACY_PATHS)


def test_cleanup_discovers_legacy_root_artifacts_and_backups(tmp_path: Path) -> None:
    legacy = tmp_path / LEGACY_PATHS[0]
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy", encoding="utf-8")

    note = tmp_path / "FINAL_NOTES.txt"
    note.write_text("temporary", encoding="utf-8")
    patch = tmp_path / "update.patch"
    patch.write_text("temporary patch", encoding="utf-8")
    report = tmp_path / "report.docx"
    report.write_bytes(b"temporary report")
    backup = tmp_path / "app" / "ui" / "page.py.bak-old"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("backup", encoding="utf-8")

    targets = discover_cleanup_targets(tmp_path)

    expected = {legacy, note, patch, report, backup}
    assert set(targets) == expected
    assert set(remove_targets(targets)) == expected
    assert not any(path.exists() for path in targets)
