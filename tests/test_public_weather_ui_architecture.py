from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_planning_page_is_registered() -> None:
    navigation = (PROJECT_ROOT / "app/ui/navigation.py").read_text()
    streamlit_app = (PROJECT_ROOT / "streamlit_app.py").read_text()
    assert "PUBLIC_PLANNING" in navigation
    assert "render_public_planning_page" in streamlit_app


def test_access_page_builds_weather_opportunities() -> None:
    source = (PROJECT_ROOT / "app/ui/pages/access.py").read_text()
    assert "get_cloud_assessment_service" in source
    assert "build_public_opportunities" in source
    assert "OpenMeteoClientError" in source
