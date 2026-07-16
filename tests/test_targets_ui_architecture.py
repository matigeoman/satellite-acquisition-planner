from pathlib import Path


def test_targets_page_is_registered_in_navigation() -> None:
    navigation = Path("app/ui/navigation.py").read_text(encoding="utf-8")
    streamlit_app = Path("streamlit_app.py").read_text(encoding="utf-8")

    assert 'TARGETS = "Cele i zlecenia"' in navigation
    assert "ApplicationPage.TARGETS" in streamlit_app
    assert "render_targets_page" in streamlit_app


def test_aoi_editor_dependency_is_declared() -> None:
    requirements = Path("requirements-ui.txt").read_text(encoding="utf-8")

    assert "folium" in requirements
    assert "streamlit-folium" in requirements
