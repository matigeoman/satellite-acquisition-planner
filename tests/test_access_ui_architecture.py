from pathlib import Path


def test_access_page_is_registered() -> None:
    navigation = Path("app/ui/navigation.py").read_text(encoding="utf-8")
    application = Path("streamlit_app.py").read_text(encoding="utf-8")
    pages = Path("app/ui/pages/__init__.py").read_text(encoding="utf-8")

    assert 'ACCESS = "Okna dostępu i pogoda"' in navigation
    assert "ApplicationPage.ACCESS" in application
    assert "render_access_page" in pages


def test_leaflet_toolbar_uses_independent_icons() -> None:
    editor = Path("app/ui/components/aoi_editor.py").read_text(encoding="utf-8")

    assert "background-image: none" in editor
    assert ".leaflet-draw-draw-marker::before" in editor
    assert ".leaflet-draw-draw-polygon::before" in editor
    assert ".leaflet-draw-draw-rectangle::before" in editor


def test_orbit_map_uses_full_width_maplibre_view() -> None:
    orbit_view = Path("app/ui/orbit_view.py").read_text(encoding="utf-8")

    assert "go.Scattermap" in orbit_view
    assert '"style": "carto-darkmatter"' in orbit_view
    assert "visible_slot_ids" in orbit_view
