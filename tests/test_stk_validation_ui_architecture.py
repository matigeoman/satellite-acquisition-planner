from pathlib import Path


def test_stk_validation_page_is_registered() -> None:
    navigation = Path("app/ui/navigation.py").read_text(encoding="utf-8")
    pages = Path("app/ui/pages/__init__.py").read_text(encoding="utf-8")
    entrypoint = Path("streamlit_app.py").read_text(encoding="utf-8")
    page = Path("app/ui/pages/stk_validation.py").read_text(encoding="utf-8")

    assert 'STK_VALIDATION = "Walidacja względem STK"' in navigation
    assert "render_stk_validation_page" in pages
    assert "ApplicationPage.STK_VALIDATION" in entrypoint
    assert "Pobierz paczkę walidacyjną STK" in page
    assert "parse_access" in page
    assert "parse_aer" in page
