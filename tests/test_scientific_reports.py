from __future__ import annotations

import io
import json
import zipfile

from app.reporting import ScientificReportConfig, ScientificReportService


def test_report_package_contains_all_primary_formats() -> None:
    service = ScientificReportService()
    result = service.build(
        {},
        config=ScientificReportConfig(
            title="Raport testowy SatPlan",
            author="Autor testowy",
        ),
    )

    assert result.archive_bytes.startswith(b"PK")
    assert result.docx_bytes.startswith(b"PK")
    assert result.xlsx_bytes.startswith(b"PK")
    assert b"Raport testowy SatPlan" in result.html_bytes
    assert result.suggested_filename.endswith("-raport.zip")
    assert result.warnings

    with zipfile.ZipFile(io.BytesIO(result.archive_bytes)) as archive:
        names = set(archive.namelist())
        assert {
            "report.html",
            "report.docx",
            "results.xlsx",
            "report.json",
            "README.txt",
            "tables/overview_metrics.csv",
        }.issubset(names)
        payload = json.loads(archive.read("report.json").decode("utf-8"))
        assert payload["title"] == "Raport testowy SatPlan"
        assert payload["author"] == "Autor testowy"


def test_office_documents_are_valid_ooxml_archives() -> None:
    result = ScientificReportService().build(
        {},
        config=ScientificReportConfig(title="Walidacja OOXML"),
    )

    with zipfile.ZipFile(io.BytesIO(result.docx_bytes)) as document:
        assert "word/document.xml" in document.namelist()
        assert "[Content_Types].xml" in document.namelist()

    with zipfile.ZipFile(io.BytesIO(result.xlsx_bytes)) as workbook:
        assert "xl/workbook.xml" in workbook.namelist()
        assert "[Content_Types].xml" in workbook.namelist()


def test_raw_tables_can_be_disabled() -> None:
    result = ScientificReportService().build(
        {},
        config=ScientificReportConfig(
            title="Raport bez CSV",
            include_raw_tables=False,
        ),
    )

    assert not any(path.startswith("tables/") for path in result.included_files)
    assert "report.html" in result.included_files
    assert "results.xlsx" in result.included_files


def test_docx_tables_repeat_headers_and_keep_rows_together() -> None:
    result = ScientificReportService().build(
        {},
        config=ScientificReportConfig(title="Walidacja tabel DOCX"),
    )

    with zipfile.ZipFile(io.BytesIO(result.docx_bytes)) as document:
        xml = document.read("word/document.xml")

    assert b"<w:tblHeader" in xml
    assert b"<w:cantSplit" in xml


def test_history_has_summary_for_documents_and_full_hidden_xlsx_sheet() -> None:
    marker = "RAW-HISTORY-DETAIL-" + "x" * 512
    state = {
        "project_schedule_history": [
            {
                "history_id": "HISTORY-TEST-001",
                "event_type": "WEATHER_REPLANNING",
                "recorded_at_utc": "2026-08-05T07:00:00+00:00",
                "schedule_signature": "SCHEDULE-TEST-002:2026-08-05T07:00:00+00:00",
                "schedule": {
                    "schedule_id": "SCHEDULE-TEST-002",
                    "name": marker,
                },
                "algorithm": "HYBRID",
                "options": {"technical_payload": marker},
                "solver_status": "OPTIMAL",
                "wall_clock_runtime_s": 1.25,
                "objective_value": 123.0,
                "fully_satisfied_requests": 1,
                "total_acquisitions": 1,
                "previous_schedule_id": "SCHEDULE-TEST-001",
                "added_opportunity_ids": ["OPP-002"],
                "removed_opportunity_ids": ["OPP-001"],
            }
        ]
    }
    result = ScientificReportService().build(
        state,
        config=ScientificReportConfig(title="Historia raportu"),
    )
    payload = json.loads(result.json_bytes.decode("utf-8"))

    summary = payload["schedule_history_summary_rows"][0]
    assert summary["schedule_id"] == "SCHEDULE-TEST-002"
    assert summary["previous_schedule_id"] == "SCHEDULE-TEST-001"
    assert summary["added_opportunities"] == 1
    assert marker in payload["schedule_history_rows"][0]["schedule"]
    assert marker.encode("utf-8") not in result.html_bytes

    with zipfile.ZipFile(io.BytesIO(result.xlsx_bytes)) as workbook:
        workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")

    assert 'name="Historia_planow"' in workbook_xml
    assert 'name="Historia_szczegoly"' in workbook_xml
    assert 'name="Historia_szczegoly" sheetId=' in workbook_xml
    details_fragment = workbook_xml.split('name="Historia_szczegoly"', 1)[1]
    assert 'state="hidden"' in details_fragment.split("/>", 1)[0]


def test_benchmark_heading_lists_hybrid_when_present() -> None:
    from types import SimpleNamespace

    from app.reporting.collector import _benchmark_heading

    benchmark = SimpleNamespace(
        run_records=(
            SimpleNamespace(algorithm="GREEDY"),
            SimpleNamespace(algorithm="CP_SAT"),
            SimpleNamespace(algorithm="HYBRID"),
        )
    )

    assert _benchmark_heading(benchmark) == "Benchmark Greedy, CP-SAT i Hybrid"


def test_current_planning_scenario_is_authoritative_for_report_requests(
    monkeypatch,
) -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    import app.reporting.collector as collector

    class FakeRequest:
        def __init__(self, request_id: str) -> None:
            now = datetime(2026, 8, 5, tzinfo=timezone.utc)
            self.request_id = request_id
            self.name = request_id
            self.request_mode = "SINGLE"
            self.requested_sensor_types = ("SAR",)
            self.priority = 50
            self.is_mandatory = False
            self.earliest_start_utc = now
            self.latest_end_utc = now
            self.max_resolution_m = 1.0
            self.minimum_coverage_ratio = 0.8
            self.max_cloud_cover = None
            self.max_incidence_angle_deg = 45.0
            self.max_off_nadir_deg = 35.0
            self.max_dual_separation_hours = 24.0
            self.status = "ACTIVE"

    class FakePlanningResult:
        pass

    monkeypatch.setattr(collector, "ObservationRequest", FakeRequest)
    monkeypatch.setattr(collector, "PlanningResult", FakePlanningResult)

    session_requests = [FakeRequest("REQ-OLD-001"), FakeRequest("REQ-OLD-002")]
    current_request = FakeRequest("REQ-CURRENT-001")
    analysis = SimpleNamespace(
        total_active_requests=1,
        total_acquisitions=1,
        fully_satisfied_requests=1,
        satisfaction_ratio=1.0,
        objective_value=100.0,
        request_diagnostics=(),
        satellite_kpis=(),
    )
    planning = FakePlanningResult()
    planning.scenario = SimpleNamespace(
        scenario_id="PUBLIC",
        request_set=SimpleNamespace(requests=(current_request,)),
        opportunity_set=SimpleNamespace(opportunities=()),
        catalog=SimpleNamespace(satellites=()),
    )
    planning.schedule = SimpleNamespace(active_entries=())
    planning.analysis = analysis
    planning.algorithm = SimpleNamespace(value="HYBRID")
    planning.objective_value = 100.0
    planning.fully_satisfied_requests = 1
    planning.total_acquisitions = 1

    snapshot = collector.collect_report_snapshot(
        {
            collector.CUSTOM_REQUESTS_STATE_KEY: session_requests,
            collector.PLANNING_RESULT_STATE_KEY: planning,
        },
        config=ScientificReportConfig(
            title="Spójność scenariusza",
            include_benchmarks=False,
            include_stk_validation=False,
        ),
    )

    assert [row["request_id"] for row in snapshot.request_rows] == [
        "REQ-CURRENT-001"
    ]
    metric_map = {
        row["metric"]: row["value"] for row in snapshot.overview_metrics
    }
    assert metric_map["Zlecenia"] == 1
    assert metric_map["Scenariusz harmonogramu"] == "PUBLIC"
    assert any("mieszany stan sesji" in item for item in snapshot.warnings)


def test_report_warns_when_replanning_reuses_schedule_id() -> None:
    state = {
        "project_schedule_history": [
            {
                "event_type": "WEATHER_REPLANNING",
                "schedule": {"schedule_id": "SCHEDULE-PUBLIC-REPLAN-001"},
                "previous_schedule_id": "SCHEDULE-PUBLIC-REPLAN-001",
            }
        ]
    }

    result = ScientificReportService().build(
        state,
        config=ScientificReportConfig(
            title="Powtórzony identyfikator harmonogramu",
            include_benchmarks=False,
            include_stk_validation=False,
        ),
    )

    assert any(
        "takim samym identyfikatorem" in warning
        for warning in result.warnings
    )
