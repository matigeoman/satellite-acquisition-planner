from pathlib import Path


def test_orbit_page_is_registered() -> None:
    navigation = Path("app/ui/navigation.py").read_text(encoding="utf-8")
    application = Path("streamlit_app.py").read_text(encoding="utf-8")
    pages = Path("app/ui/pages/__init__.py").read_text(encoding="utf-8")

    assert 'ORBITS = "Orbity i dane OMM"' in navigation
    assert "ApplicationPage.ORBITS" in application
    assert "render_orbits_page" in pages


def test_sgp4_dependency_is_declared() -> None:
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "sgp4" in requirements


def test_responsive_interface_scale_and_map_controls_are_present() -> None:
    stylesheet = Path("app/ui/assets/application.css").read_text(encoding="utf-8")
    aoi_editor = Path("app/ui/components/aoi_editor.py").read_text(encoding="utf-8")

    assert "font-size: 18px" in stylesheet
    assert "min-width: 340px" in stylesheet
    assert '[data-testid="stIconMaterial"]' in stylesheet
    assert "height=700" in aoi_editor
    assert ".leaflet-draw-toolbar a" in aoi_editor
