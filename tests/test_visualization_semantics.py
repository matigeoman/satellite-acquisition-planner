from __future__ import annotations

from datetime import datetime, timezone

from app.tracking import ObserverSite
from app.visualization.live_tracking import (
    build_live_ground_map_figure,
    build_sky_map_figure,
)


def test_sky_map_uses_standard_local_horizon_convention() -> None:
    figure = build_sky_map_figure(
        states=(),
        tracks=(),
        minimum_elevation_deg=0.0