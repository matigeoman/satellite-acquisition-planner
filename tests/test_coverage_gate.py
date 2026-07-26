from __future__ import annotations

import json
from pathlib import Path

from scripts.check_coverage import _critical_coverage


def test_critical_coverage_accepts_windows_or_absolute_paths() -> None:
    payload = {
        "files": {
            "C:/repo/app/integrations/orbits/selection.py": {
                "summary": {"covered_lines": 8, "num_statements": 10}
            },
            "app/services/orbit_service.py": {
                "summary": {"covered_lines": 7, "num_statements": 10}
            },
            "app/ui/pages/orbits.py": {
                "summary": {"covered_lines": 1, "num_statements": 100}
            },
        }
    }

    percent, covered, statements = _critical_coverage(
        payload,
        ("app/integrations/orbits/", "app/services/orbit_service.py"),
    )

    assert percent == 75.0
    assert covered == 15
    assert statements == 20


def test_coverage_report_fixture_is_valid_json(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(
        json.dumps(
            {
                "totals": {"percent_covered": 80.0},
                "files": {
                    "app/integrations/orbits/models.py": {
                        "summary": {"covered_lines": 80, "num_statements": 100}
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    payload = json.loads(report.read_text(encoding="utf-8"))
    percent, covered, statements = _critical_coverage(
        payload,
        ("app/integrations/orbits/",),
    )

    assert percent == 80.0
    assert (covered, statements) == (80, 100)
