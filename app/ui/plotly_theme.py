from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio


_TEMPLATE_NAME = "satplan"
_COLORWAY = (
    "#50a9ff",
    "#ff636a",
    "#34d399",
    "#f59e0b",
    "#a78bfa",
    "#22d3ee",
    "#f472b6",
    "#94a3b8",
)


def register_plotly_theme() -> None:
    """Rejestruje jeden motyw Plotly używany przez wszystkie wykresy aplikacji."""

    if _TEMPLATE_NAME not in pio.templates:
        pio.templates[_TEMPLATE_NAME] = go.layout.Template(
            layout=go.Layout(
                colorway=list(_COLORWAY),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(8,13,22,0.62)",
                font={"color": "#dce6f2", "family": "Inter, Segoe UI, sans-serif"},
                title={"x": 0.0, "xanchor": "left", "font": {"size": 18}},
                margin={"l": 56, "r": 28, "t": 58, "b": 52},
                hoverlabel={
                    "bgcolor": "#111b2e",
                    "bordercolor": "rgba(148,163,184,0.34)",
                    "font": {"color": "#f8fafc"},
                },
                legend={
                    "bgcolor": "rgba(8,13,22,0.70)",
                    "bordercolor": "rgba(148,163,184,0.20)",
                    "borderwidth": 1,
                },
                xaxis={
                    "gridcolor": "rgba(148,163,184,0.12)",
                    "zerolinecolor": "rgba(148,163,184,0.22)",
                    "linecolor": "rgba(148,163,184,0.26)",
                    "automargin": True,
                },
                yaxis={
                    "gridcolor": "rgba(148,163,184,0.12)",
                    "zerolinecolor": "rgba(148,163,184,0.22)",
                    "linecolor": "rgba(148,163,184,0.26)",
                    "automargin": True,
                },
            )
        )

    pio.templates.default = f"plotly_dark+{_TEMPLATE_NAME}"


__all__ = ["register_plotly_theme"]
