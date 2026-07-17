from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_ui_exposes_operational_constraints() -> None:
    targets = (PROJECT_ROOT / "app" / "ui" / "pages" / "targets.py").read_text(
        encoding="utf-8"
    )
    planning = (
        PROJECT_ROOT / "app" / "ui" / "pages" / "public_planning.py"
    ).read_text(encoding="utf-8")

    assert "Maksymalny odstęp SAR–EO" in targets
    assert "Dynamiczne przeorientowanie Pléiades Neo i ICEYE" in planning
    assert "Zmiana LEFT/RIGHT" in planning
    assert "Maksymalna liczba akwizycji ICEYE" in planning
