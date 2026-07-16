from __future__ import annotations

from datetime import datetime, timezone

from app.catalogs.models import (
    ParameterOrigin,
    ParameterSource,
    ProductSizeRange,
    PublicMissionProfile,
)
from app.models.enums import (
    FrequencyBand,
    LookSideCapability,
    ModeCategory,
    OrbitSourceType,
    OrbitType,
    ProductType,
    ReferenceFrame,
    SensorSourceType,
    SensorType,
)
from app.models.imaging import ImagingMode
from app.models.orbit import OrbitDefinition
from app.models.sensor import Sensor


ICEYE_IMAGING_MODES_REFERENCE = (
    "https://sar.iceye.com/6.0.7/productspecification/imagingmodes/"
)
ICEYE_API_REFERENCE = "https://www.iceye.com/sar-data/api"


def _estimated_rate(
    minimum_product_mb: float,
    maximum_product_mb: float,
    typical_duration_s: float,
) -> float:
    """Wyznacza modelową szybkość danych z mediany zakresu produktu GRD."""

    return (
        (minimum_product_mb + maximum_product_mb)
        / 2.0
        / typical_duration_s
    )


def _sar_mode(
    *,
    mode_id: str,
    name: str,
    category: ModeCategory,
    resolution_m: float,
    width_km: float,
    length_km: float,
    typical_duration_s: float,
    maximum_duration_s: float,
    incidence_min_deg: float,
    incidence_max_deg: float,
    product_min_mb: float,
    product_max_mb: float,
    quality_factor: float,
) -> ImagingMode:
    return ImagingMode(
        mode_id=mode_id,
        name=name,
        sensor_type=SensorType.SAR,
        mode_category=category,
        product_type=ProductType.SAR_IMAGE,
        nominal_resolution_m=resolution_m,
        nominal_scene_width_km=width_km,
        nominal_scene_length_km=length_km,
        min_acquisition_duration_s=typical_duration_s,
        max_acquisition_duration_s=maximum_duration_s,
        data_rate_mb_s=_estimated_rate(
            product_min_mb,
            product_max_mb,
            typical_duration_s,
        ),
        max_off_nadir_deg=45.0,
        min_incidence_angle_deg=incidence_min_deg,
        max_incidence_angle_deg=incidence_max_deg,
        polarizations=["VV"],
        spectral_bands=None,
        quality_factor=quality_factor,
        notes=(
            "Parametry geometryczne pochodzą z ICEYE Product "
            "Documentation 6.0.7. data_rate_mb_s jest wartością "
            "modelową wyznaczoną z połowy publicznego zakresu "
            "rozmiaru produktu GRD i typowego czasu kolekcji."
        ),
    )


_PRODUCT_RANGES = {
    "MODE-SAR-ICEYE-SPOT": ProductSizeRange(
        minimum_mb=100,
        maximum_mb=400,
        product_name="GRD",
        origin=ParameterOrigin.PUBLIC_DATA,
    ),
    "MODE-SAR-ICEYE-SPOT-FINE": ProductSizeRange(
        minimum_mb=400,
        maximum_mb=1100,
        product_name="GRD",
        origin=ParameterOrigin.PUBLIC_DATA,
    ),
    "MODE-SAR-ICEYE-SLEA": ProductSizeRange(
        minimum_mb=1000,
        maximum_mb=3000,
        product_name="GRD",
        origin=ParameterOrigin.PUBLIC_DATA,
    ),
    "MODE-SAR-ICEYE-DWELL": ProductSizeRange(
        minimum_mb=120,
        maximum_mb=300,
        product_name="GRD",
        origin=ParameterOrigin.PUBLIC_DATA,
    ),
    "MODE-SAR-ICEYE-DWELL-FINE": ProductSizeRange(
        minimum_mb=400,
        maximum_mb=1400,
        product_name="GRD",
        origin=ParameterOrigin.PUBLIC_DATA,
    ),
    "MODE-SAR-ICEYE-DWELL-PRECISE": ProductSizeRange(
        minimum_mb=2000,
        maximum_mb=4000,
        product_name="GRD",
        origin=ParameterOrigin.PUBLIC_DATA,
    ),
    "MODE-SAR-ICEYE-STRIP": ProductSizeRange(
        minimum_mb=600,
        maximum_mb=1400,
        product_name="GRD",
        origin=ParameterOrigin.PUBLIC_DATA,
    ),
    "MODE-SAR-ICEYE-SCAN": ProductSizeRange(
        minimum_mb=700,
        maximum_mb=1300,
        product_name="GRD",
        origin=ParameterOrigin.PUBLIC_DATA,
    ),
    "MODE-SAR-ICEYE-SCAN-WIDE": ProductSizeRange(
        minimum_mb=800,
        maximum_mb=1600,
        product_name="GRD",
        origin=ParameterOrigin.PUBLIC_DATA,
    ),
}


def build_iceye_public_profile() -> PublicMissionProfile:
    """Buduje jawny profil bazowy ICEYE używany przed przypisaniem TLE."""

    modes = [
        _sar_mode(
            mode_id="MODE-SAR-ICEYE-SPOT",
            name="ICEYE Spot",
            category=ModeCategory.SPOTLIGHT,
            resolution_m=1.0,
            width_km=5,
            length_km=5,
            typical_duration_s=10,
            maximum_duration_s=10,
            incidence_min_deg=20,
            incidence_max_deg=40,
            product_min_mb=100,
            product_max_mb=400,
            quality_factor=0.92,
        ),
        _sar_mode(
            mode_id="MODE-SAR-ICEYE-SPOT-FINE",
            name="ICEYE Spot Fine",
            category=ModeCategory.SPOTLIGHT,
            resolution_m=0.5,
            width_km=5,
            length_km=5,
            typical_duration_s=15,
            maximum_duration_s=15,
            incidence_min_deg=20,
            incidence_max_deg=40,
            product_min_mb=400,
            product_max_mb=1100,
            quality_factor=0.97,
        ),
        _sar_mode(
            mode_id="MODE-SAR-ICEYE-SLEA",
            name="ICEYE Spot Extended Area",
            category=ModeCategory.SPOTLIGHT,
            resolution_m=1.0,
            width_km=15,
            length_km=15,
            typical_duration_s=10,
            maximum_duration_s=10,
            incidence_min_deg=20,
            incidence_max_deg=40,
            product_min_mb=1000,
            product_max_mb=3000,
            quality_factor=0.90,
        ),
        _sar_mode(
            mode_id="MODE-SAR-ICEYE-DWELL",
            name="ICEYE Dwell",
            category=ModeCategory.SPOTLIGHT,
            resolution_m=1.0,
            width_km=5,
            length_km=5,
            typical_duration_s=25,
            maximum_duration_s=25,
            incidence_min_deg=20,
            incidence_max_deg=40,
            product_min_mb=120,
            product_max_mb=300,
            quality_factor=0.95,
        ),
        _sar_mode(
            mode_id="MODE-SAR-ICEYE-DWELL-FINE",
            name="ICEYE Dwell Fine",
            category=ModeCategory.SPOTLIGHT,
            resolution_m=0.5,
            width_km=5,
            length_km=5,
            typical_duration_s=25,
            maximum_duration_s=25,
            incidence_min_deg=20,
            incidence_max_deg=40,
            product_min_mb=400,
            product_max_mb=1400,
            quality_factor=0.98,
        ),
        _sar_mode(
            mode_id="MODE-SAR-ICEYE-DWELL-PRECISE",
            name="ICEYE Dwell Precise",
            category=ModeCategory.SPOTLIGHT,
            resolution_m=0.25,
            width_km=5,
            length_km=5,
            typical_duration_s=25,
            maximum_duration_s=25,
            incidence_min_deg=20,
            incidence_max_deg=33,
            product_min_mb=2000,
            product_max_mb=4000,
            quality_factor=1.0,
        ),
        _sar_mode(
            mode_id="MODE-SAR-ICEYE-STRIP",
            name="ICEYE Strip",
            category=ModeCategory.STRIPMAP,
            resolution_m=3.0,
            width_km=30,
            length_km=50,
            typical_duration_s=10,
            maximum_duration_s=70,
            incidence_min_deg=15,
            incidence_max_deg=35,
            product_min_mb=600,
            product_max_mb=1400,
            quality_factor=0.80,
        ),
        _sar_mode(
            mode_id="MODE-SAR-ICEYE-SCAN",
            name="ICEYE Scan",
            category=ModeCategory.SCANSAR,
            resolution_m=15.0,
            width_km=100,
            length_km=100,
            typical_duration_s=15,
            maximum_duration_s=70,
            incidence_min_deg=21,
            incidence_max_deg=29,
            product_min_mb=700,
            product_max_mb=1300,
            quality_factor=0.62,
        ),
        _sar_mode(
            mode_id="MODE-SAR-ICEYE-SCAN-WIDE",
            name="ICEYE Scan Wide",
            category=ModeCategory.SCANSAR,
            resolution_m=27.0,
            width_km=200,
            length_km=300,
            typical_duration_s=42,
            maximum_duration_s=84,
            incidence_min_deg=21,
            incidence_max_deg=26,
            product_min_mb=800,
            product_max_mb=1600,
            quality_factor=0.50,
        ),
    ]

    sensor = Sensor(
        sensor_id="SENSOR-SAR-ICEYE-PUBLIC",
        name="ICEYE X-band SAR public baseline",
        sensor_type=SensorType.SAR,
        imaging_modes=modes,
        frequency_band=FrequencyBand.X,
        cloud_sensitive=False,
        daylight_required=False,
        minimum_sun_elevation_deg=None,
        default_max_cloud_cover=None,
        look_side_capability=LookSideCapability.BOTH,
        warmup_time_s=0,
        cooldown_time_s=0,
        maximum_continuous_acquisition_s=84,
        source_type=SensorSourceType.PUBLIC_DATA,
        source_reference=ICEYE_IMAGING_MODES_REFERENCE,
        notes=(
            "Profil bazowy publicznej specyfikacji produktów. Dokładna "
            "dostępność trybów może różnić się pomiędzy generacjami "
            "i pojedynczymi satelitami ICEYE."
        ),
    )

    orbit_template = OrbitDefinition(
        orbit_id="ORB-SAR-ICEYE-PUBLIC",
        name="ICEYE public orbit placeholder",
        orbit_type=OrbitType.CIRCULAR_SSO,
        altitude_km=570,
        inclination_deg=97.7,
        eccentricity=0.0,
        raan_deg=0.0,
        argument_of_perigee_deg=0.0,
        epoch_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        reference_frame=ReferenceFrame.J2000,
        is_sun_synchronous=True,
        source_type=OrbitSourceType.MODEL,
        notes=(
            "Wyłącznie szablon do interfejsu. W następnym etapie zostanie "
            "zastąpiony aktualnym OMM/TLE i propagacją SGP4."
        ),
    )

    return PublicMissionProfile(
        profile_id="PROFILE-ICEYE-PUBLIC",
        name="ICEYE public baseline",
        operator="ICEYE",
        description=(
            "Publiczny profil sensora SAR ICEYE. Parametry trybów są "
            "zaczerpnięte z Product Documentation 6.0.7, natomiast "
            "orbita jest tylko szablonem oczekującym na aktualne TLE/OMM."
        ),
        satellite_slots=4,
        satellite_labels=[
            "ICEYE public satellite 1",
            "ICEYE public satellite 2",
            "ICEYE public satellite 3",
            "ICEYE public satellite 4",
        ],
        orbit_template=orbit_template,
        sensor=sensor,
        product_sizes_by_mode=_PRODUCT_RANGES,
        parameter_sources=[
            ParameterSource(
                parameter_group="tryby, sceny, czasy i kąty padania",
                origin=ParameterOrigin.PUBLIC_DATA,
                reference=ICEYE_IMAGING_MODES_REFERENCE,
            ),
            ParameterSource(
                parameter_group="data_rate_mb_s i quality_factor",
                origin=ParameterOrigin.MODEL_DERIVED,
                reference=ICEYE_IMAGING_MODES_REFERENCE,
                notes=(
                    "Wartości pomocnicze do optymalizacji. Nie są "
                    "deklarowanymi parametrami operacyjnymi operatora."
                ),
            ),
            ParameterSource(
                parameter_group="orbita każdej jednostki",
                origin=ParameterOrigin.TLE_PENDING,
                reference="CelesTrak GP/OMM — etap propagacji SGP4",
            ),
        ],
    )


ICEYE_PUBLIC_PROFILE = build_iceye_public_profile()
