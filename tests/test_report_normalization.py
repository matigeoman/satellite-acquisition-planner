from datetime import datetime, timezone

from app.reporting.models import ScientificReportSnapshot
from app.reporting.normalization import (
    normalize_report_snapshot,
    polish_count,
)


def _snapshot(*, results: str, methodology: str) -> ScientificReportSnapshot:
    return ScientificReportSnapshot(
        generated_at_utc=datetime(2026, 8, 5, tzinfo=timezone.utc),
        title="Raport testowy",
        author="",
        institution="WAT",
        description="",
        include_methodology=True,
        include_limitations=True,
        include_stk_validation=False,
        include_benchmarks=False,
        project_name="Test",
        project_id="TEST",
        application_version="1.4.0",
        overview_metrics=(),
        satellite_rows=(),
        request_rows=(),
        access_rows=(),
        opportunity_rows=(),
        schedule_rows=(),
        request_diagnostic_rows=(),
        satellite_kpi_rows=(),
        benchmark_rows=(),
        benchmark_summary_rows=(),
        schedule_history_summary_rows=(),
        schedule_history_rows=(),
        stk_access_rows=(),
        stk_aer_rows=(),
        narrative={
            "methodology": methodology,
            "results": results,
        },
        limitations=(),
        warnings=(),
    )


def test_polish_count_uses_correct_acquisition_forms() -> None:
    forms = {
        1: "1 akwizycję",
        2: "2 akwizycje",
        3: "3 akwizycje",
        4: "4 akwizycje",
        5: "5 akwizycji",
        12: "12 akwizycji",
        14: "14 akwizycji",
        22: "22 akwizycje",
        25: "25 akwizycji",
    }

    for count, expected in forms.items():
        assert polish_count(
            count,
            singular="akwizycję",
            paucal="akwizycje",
            plural="akwizycji",
        ) == expected


def test_snapshot_normalization_fixes_language_and_false_downlink_claim() -> None:
    snapshot = _snapshot(
        results="Solver wybrał 3 akwizycji.",
        methodology=(
            "Plan utworzono z uwzględnieniem zasobów, downlinku "
            "i przeorientowań."
        ),
    )

    normalized = normalize_report_snapshot(snapshot)

    assert normalized.narrative["results"] == "Solver wybrał 3 akwizycje."
    assert "downlinku" not in normalized.narrative["methodology"]
    assert (
        "skonfigurowanych ograniczeń planistycznych"
        in normalized.narrative["methodology"]
    )


def test_normalization_does_not_modify_source_snapshot() -> None:
    snapshot = _snapshot(
        results="Solver wybrał 5 akwizycji.",
        methodology="Metodyka bez deklaracji downlinku.",
    )

    normalized = normalize_report_snapshot(snapshot)

    assert normalized is not snapshot
    assert snapshot.narrative["results"] == "Solver wybrał 5 akwizycji."
    assert normalized.narrative["results"] == "Solver wybrał 5 akwizycji."
