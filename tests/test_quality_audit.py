from __future__ import annotations

import json
from pathlib import Path

from app.cli import build_parser, main
from app.config.paths import ProjectPaths
from app.quality import AuditStatus, run_project_audit
from app.version import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_version_is_loaded_from_repository_file() -> None:
    expected = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()

    assert __version__ == expected
    assert __version__ == "1.0.0-rc3"


def test_audit_parser_is_registered() -> None:
    args = build_parser().parse_args(["audit"])

    assert args.command == "audit"
    assert args.strict is False
    assert args.json_output is None


def test_project_audit_has_no_failures() -> None:
    report = run_project_audit(ProjectPaths(PROJECT_ROOT))
    statuses = {check.name: check.status for check in report.checks}

    assert report.is_success
    assert not report.failures
    assert statuses["application-version"] is AuditStatus.PASS
    assert statuses["required-paths"] is AuditStatus.PASS
    assert statuses["utf8-and-mojibake"] is AuditStatus.PASS
    assert statuses["windows-powershell-encoding"] is AuditStatus.PASS
    assert statuses["scenario-integrity"] is AuditStatus.PASS
    assert statuses["docker-assets"] is AuditStatus.PASS
    assert statuses["repository-cleanliness"] is AuditStatus.PASS


def test_cli_audit_writes_json_report(tmp_path: Path) -> None:
    output = tmp_path / "audit.json"

    result = main(
        ["audit", "--json", str(output)],
        paths=ProjectPaths(PROJECT_ROOT),
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["success"] is True
    assert payload["application_version"] == __version__
    assert payload["failure_count"] == 0
