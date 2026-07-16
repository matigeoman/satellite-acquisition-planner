"""Geometria sensora i publiczne okna dostępu z propagacji SGP4."""

from app.integrations.access.calculator import GeometricAccessCalculator
from app.integrations.access.geometry import (
    approximate_aoi_extent_km,
    approximate_coverage_ratio,
    geodetic_to_ecef,
    haversine_distance_km,
    observation_side,
    solar_elevation_deg,
    target_look_angles,
)
from app.integrations.access.models import (
    AccessCalculationResult,
    AccessPathPoint,
    GeometricAccessWindow,
)

__all__ = [
    "AccessCalculationResult",
    "AccessPathPoint",
    "GeometricAccessCalculator",
    "GeometricAccessWindow",
    "approximate_aoi_extent_km",
    "approximate_coverage_ratio",
    "geodetic_to_ecef",
    "haversine_distance_km",
    "observation_side",
    "solar_elevation_deg",
    "target_look_angles",
]
