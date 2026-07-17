from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_replanning_page_is_registered() -> None:
    navigation = (PROJECT_ROOT / "app" / "ui" / "navigation.py").read_text(encoding="utf-8")
    streamlit_app = (PROJECT_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    page = (
        PROJECT_ROOT / "app" / "ui" / "pages" / "public_replanning.py"
    ).read_text(encoding="utf-8")

    assert "PUBLIC_REPLANNING" in navigation
    assert "render_public_replanning_page" in streamlit_app
    assert "Odśwież pogodę i przeplanuj" in page
    assert "Okno zamrożone" in page


def test_globe_uses_custom_category_legend() -> None:
    page = (PROJECT_ROOT / "app" / "ui" / "pages" / "globe.py").read_text(encoding="utf-8")
    plotly_globe = (
        PROJECT_ROOT / "app" / "visualization" / "plotly_globe.py"
    ).read_text(encoding="utf-8")

    assert "_render_category_legend" in page
    assert "ICEYE SAR" in page
    assert "Pléiades Neo EO" in page
    assert "showlegend=False" in plotly_globe
