from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_reports_page_is_registered() -> None:
    navigation = (PROJECT_ROOT / "app" / "ui" / "navigation.py").read_text(
        encoding="utf-8"
    )
    streamlit_app = (PROJECT_ROOT / "streamlit_app.py").read_text(
        encoding="utf-8"
    )
    page = (PROJECT_ROOT / "app" / "ui" / "pages" / "reports.py").read_text(
        encoding="utf-8"
    )

    assert 'REPORTS = "Raporty i wyniki"' in navigation
    assert "render_reports_page" in streamlit_app
    assert "Zbuduj pakiet raportowy" in page
    assert "Pobierz kompletny pakiet raportowy ZIP" in page


def test_report_dependencies_are_declared() -> None:
    requirements = (PROJECT_ROOT / "requirements-ui.txt").read_text(
        encoding="utf-8"
    )
    assert "python-docx" in requirements
    assert "XlsxWriter" in requirements
