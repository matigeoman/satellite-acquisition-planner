"""Ekrany aplikacji Streamlit podzielone według przypadków użycia."""

from app.ui.pages.disruption import render_disruption_page
from app.ui.pages.experiments import render_experiments_page
from app.ui.pages.planning import render_planning_page
from app.ui.pages.replanning import render_replanning_page
from app.ui.pages.targets import render_targets_page

__all__ = [
    "render_disruption_page",
    "render_experiments_page",
    "render_planning_page",
    "render_replanning_page",
    "render_targets_page",
]
