from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_live_tracking_page_is_registered() -> None:
    navigation = (PROJECT_ROOT / "app/ui/navigation.py").read_text(encoding="utf-8")
    streamlit_app = (PROJECT_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    pages = (PROJECT_ROOT / "app/ui/pages/__init__.py").read_text(encoding="utf-8")

    assert "LIVE_TRACKING" in navigation
    assert "Śledzenie i przeloty" in navigation
    assert "render_live_tracking_page" in streamlit_app
    assert "render_live_tracking_page" in pages


def test_live_tracking_page_contains_live_fragment_and_planner_context() -> None:
    source = (PROJECT_ROOT / "app/ui/pages/live_tracking.py").read_text(
        encoding="utf-8"
    )

    assert '@st.fragment(run_every="2s")' in source
    assert "AOS UTC" in source
    assert "MAX UTC" in source
    assert "LOS UTC" in source
    assert "ACCESS_RESULT_STATE_KEY" in source
    assert "PLANNING_RESULT_STATE_KEY" in source
    assert "build_sky_map_figure" in source
    assert "build_live_ground_map_figure" in source


def test_live_tracking_time_input_uses_supported_step() -> None:
    source = (PROJECT_ROOT / "app/ui/pages/live_tracking.py").read_text(
        encoding="utf-8"
    )

    assert "step=timedelta(minutes=1)" in source
    assert (
        'step=timedelta(seconds=30),\n                key="live_tracking_time"'
        not in source
    )


def test_live_tracking_hardening_controls_are_present() -> None:
    source = (PROJECT_ROOT / "app/ui/pages/live_tracking.py").read_text(
        encoding="utf-8"
    )

    assert "force_refresh=True" in source
    assert "Źródło i jakość danych orbitalnych" in source
    assert "Tylko widoczne optycznie" in source
    assert "Tylko powiązane z harmonogramem" in source
    assert "Ślad naziemny" in source
    assert "Wynik [0–100]" in source
    assert '"Okna dostępu"' in source
