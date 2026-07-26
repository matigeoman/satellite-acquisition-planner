from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_system_overview_is_registered_and_uses_catalogs() -> None:
    entrypoint = (PROJECT_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    navigation = (PROJECT_ROOT / "app/ui/navigation.py").read_text(encoding="utf-8")
    page = (
        PROJECT_ROOT / "app/ui/pages/system_overview.py"
    ).read_text(encoding="utf-8")

    assert "ApplicationPage.SYSTEM_OVERVIEW" in entrypoint
    assert 'SYSTEM_OVERVIEW = "System i satelity"' in navigation
    assert "ICEYE_PUBLIC_PROFILE" in page
    assert "PLEIADES_NEO_PUBLIC_PROFILE" in page
    assert "render_page_header(" in page
    assert "render_constellation_phasing_visual" in page


def test_system_diagrams_and_documentation_exist() -> None:
    diagram_root = PROJECT_ROOT / "docs/assets/diagrams"
    required = (
        "constellation_phasing.svg",
        "acquisition_geometry.svg",
        "orbit_data_layers.svg",
        "planning_pipeline.svg",
        "pass_geometry.svg",
    )

    assert all((diagram_root / filename).is_file() for filename in required)
    documentation = (PROJECT_ROOT / "docs/satellite_system.md").read_text(
        encoding="utf-8"
    )
    assert "Profil nominalny a aktualne OMM" in documentation
    assert "Konstelacja demonstracyjna i fazowanie" in documentation
    assert "prefers-reduced-motion" in documentation

def test_sensor_table_is_arrow_serializable() -> None:
    import pyarrow as pa

    from app.ui.pages.system_overview import _sensor_table

    table = _sensor_table()
    pa.Table.from_pandas(table, preserve_index=False)
    assert table["Min. elewacja Słońca [°]"].map(type).eq(str).all()

