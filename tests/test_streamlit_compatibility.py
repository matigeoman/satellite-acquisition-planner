from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_pages_use_current_width_api() -> None:
    pages = PROJECT_ROOT / "app" / "ui" / "pages"
    offenders = [
        path.relative_to(PROJECT_ROOT)
        for path in pages.rglob("*.py")
        if "use_container_width=" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_folium_keeps_its_own_width_parameter() -> None:
    source = (
        PROJECT_ROOT / "app" / "ui" / "components" / "aoi_editor.py"
    ).read_text(encoding="utf-8")

    assert "use_container_width=True" in source


def test_request_resolution_columns_do_not_mix_text_and_numbers() -> None:
    source = (
        PROJECT_ROOT / "app" / "ui" / "pages" / "targets.py"
    ).read_text(encoding="utf-8")

    assert '"SAR [m]": (' in source
    assert '"EO [m]": (' in source
    assert source.count("else None") >= 2
