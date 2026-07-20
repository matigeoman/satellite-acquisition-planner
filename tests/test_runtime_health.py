from __future__ import annotations

import json
from pathlib import Path

from app.cli import build_parser, main
from app.config.paths import ProjectPaths
from app.quality import RuntimeHealthCheck, run_runtime_healthcheck


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_health_without_http_is_healthy() -> None:
    report = run_runtime_healthcheck(
        ProjectPaths(PROJECT_ROOT),
        streamlit_url=None,
    )
    names = {check.name for check in report.checks}

    assert report.healthy
    assert names == {
        "python",
        "cp-sat",
        "example-scenario",
        "writable-storage",
    }


def test_runtime_health_includes_injected_http_check() -> None:
    def fake_http(url: str, timeout_s: float) -> RuntimeHealthCheck:
        assert url == "http://example.test/health"
        assert timeout_s == 1.5
        return RuntimeHealthCheck("streamlit-http", True, "ok")

    report = run_runtime_healthcheck(
        ProjectPaths(PROJECT_ROOT),
        streamlit_url="http://example.test/health",
        timeout_s=1.5,
        http_checker=fake_http,
    )

    assert report.healthy
    assert report.checks[-1].name == "streamlit-http"


def test_health_cli_is_registered_and_writes_json(tmp_path: Path) -> None:
    args = build_parser().parse_args(["health", "--skip-http", "--quiet"])
    assert args.command == "health"
    assert args.skip_http is True
    assert args.quiet is True

    output = tmp_path / "runtime-health.json"
    exit_code = main(
        ["health", "--skip-http", "--quiet", "--json", str(output)],
        paths=ProjectPaths(PROJECT_ROOT),
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["healthy"] is True
    assert payload["application_version"]
