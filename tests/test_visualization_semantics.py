from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.tracking import ObserverSite
from app.visualization.live_tracking import (
    build_live_ground_map_figure,
    build_sky_map_figure,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_sky_map_uses_standard_local_horizon_convention() -> None:
    figure = build_sky_map_figure(
        states=(),
        tracks=(),
        minimum_elevation_deg=0.0,
    )

    polar = figure.layout.polar
    assert polar.angularaxis.direction == "clockwise"
    assert polar.angularaxis.rotation == 90
    assert list(polar.angularaxis.tickvals) == [
        0,
        45,
        90,
        135,
        180,
        225,
        270,
        315,
    ]
    assert list(polar.angularaxis.ticktext) == [
        "N",
        "NE",
        "E",
        "SE",
        "S",
        "SW",
        "W",
        "NW",
    ]
    assert list(polar.radialaxis.tickvals) == [0, 15, 30, 45, 60, 75, 90]
    assert list(polar.radialaxis.ticktext) == [
        "90°",
        "75°",
        "60°",
        "45°",
        "30°",
        "15°",
        "0°",
    ]


def test_ground_map_without_selected_satellite_does_not_invent_footprint() -> None:
    figure = build_live_ground_map_figure(
        observer=ObserverSite(
            name="WAT Warszawa",
            latitude_deg=52.2532,
            longitude_deg=20.8997,
            altitude_m=110.0,
        ),
        states=(),
        tracks=(),
        timestamp_utc=datetime(2026, 8, 5, tzinfo=timezone.utc),
        selected_slot_id=None,
        footprint_radius_km=75.0,
        show_ground_tracks=False,
        show_footprint=True,
        show_terminator=False,
    )

    assert all(trace.name != "Referencyjny footprint" for trace in figure.data)


def test_ui_and_documentation_describe_footprint_as_reference_only() -> None:
    ui_text = (
        PROJECT_ROOT / "app" / "ui" / "pages" / "live_tracking.py"
    ).read_text(encoding="utf-8")
    semantics = (
        PROJECT_ROOT / "docs" / "visualization_semantics.md"
    ).read_text(encoding="utf-8")

    assert "referencyjnym footprintem prezentacyjnym" in ui_text
    assert "Nie zastępuje geometrii konkretnego trybu obrazowania" in ui_text
    assert "nie rzeczywisty footprint konkretnego trybu obrazowania" in semantics


def test_visualization_document_rejects_attitude_and_phasing_overclaims() -> None:
    semantics = (
        PROJECT_ROOT / "docs" / "visualization_semantics.md"
    ).read_text(encoding="utf-8")

    assert "Aplikacja nie wyznacza" in semantics
    assert "orientacji attitude" in semantics
    assert "nie ma osobnego modelu wizualizacji fazowania" in semantics
    assert "chwilowe rozmieszczenie propagowanych obiektów" in semantics
