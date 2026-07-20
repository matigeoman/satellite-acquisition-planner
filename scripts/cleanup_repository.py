from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

try:
    from _bootstrap import PROJECT_ROOT
except ModuleNotFoundError:  # import during package-based tests
    from scripts._bootstrap import PROJECT_ROOT


LEGACY_PATHS = (
    "app/ui/components/cesium_globe.py",
    "app/visualization/czml.py",
    "app/ui/assets/earth_fallback.jpg",
    "docs/cesium_3d_globe.md",
    "tests/test_cesium_scene.py",
)

TRANSIENT_EXACT = (
    "HOTFIX_README.txt",
    "RECOVERY_README.txt",
    "README_STAGE17_WINDOWS.txt",
    "run_stage17_checks.ps1",
    "report.docx",
)


TRANSIENT_PATTERNS = (
    "*_NOTES.txt",
    "satplan-*.zip",
    "*.bak-stage*",
)


def discover_cleanup_targets(root: Path) -> tuple[Path, ...]:
    targets: set[Path] = set()
    for relative in LEGACY_PATHS:
        path = root / relative
        if path.exists():
            targets.add(path)
    for relative in TRANSIENT_EXACT:
        path = root / relative
        if path.is_file():
            targets.add(path)
    for pattern in TRANSIENT_PATTERNS:
        for path in root.rglob(pattern):
            if not path.is_file():
                continue
            if ".git" in path.relative_to(root).parts:
                continue
            targets.add(path)
    return tuple(sorted(targets))


def remove_targets(paths: Iterable[Path]) -> tuple[Path, ...]:
    removed: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        path.unlink()
        removed.append(path)
    return tuple(removed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Usuwa historyczny renderer Cesium, hotfixy i tymczasowe artefakty etapów."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tylko wyświetla pliki przeznaczone do usunięcia.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.project_root.resolve()
    targets = discover_cleanup_targets(root)
    if not targets:
        print("Repozytorium jest już uporządkowane.")
        return 0

    for path in targets:
        print(path.relative_to(root))
    if args.dry_run:
        print(f"Do usunięcia: {len(targets)}")
        return 0

    removed = remove_targets(targets)
    print(f"Usunięto: {len(removed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
