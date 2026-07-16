"""Wspólny bootstrap dla skryptów uruchamianych bez instalacji pakietu."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.paths import ProjectPaths  # noqa: E402


PROJECT_PATHS = ProjectPaths(PROJECT_ROOT)
PROJECT_PATHS.ensure_output_directories()

__all__ = ["PROJECT_PATHS", "PROJECT_ROOT"]
