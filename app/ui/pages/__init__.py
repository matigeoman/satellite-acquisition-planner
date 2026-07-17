"""Ekrany aplikacji Streamlit podzielone według przypadków użycia."""

from app.ui.pages.access import render_access_page
from app.ui.pages.benchmark import render_benchmark_page
from app.ui.pages.disruption import render_disruption_page
from app.ui.pages.experiments import render_experiments_page
from app.ui.pages.globe import render_globe_page
from app.ui.pages.planning import render_planning_page
from app.ui.pages.public_planning import render_public_planning_page
from app.ui.pages.public_replanning import render_public_replanning_page
from app.ui.pages.projects import render_projects_page
from app.ui.pages.reports import render_reports_page
from app.ui.pages.orbits import render_orbits_page
from app.ui.pages.replanning import render_replanning_page
from app.ui.pages.targets import render_targets_page
from app.ui.pages.stk_validation import render_stk_validation_page

__all__ = [
    "render_access_page",
    "render_benchmark_page",
    "render_disruption_page",
    "render_experiments_page",
    "render_globe_page",
    "render_planning_page",
    "render_public_planning_page",
    "render_public_replanning_page",
    "render_projects_page",
    "render_reports_page",
    "render_orbits_page",
    "render_replanning_page",
    "render_targets_page",
    "render_stk_validation_page",
]
