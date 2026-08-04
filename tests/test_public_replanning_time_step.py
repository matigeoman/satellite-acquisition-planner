from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_replanning_time_input_uses_minute_step() -> None:
    page = (
        PROJECT_ROOT
        / "app"
        / "ui"
        / "pages"
        / "public_replanning.py"
    )
    source = page.read_text(encoding="utf-8")

    assert "step=timedelta(minutes=1)," in source
    assert "step=timedelta(minutes=5)," not in source
