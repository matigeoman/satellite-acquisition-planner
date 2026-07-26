from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from _bootstrap import PROJECT_ROOT
except ModuleNotFoundError:
    from scripts._bootstrap import PROJECT_ROOT


DEFAULT_CRITICAL_PREFIXES = (
    "app/integrations/orbits/",
    "app/services/orbit_service.py",
)


def _percentage(covered: float, statements: float) -> float:
    if statements <= 0:
        return 100.0
    return covered / statements * 100.0


def _critical_coverage(
    payload: dict[str, Any],
    prefixes: tuple[str, ...],
) -> tuple[float, int, int]:
    covered = 0
    statements = 0

    for filename, details in payload.get("files", {}).items():
        normalized = filename.replace("\\", "/")

        if not any(
            normalized.startswith(prefix) or f"/{prefix}" in normalized
            for prefix in prefixes
        ):
            continue

        summary = details.get("summary", {})
        covered += int(summary.get("covered_lines", 0))
        statements += int(summary.get("num_statements", 0))

    return _percentage(covered, statements), covered, statements


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enforce SATPLAN coverage gates."
    )
    parser.add_argument(
        "report",
        type=Path,
        nargs="?",
        default=Path("coverage.json"),
    )
    parser.add_argument("--global-min", type=float, default=60.0)
    parser.add_argument("--critical-min", type=float, default=65.0)
    args = parser.parse_args()

    report_path = args.report
    if not report_path.is_absolute():
        report_path = PROJECT_ROOT / report_path

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    global_percent = float(payload["totals"]["percent_covered"])
    critical_percent, covered, statements = _critical_coverage(
        payload,
        DEFAULT_CRITICAL_PREFIXES,
    )

    print(
        f"Global coverage: {global_percent:.2f}% "
        f"(minimum {args.global_min:.2f}%)"
    )
    print(
        "Critical orbit coverage: "
        f"{critical_percent:.2f}% "
        f"({covered}/{statements}; "
        f"minimum {args.critical_min:.2f}%)"
    )

    failed = False

    if global_percent < args.global_min:
        print("ERROR: global coverage gate failed")
        failed = True

    if statements == 0:
        print("ERROR: coverage report contains no critical orbit files")
        failed = True
    elif critical_percent < args.critical_min:
        print("ERROR: critical orbit coverage gate failed")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())