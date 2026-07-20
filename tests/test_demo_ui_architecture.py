from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_demo_page_is_registered_in_navigation_and_streamlit() -> None:
    navigation = (PROJECT_ROOT / "app/ui/navigation.py").read_text(encoding="utf-8")
    streamlit_app = (PROJECT_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    page = (PROJECT_ROOT / "app/ui/pages/demo.py").read_text(encoding="utf-8")

    assert 'DEMO = "Start i demo"' in navigation
    assert "render_demo_page" in streamlit_app
    assert "Wczytaj scenariusz demonstracyjny Polski" in page
    assert "CelesTrak" in page
    assert "50 zleceń" in page
    assert "500 okazji" in page
    assert "48-godzinny" in page
    assert "okna dostępu" in page
    assert "Open-Meteo" in page
