from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = PROJECT_ROOT / "app" / "ui"
PAGE_ROOT = UI_ROOT / "pages"

_PAGE_MODULES = (
    "access.py",
    "benchmark.py",
    "demo.py",
    "disruption.py",
    "experiments.py",
    "globe.py",
    "live_tracking.py",
    "orbits.py",
    "planning.py",
    "projects.py",
    "public_planning.py",
    "public_replanning.py",
    "replanning.py",
    "reports.py",
    "stk_validation.py",
    "targets.py",
)


def test_every_primary_page_uses_shared_header() -> None:
    missing: list[str] = []

    for filename in _PAGE_MODULES:
        source = (PAGE_ROOT / filename).read_text(encoding="utf-8")
        if "render_page_header(" not in source:
            missing.append(filename)

    assert not missing, f"Brak wspólnego nagłówka: {', '.join(missing)}"


def test_visual_components_are_isolated_from_domain_logic() -> None:
    source = (UI_ROOT / "page_layout.py").read_text(encoding="utf-8")

    assert "from app.models" not in source
    assert "from app.planning" not in source
    assert "unsafe_allow_html=True" in source
    assert "escape(" in source


def test_plotly_theme_is_registered_by_entrypoint() -> None:
    entrypoint = (PROJECT_ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    theme = (UI_ROOT / "plotly_theme.py").read_text(encoding="utf-8")

    assert "register_plotly_theme()" in entrypoint
    assert 'pio.templates.default = f"plotly_dark+{_TEMPLATE_NAME}"' in theme
    assert '"#50a9ff"' in theme
    assert '"#ff636a"' in theme


def test_stylesheet_contains_responsive_visual_tokens() -> None:
    stylesheet = (UI_ROOT / "assets" / "application.css").read_text(
        encoding="utf-8"
    )

    for selector in (
        ".satplan-page-header",
        ".satplan-page-badge",
        ".satplan-sidebar-heading",
        "button:focus-visible",
        "@media (max-width: 760px)",
    ):
        assert selector in stylesheet

    assert "font-size: 18px" in stylesheet
    assert "min-width: 340px" in stylesheet


def test_sidebar_parameter_pages_use_compact_heading() -> None:
    for filename in (
        "benchmark.py",
        "disruption.py",
        "experiments.py",
        "planning.py",
        "replanning.py",
    ):
        source = (PAGE_ROOT / filename).read_text(encoding="utf-8")
        assert "render_sidebar_heading(" in source


def test_ui_architecture_documents_visual_system() -> None:
    documentation = (PROJECT_ROOT / "docs" / "ui_architecture.md").read_text(
        encoding="utf-8"
    )

    assert "## System wizualny" in documentation
    assert "app/ui/page_layout.py" in documentation
    assert "app/ui/plotly_theme.py" in documentation
