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


def test_targets_page_exposes_clear_dual_sensor_variants() -> None:
    source = Path("app/ui/pages/targets.py").read_text(encoding="utf-8")

    assert "SAR + EO — oba wymagane" in source
    assert "SAR + EO — drugi sensor opcjonalny" in source
    assert "Maksymalna rozdzielczość SAR" in source
    assert "Maksymalna GSD EO" in source
