from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_globe_page_is_registered_in_navigation() -> None:
    navigation = (PROJECT_ROOT / "app/ui/navigation.py").read_text()
    streamlit_app = (PROJECT_ROOT / "streamlit_app.py").read_text()
    pages = (PROJECT_ROOT / "app/ui/pages/__init__.py").read_text()

    assert "GLOBE" in navigation
    assert "render_globe_page" in streamlit_app
    assert "render_globe_page" in pages


def test_globe_page_uses_shared_public_state() -> None:
    source = (PROJECT_ROOT / "app/ui/pages/globe.py").read_text()

    assert "public_access_result" in source
    assert "public_planning_result" in source
    assert "custom_observation_requests" in source
    assert "build_cesium_scene" in source
