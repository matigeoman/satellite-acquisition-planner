from __future__ import annotations

from datetime import date, time, timezone

import pytest

from app.ui.common import algorithm_display_name, combine_utc
from app.ui.paths import PROJECT_ROOT, reference_schedule_path


def test_streamlit_entrypoint_is_small_and_compilable() -> None:
    entrypoint = PROJECT_ROOT / "streamlit_app.py"
    source = entrypoint.read_text(encoding="utf-8")

    compile(source, str(entrypoint), "exec")
    assert len(source.splitlines()) < 100


def test_application_stylesheet_is_external_and_nonempty() -> None:
    stylesheet_path = PROJECT_ROOT / "app" / "ui" / "assets" / "application.css"
    stylesheet = stylesheet_path.read_text(encoding="utf-8")

    assert "stAppViewContainer" in stylesheet
    assert "<style>" not in stylesheet
    assert len(stylesheet) > 1000


def test_all_page_modules_exist_and_compile() -> None:
    pages_directory = PROJECT_ROOT / "app" / "ui" / "pages"
    expected = {
        "planning.py",
        "replanning.py",
        "disruption.py",
        "experiments.py",
    }

    available = {path.name for path in pages_directory.glob("*.py")}
    assert expected <= available

    for filename in expected:
        path = pages_directory / filename
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_navigation_is_grouped_and_contains_reference_modules() -> None:
    navigation_source = (PROJECT_ROOT / "app" / "ui" / "navigation.py").read_text(
        encoding="utf-8"
    )

    for label in [
        "Przepływ operacyjny",
        "Analiza i walidacja",
        "Projekt i wyniki",
        "Planowanie scenariuszy referencyjnych",
        "Eksperymenty porównawcze",
    ]:
        assert label in navigation_source


def test_combine_utc_creates_timezone_aware_datetime() -> None:
    value = combine_utc(date(2026, 7, 15), time(6, 30))

    assert value.isoformat() == "2026-07-15T06:30:00+00:00"
    assert value.tzinfo == timezone.utc


@pytest.mark.parametrize(
    ("raw", "display"),
    [
        ("GREEDY", "Greedy"),
        ("CP_SAT", "CP-SAT"),
        ("CUSTOM_MODE", "CUSTOM-MODE"),
    ],
)
def test_algorithm_display_name(raw: str, display: str) -> None:
    assert algorithm_display_name(raw) == display


def test_reference_schedule_path_is_stable() -> None:
    path = reference_schedule_path(
        scenario_id="EXAMPLE",
        algorithm_value="CP_SAT",
    )

    assert (
        path
        == PROJECT_ROOT / "data" / "reference_schedules" / "example" / "cp_sat.json"
    )


def test_reference_schedule_path_rejects_unknown_scenario() -> None:
    with pytest.raises(ValueError, match="Nieobsługiwany scenariusz"):
        reference_schedule_path(
            scenario_id="UNKNOWN",
            algorithm_value="GREEDY",
        )


def test_planning_page_contains_integrated_downlink_view() -> None:
    path = PROJECT_ROOT / "app" / "ui" / "pages" / "planning.py"
    source = path.read_text(encoding="utf-8")

    assert "Pamięć i downlink" in source
    assert "Zintegrowane planowanie downlinku" in source
    assert "Pobierz downlink CSV" in source
    assert "build_memory_timeline_dataframe" in source
