from __future__ import annotations

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"
_FALLBACK_VERSION = "0.0.0+unknown"


def read_application_version() -> str:
    """Return the repository version without importing packaging tooling."""

    try:
        value = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return _FALLBACK_VERSION
    return value or _FALLBACK_VERSION


__version__ = read_application_version()

__all__ = ["__version__", "read_application_version"]
