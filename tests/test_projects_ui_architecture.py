from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_projects_page_is_registered() -> None:
    navigation = (PROJECT_ROOT / "app" / "ui" / "navigation.py").read_text(
        encoding="utf-8"
    )
    streamlit_app = (PROJECT_ROOT / "streamlit_app.py").read_text(
        encoding="utf-8"
    )
    page = (
        PROJECT_ROOT / "app" / "ui" / "pages" / "projects.py"
    ).read_text(encoding="utf-8")

    assert "PROJECTS" in navigation
    assert "Projekty i scenariusze" in navigation
    assert "render_projects_page" in streamlit_app
    assert "Zbuduj archiwum projektu" in page
    assert "Wczytaj projekt i przywróć sesję" in page


def test_planning_pages_record_schedule_history() -> None:
    public_planning = (
        PROJECT_ROOT / "app" / "ui" / "pages" / "public_planning.py"
    ).read_text(encoding="utf-8")
    public_replanning = (
        PROJECT_ROOT / "app" / "ui" / "pages" / "public_replanning.py"
    ).read_text(encoding="utf-8")

    assert "record_schedule_history" in public_planning
    assert "INITIAL_PLANNING" in public_planning
    assert "record_schedule_history" in public_replanning
    assert "WEATHER_REPLANNING" in public_replanning
