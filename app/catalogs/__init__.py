"""Publiczne profile misji używane przez warstwę integracyjną."""

from app.catalogs.iceye import ICEYE_PUBLIC_PROFILE, build_iceye_public_profile
from app.catalogs.models import (
    ParameterOrigin,
    ParameterSource,
    ProductSizeRange,
    PublicMissionProfile,
)
from app.catalogs.pleiades_neo import (
    PLEIADES_NEO_PUBLIC_PROFILE,
    build_pleiades_neo_public_profile,
)

PUBLIC_MISSION_PROFILES = {
    ICEYE_PUBLIC_PROFILE.profile_id: ICEYE_PUBLIC_PROFILE,
    PLEIADES_NEO_PUBLIC_PROFILE.profile_id: PLEIADES_NEO_PUBLIC_PROFILE,
}

__all__ = [
    "ICEYE_PUBLIC_PROFILE",
    "PLEIADES_NEO_PUBLIC_PROFILE",
    "PUBLIC_MISSION_PROFILES",
    "ParameterOrigin",
    "ParameterSource",
    "ProductSizeRange",
    "PublicMissionProfile",
    "build_iceye_public_profile",
    "build_pleiades_neo_public_profile",
]
