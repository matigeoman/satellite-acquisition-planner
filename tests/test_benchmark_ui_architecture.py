from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_page_is_registered() -> None:
    navigation = (PROJECT_ROOT / "app" / "ui" / "navigation.py").read_text(
        encoding="utf-8"
    )
    streamlit_app = (PROJECT_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    page = (PROJECT_ROOT / "app" / "ui" / "pages" / "benchmark.py").read_text(
        encoding="utf-8"
    )

    assert "BENCHMARKS" in navigation
    assert "Benchmarki" in navigation
    assert "render_benchmark_page" in streamlit_app
    assert "Uruchom benchmark Greedy vs CP-SAT" in page
    assert "5000 okazji" in page


def test_benchmark_export_contains_expected_artifacts() -> None:
    view = (PROJECT_ROOT / "app" / "ui" / "benchmark_view.py").read_text(
        encoding="utf-8"
    )

    for filename in [
        "benchmark_runs.csv",
        "benchmark_pairs.csv",
        "benchmark_summary.csv",
        "benchmark_results.json",
        "benchmark_charts.html",
    ]:
        assert filename in view
